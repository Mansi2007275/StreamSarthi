import logging
from functools import lru_cache

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from app.core.auth import CurrentUser, get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import AppError, not_found
from app.core.logging import log_event
from app.core.ratelimit import RateLimiter
from app.models.schemas import (
    AnswerChoice,
    AnswerOut,
    AuditResponse,
    Confidence,
    Indicator,
    IndicatorResult,
    ObservationCreate,
    ObservationCreated,
    ObservationOut,
    ObservationPage,
    ObservationSummary,
    SubmitResult,
)
from app.services import ai_opinion, audit, points
from app.services import photo_quality as pq
from app.services.consistency import check_observation, is_disagreement, is_strong_disagreement
from app.services.db import RepoProtocol, get_repo, now_iso
from app.services.game_config import load_game_config
from app.services.indicators import get_indicator, load_indicators
from app.services.one_health import compute_one_health
from app.services.scoring import final_score
from app.services.storage import StorageProtocol, get_storage, photo_path, process_image
from app.services.trust import compute_trust

logger = logging.getLogger("streamsaathi")

router = APIRouter(prefix="/api/v1", tags=["observations"])


def _audit_best_effort(repo: RepoProtocol, obs_id: str, actor_id: str, event: str, payload: dict) -> None:
    """Citizen-flow audit writes are best-effort: they must never block a citizen action."""
    try:
        audit.append_event(repo, obs_id, actor_id, event, payload)
    except Exception:
        logger.exception("audit_failed", extra={"extra_fields": {"observation_id": obs_id, "event": event}})


@lru_cache
def get_ai_limiter() -> RateLimiter:
    return RateLimiter(get_settings().ai_rate_limit_per_minute, 60)


