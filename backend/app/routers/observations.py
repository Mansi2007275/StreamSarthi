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
    Indicator,
    IndicatorResult,
    ObservationCreate,
    ObservationCreated,
    ObservationOut,
    ObservationPage,
    ObservationSummary,
)
from app.services import ai_opinion, audit
from app.services import photo_quality as pq
from app.services.consistency import check_observation, is_strong_disagreement
from app.services.db import RepoProtocol, get_repo, now_iso
from app.services.indicators import get_indicator, load_indicators
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
    _audit_best_effort(repo, obs["id"], user.id, "observation_created", {"lat": body.lat, "lng": body.lng})
    return ObservationCreated(id=obs["id"], status=obs["status"])


@router.post("/observations/{obs_id}/indicators/{indicator_id}", response_model=IndicatorResult)
async def answer_indicator(
    obs_id: str,
    indicator_id: str,
    human_score: int | None = Form(default=None),
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


@router.post("/observations/{obs_id}/submit", response_model=ObservationOut)
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

    issues = check_observation(obs, answers)
    profile = repo.get_profile(user.id)
    observer_accuracy = profile.get("observer_accuracy") if profile else None
    trust = compute_trust(obs, answers, load_indicators(), observer_accuracy, issues)

    status = "needs_review" if trust["needs_review"] else "submitted"
    obs = repo.update_observation(
        obs_id,
        {
            "status": status,
            "submitted_at": now_iso(),
            "trust_score": trust["score"],
            "trust_breakdown": trust,
        },
    )

    for a in answers:
        if is_strong_disagreement(a):
            existing = list(a.get("flags") or [])
            if "strong_disagreement" not in existing:
                repo.update_answer(obs_id, a["indicator_id"], {"flags": existing + ["strong_disagreement"]})

    _audit_best_effort(repo, obs_id, user.id, "submitted", {"trust_score": trust["score"]})
    if issues:
        _audit_best_effort(repo, obs_id, user.id, "flagged", {"issues": [i["code"] for i in issues]})
    if trust["needs_review"]:
        _audit_best_effort(repo, obs_id, user.id, "routed_to_review", {"trust_score": trust["score"]})

    log_event("trust_computed", observation_id=obs_id, score=trust["score"], needs_review=trust["needs_review"])

    answers = repo.list_answers(obs_id)  # refreshed, so the response reflects the new flags
    return _observation_out(obs, answers, storage)


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