# ---------------- helpers ----------------
def _user(request: Request, user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    request.state.user_id = user.id  # so the request log line has user_id
    return user


def _own_observation(repo: RepoProtocol, obs_id: str, user: CurrentUser) -> dict:
    """404 (not 403) when it isn't yours: don't leak that the id exists."""
    obs = repo.get_observation(obs_id)
    if not obs or obs["user_id"] != user.id:
        raise not_found("Observation")
    return obs


def _require_draft(obs: dict) -> None:
    if obs["status"] != "draft":
        raise AppError(409, "NOT_EDITABLE", "Observation is already submitted")


def _indicator_or_404(indicator_id: str) -> Indicator:
    ind = get_indicator(indicator_id)
    if not ind:
        raise not_found("Indicator")
    return ind


def _check_score(score: int | None, ind: Indicator) -> None:
    lo, hi = ind.scale
    if score is not None and not lo <= score <= hi:
        raise AppError(422, "VALIDATION_ERROR", f"human_score must be between {lo} and {hi}")


def _answer_out(ans: dict, storage: StorageProtocol | None = None) -> AnswerOut:
    url = storage.signed_url(ans["photo_path"]) if storage and ans.get("photo_path") else None
    return AnswerOut(
        indicator_id=ans["indicator_id"],
        human_score=ans.get("human_score"),
        ai_score=ans.get("ai_score"),
        ai_confidence=ans.get("ai_confidence"),
        ai_reason=ans.get("ai_reason"),
        ai_evidence=ans.get("ai_evidence") or [],
        used_ai_answer=bool(ans.get("used_ai_answer")),
        final_score=final_score(ans),
        photo_url=url,
        photo_quality=ans.get("photo_quality"),
        flags=ans.get("flags") or [],
        expert_score=ans.get("expert_score"),
        human_confidence=ans.get("human_confidence"),
        crowd_score=ans.get("crowd_score"),
        crowd_votes=ans.get("crowd_votes") or 0,
        crowd_status=ans.get("crowd_status"),
    )


def _observation_out(obs: dict, answers: list[dict], storage: StorageProtocol | None) -> ObservationOut:
    order = {ind.id: i for i, ind in enumerate(load_indicators())}
    answers = sorted(answers, key=lambda a: order.get(a["indicator_id"], 999))
    return ObservationOut(
        id=obs["id"],
        status=obs["status"],
        lat=obs.get("lat"),
        lng=obs.get("lng"),
        created_at=obs.get("created_at"),
        submitted_at=obs.get("submitted_at"),
        trust_score=obs.get("trust_score"),
        trust_breakdown=obs.get("trust_breakdown"),
        review_note=obs.get("review_note"),
        reviewed_at=obs.get("reviewed_at"),
        one_health=obs.get("one_health"),
        site_id=obs.get("site_id"),
        source=obs.get("source") or "app",
        answers=[_answer_out(a, storage) for a in answers],
    )


# ---------------- endpoints ----------------
@router.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@router.get("/indicators", response_model=list[Indicator])
def indicators(_: CurrentUser = Depends(_user)):
    return load_indicators()


@router.post("/observations", response_model=ObservationCreated, status_code=201)
def create_observation(
    body: ObservationCreate,
    user: CurrentUser = Depends(_user),
    repo: RepoProtocol = Depends(get_repo),
):
    repo.ensure_profile(user.id, user.email)
    obs = repo.create_observation(user.id, body.lat, body.lng)
    if body.source != "app":
        repo.update_observation(obs["id"], {"source": body.source})

    # Resolve the site now, while the client still knows what the citizen chose on the site
    # step. A confirmed site must exist; a new place is created here so its name is kept.
    site_id, site_name = None, None
    if body.site_id:
        site = repo.get_site(body.site_id)
        if not site:
            raise not_found("Site")
        site_id, site_name = site["id"], site.get("name")
    elif body.site_name and body.lat is not None and body.lng is not None:
        site = repo.create_site(body.lat, body.lng, body.site_name.strip() or None)
        site_id, site_name = site["id"], site.get("name")
    if site_id:
        repo.update_observation(obs["id"], {"site_id": site_id})

    _audit_best_effort(repo, obs["id"], user.id, "observation_created", {"lat": body.lat, "lng": body.lng})
    return ObservationCreated(id=obs["id"], status=obs["status"], site_id=site_id, site_name=site_name)


@router.post("/observations/{obs_id}/indicators/{indicator_id}", response_model=IndicatorResult)
async def answer_indicator(
    obs_id: str,
    indicator_id: str,
    human_score: int | None = Form(default=None),
    human_confidence: Confidence | None = Form(default=None),
    photo: UploadFile | None = File(default=None),
    user: CurrentUser = Depends(_user),
    repo: RepoProtocol = Depends(get_repo),
    storage: StorageProtocol = Depends(get_storage),
    settings: Settings = Depends(get_settings),
    limiter: RateLimiter = Depends(get_ai_limiter),
):
    obs = _own_observation(repo, obs_id, user)
    _require_draft(obs)
    ind = _indicator_or_404(indicator_id)
    _check_score(human_score, ind)

    if photo is None and ind.photo_required:
        raise AppError(422, "PHOTO_REQUIRED", "A photo is required for this indicator")

    row: dict = {
        "observation_id": obs_id,
        "indicator_id": indicator_id,
        "human_score": human_score,
        # Asked after the score and before the AI is called, so the citizen commits to both
        # their answer and how sure they are without the AI having nudged either.
        "human_confidence": human_confidence,
        "used_ai_answer": False,
    }
    opinion = ai_opinion.FALLBACK.model_copy(update={"reason": "No photo, so no AI opinion"})
    quality: dict | None = None
    flags: list[str] = []

    if photo is not None:
        clean = process_image(await photo.read(), photo.content_type, settings.max_upload_mb)
        path = photo_path(user.id, obs_id, indicator_id)
        try:
            storage.upload(path, clean)
        except Exception as e:
            raise AppError(502, "STORAGE_ERROR", "Could not save the photo, please retry") from e
        row["photo_path"] = path

        try:
            previous_hashes = repo.recent_phashes(user.id, obs_id)
            quality = await run_in_threadpool(pq.check_quality, clean, previous_hashes)
            flags = pq.quality_flags(quality)
        except Exception:
            logger.exception("photo_quality_failed")
            quality, flags = None, []

        limiter.check(user.id)
        opinion = await ai_opinion.get_opinion(clean, ind, settings)

    row.update(
        ai_score=opinion.suggested_score,
        ai_confidence=opinion.confidence,
        ai_reason=opinion.reason,
        ai_evidence=opinion.visible_evidence,
        photo_quality=quality,
        flags=flags,
    )
    repo.upsert_answer(row)  # unique(observation_id, indicator_id) -> retake overwrites, no duplicates

    if opinion.suggested_score is not None:
        _audit_best_effort(
            repo,
            obs_id,
            user.id,
            "ai_suggested",
            {"indicator": indicator_id, "ai_score": opinion.suggested_score, "confidence": opinion.confidence},
        )

    disagreement = is_disagreement(
        {
            "human_score": human_score,
            "ai_score": opinion.suggested_score,
            "ai_can_assess": opinion.can_assess,
        }
    )
    return IndicatorResult(
        indicator_id=indicator_id,
        human_score=human_score,
        ai_score=opinion.suggested_score,
        confidence=opinion.confidence,
        reason=opinion.reason,
        evidence=opinion.visible_evidence,
        can_assess=opinion.can_assess,
        retake_tip=opinion.retake_tip,
        photo_quality=quality,
        flags=flags,
        human_confidence=human_confidence,
        disagreement=disagreement,
    )


@router.patch("/observations/{obs_id}/indicators/{indicator_id}", response_model=AnswerOut)
def choose_answer(
    obs_id: str,
    indicator_id: str,
    body: AnswerChoice,
    user: CurrentUser = Depends(_user),
    repo: RepoProtocol = Depends(get_repo),
):
    obs = _own_observation(repo, obs_id, user)
    _require_draft(obs)
    ind = _indicator_or_404(indicator_id)
    ans = repo.get_answer(obs_id, indicator_id)
    if not ans:
        raise not_found("Answer")

    fields: dict = {"used_ai_answer": body.used_ai_answer}
    if body.used_ai_answer and ans.get("ai_score") is None:
        raise AppError(409, "NO_AI_SCORE", "AI has no score for this indicator, keep your own answer")
    if body.human_score is not None:
        _check_score(body.human_score, ind)
        fields["human_score"] = body.human_score
    if body.human_confidence is not None:
        # "Not sure - ask an expert" lands here: downgrade the confidence, keep the score.
        fields["human_confidence"] = body.human_confidence
    updated = repo.update_answer(obs_id, indicator_id, fields)
    event = "human_used_ai" if body.used_ai_answer else "human_kept_own"
    _audit_best_effort(
        repo,
        obs_id,
        user.id,
        event,
        {"indicator": indicator_id, "human_score": updated.get("human_score"), "ai_score": updated.get("ai_score")},
    )
    return _answer_out(updated)


@router.post("/observations/{obs_id}/submit", response_model=SubmitResult)
def submit(
    obs_id: str,
    user: CurrentUser = Depends(_user),
    repo: RepoProtocol = Depends(get_repo),
    storage: StorageProtocol = Depends(get_storage),
):
    obs = _own_observation(repo, obs_id, user)
    _require_draft(obs)
    answers = repo.list_answers(obs_id)
    answered = {a["indicator_id"] for a in answers if final_score(a) is not None}
    missing = [i.label for i in load_indicators() if i.required and i.id not in answered]
    if missing:
        raise AppError(422, "MISSING_INDICATORS", "Please answer: " + ", ".join(missing))

    cfg = load_game_config()
    issues = check_observation(obs, answers, cfg)
    profile = repo.get_profile(user.id)
    observer_accuracy = profile.get("observer_accuracy") if profile else None
    trust = compute_trust(obs, answers, load_indicators(), observer_accuracy, issues)

    status = "needs_review" if trust["needs_review"] else "submitted"

    site_id = obs.get("site_id")
    if site_id is None and obs.get("lat") is not None and obs.get("lng") is not None:
        # Named only if the citizen offered a name on the site step; otherwise it shows as
        # coordinates until somebody names it. Best-effort: a site is metadata, and failing
        # to create one must not cost the citizen their submission.
        try:
            site_id = repo.create_site(obs["lat"], obs["lng"], None)["id"]
        except Exception:
            logger.exception("site_create_failed", extra={"extra_fields": {"observation_id": obs_id}})

    one_health = None
    try:
        one_health = compute_one_health({**obs, "status": status}, answers, load_indicators())
    except Exception:
        logger.exception("one_health_failed", extra={"extra_fields": {"observation_id": obs_id}})

    obs = repo.update_observation(
        obs_id,
        {
            "status": status,
            "submitted_at": now_iso(),
            "trust_score": trust["score"],
            "trust_breakdown": trust,
            "one_health": one_health,
            "site_id": site_id,
        },
    )

    for a in answers:
        if is_strong_disagreement(a):
            existing = list(a.get("flags") or [])
            if "strong_disagreement" not in existing:
                repo.update_answer(obs_id, a["indicator_id"], {"flags": existing + ["strong_disagreement"]})

    # Points for a stream check start PENDING: being right is what pays, not posting. They
    # settle when the crowd verifies (routers/play.py) or an expert reviews (Phase 4).
    # Best-effort: a failed ledger write must never cost the citizen their submission.
    pending_points = 0
    try:
        rows = points.pending_rows_for_submit(user.id, answers)
        existing = {points.dedupe_key(p) for p in repo.list_points(user.id)}
        repo.insert_points(points.filter_new(rows, existing))
        answer_ids = {a["id"] for a in answers if a.get("id")}
        pending_points = sum(
            p["amount"]
            for p in repo.list_points(user.id, status=points.PENDING)
            if p["ref_id"] in answer_ids
        )
    except Exception:
        logger.exception("pending_points_failed", extra={"extra_fields": {"observation_id": obs_id}})

    _audit_best_effort(repo, obs_id, user.id, "submitted", {"trust_score": trust["score"]})
    if issues:
        _audit_best_effort(repo, obs_id, user.id, "flagged", {"issues": [i["code"] for i in issues]})
    if trust["needs_review"]:
        _audit_best_effort(repo, obs_id, user.id, "routed_to_review", {"trust_score": trust["score"]})

    log_event("trust_computed", observation_id=obs_id, score=trust["score"], needs_review=trust["needs_review"])

    answers = repo.list_answers(obs_id)  # refreshed, so the response reflects the new flags
    return SubmitResult(
        **_observation_out(obs, answers, storage).model_dump(),
        pending_points=pending_points,
        routed_to="expert" if status == "needs_review" else "crowd",
        routing_reasons=[i["code"] for i in issues],
    )


@router.get("/observations/mine", response_model=ObservationPage)
def my_observations(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(_user),
    repo: RepoProtocol = Depends(get_repo),
):
    items, total = repo.list_observations(user.id, offset, limit)
    return ObservationPage(
        items=[ObservationSummary.model_validate(o) for o in items], total=total, offset=offset, limit=limit
    )


@router.get("/observations/{obs_id}", response_model=ObservationOut)
def observation_detail(
    obs_id: str,
    user: CurrentUser = Depends(_user),
    repo: RepoProtocol = Depends(get_repo),
    storage: StorageProtocol = Depends(get_storage),
):
    obs = _own_observation(repo, obs_id, user)
    return _observation_out(obs, repo.list_answers(obs_id), storage)


@router.get("/observations/{obs_id}/audit", response_model=AuditResponse)
def observation_audit(
    obs_id: str,
    user: CurrentUser = Depends(_user),
    repo: RepoProtocol = Depends(get_repo),
):
    obs = repo.get_observation(obs_id)
    if not obs:
        raise not_found("Observation")
    profile = repo.get_profile(user.id)
    is_owner = obs["user_id"] == user.id
    is_reviewer = bool(profile and profile.get("role") in ("expert", "admin"))
    if not is_owner and not is_reviewer:
        raise not_found("Observation")

    events = repo.list_audit_events(obs_id)
    verification = audit.verify_chain(events)

    role_cache: dict[str, str] = {}

    def role_of(actor_id: str | None) -> str:
        if actor_id is None:
            return "system"
        if actor_id not in role_cache:
            p = repo.get_profile(actor_id)
            role_cache[actor_id] = (p or {}).get("role", "citizen")
        return role_cache[actor_id]

    out_events = [
        {
            "event": e["event"],
            "actor_role": role_of(e.get("actor_id")),
            "payload": e["payload"],
            "created_at": e["created_at"],
            "hash_short": f"{e['hash'][:6]}...{e['hash'][-4:]}",
        }
        for e in events
    ]
    return AuditResponse(events=out_events, verification=verification)
