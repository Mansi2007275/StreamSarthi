"""Expert review queue: approve, correct or reject a citizen's observation.

Every endpoint here requires the expert/admin role (require_role), checked
server-side - the frontend's own role check is UX only, not security.
"""

import logging

from fastapi import APIRouter, Depends, Query

from app.core.auth import CurrentUser
from app.core.errors import AppError, not_found
from app.core.logging import log_event
from app.core.roles import require_role
from app.models.schemas import (
    CrowdPanelOut,
    CrowdVoteBucket,
    MakeGoldIn,
    MakeGoldOut,
    ReviewAction,
    ReviewDetail,
    ReviewQueuePage,
    ReviewStatsOut,
)
from app.routers.observations import _observation_out
from app.services import adopted_bonus, audit, points, settle
from app.services import badges as badges_svc
from app.services.db import RepoProtocol, get_repo, now_iso
from app.services.game_config import load_game_config
from app.services.indicators import get_indicator, load_indicators
from app.services.lessons import build_lessons
from app.services.one_health import compute_one_health
from app.services.proof import compute_proof
from app.services.scoring import truth_score
from app.services.storage import StorageProtocol, get_storage
from app.services.trust import updated_accuracy

logger = logging.getLogger("streamsaathi")

router = APIRouter(prefix="/api/v1/review", tags=["review"])

_NEW_STATUS = {"approve": "verified", "correct": "corrected", "reject": "rejected"}
_EVENT = {"approve": "expert_approved", "correct": "expert_corrected", "reject": "expert_rejected"}


def _crowd_panel(repo: RepoProtocol, answers: list[dict]) -> list[CrowdPanelOut]:
    """Per answer: the spread of Guardian votes, anonymised to counts per score.

    Voter identities never leave this function. An expert needs to see that four people
    said 4 and one said 1, not who those people were.
    """
    panel = []
    for answer in answers:
        ind = get_indicator(answer["indicator_id"])
        if ind is None:
            continue
        votes = repo.list_votes_for_answer(answer["id"]) if answer.get("id") else []
        counted = [v for v in votes if not v.get("excluded_reason")]
        lo, hi = ind.scale
        tally = {score: 0 for score in range(lo, hi + 1)}
        for vote in counted:
            if vote.get("score") in tally:
                tally[vote["score"]] += 1
        panel.append(
            CrowdPanelOut(
                indicator_id=answer["indicator_id"],
                label=ind.label,
                crowd_score=answer.get("crowd_score"),
                crowd_votes=answer.get("crowd_votes") or 0,
                crowd_status=answer.get("crowd_status"),
                histogram=[CrowdVoteBucket(score=s, count=c) for s, c in sorted(tally.items())],
                excluded_count=len(votes) - len(counted),
                human_confidence=answer.get("human_confidence"),
            )
        )
    return panel


def _review_detail(
    obs: dict, answers: list[dict], storage: StorageProtocol, repo: RepoProtocol, audit_ok: bool = True
) -> ReviewDetail:
    base = _observation_out(obs, answers, storage)
    citizen = repo.get_profile(obs["user_id"]) or {}
    issues = (obs.get("trust_breakdown") or {}).get("issues") or []
    return ReviewDetail(
        **base.model_dump(),
        citizen_display_name=citizen.get("display_name"),
        citizen_observer_accuracy=citizen.get("observer_accuracy"),
        audit_ok=audit_ok,
        crowd=_crowd_panel(repo, answers),
        routing_reasons=[i.get("code", "") for i in issues if i.get("code")],
    )


@router.get("/queue", response_model=ReviewQueuePage)
def queue(
    status: str = Query("needs_review", pattern="^(needs_review|submitted)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    expert: CurrentUser = Depends(require_role("expert", "admin")),
    repo: RepoProtocol = Depends(get_repo),
):
    items, total = repo.list_review_queue(expert.id, status, offset, limit)
    return ReviewQueuePage(items=items, total=total, offset=offset, limit=limit)


@router.get("/stats", response_model=ReviewStatsOut)
def stats(
    _: CurrentUser = Depends(require_role("expert", "admin")),
    repo: RepoProtocol = Depends(get_repo),
):
    """How rarely an expert was actually needed. The review page leads with this."""
    proof = compute_proof(repo.list_all_observations(), repo.list_all_answers(), load_indicators())
    counts = proof["counts"]
    return ReviewStatsOut(
        total_submitted=counts["total_submitted"],
        needed_expert=counts["needed_expert"],
        share_needed_expert=proof["share_needed_expert"],
        crowd_verified=counts["crowd_verified"],
    )


@router.get("/{obs_id}", response_model=ReviewDetail)
def review_detail(
    obs_id: str,
    _: CurrentUser = Depends(require_role("expert", "admin")),
    repo: RepoProtocol = Depends(get_repo),
    storage: StorageProtocol = Depends(get_storage),
):
    obs = repo.get_observation(obs_id)
    if not obs:
        raise not_found("Observation")
    answers = repo.list_answers(obs_id)
    return _review_detail(obs, answers, storage, repo)


@router.post("/{obs_id}", response_model=ReviewDetail)
def review_action(
    obs_id: str,
    body: ReviewAction,
    expert: CurrentUser = Depends(require_role("expert", "admin")),
    repo: RepoProtocol = Depends(get_repo),
    storage: StorageProtocol = Depends(get_storage),
):
    obs = repo.get_observation(obs_id)
    if not obs:
        raise not_found("Observation")
    if obs["user_id"] == expert.id:
        raise AppError(403, "SELF_REVIEW", "You cannot review your own observation")
    if obs["status"] not in ("needs_review", "submitted"):
        raise AppError(409, "ALREADY_REVIEWED", "This observation was already reviewed")

    answers = repo.list_answers(obs_id)
    answers_by_id = {a["indicator_id"]: a for a in answers}

    if body.action == "correct":
        if not body.corrections:
            raise AppError(422, "VALIDATION_ERROR", "corrections must not be empty for a correction")
        changed = False
        for ind_id, score in body.corrections.items():
            ans = answers_by_id.get(ind_id)
            if not ans:
                raise AppError(422, "VALIDATION_ERROR", f"No answer for indicator {ind_id!r} in this observation")
            ind = get_indicator(ind_id)
            if not ind:
                raise AppError(422, "VALIDATION_ERROR", f"Unknown indicator {ind_id!r}")
            lo, hi = ind.scale
            if not lo <= score <= hi:
                raise AppError(422, "VALIDATION_ERROR", f"{ind_id}: score must be between {lo} and {hi}")
            if score != truth_score(ans):
                changed = True
        if not changed:
            raise AppError(422, "VALIDATION_ERROR", "At least one correction must differ from the current score")
    elif body.corrections:
        raise AppError(422, "VALIDATION_ERROR", "corrections must be empty for approve/reject")

    if body.action == "correct":
        for ind_id, score in body.corrections.items():
            repo.update_answer(obs_id, ind_id, {"expert_score": score})

        try:
            for lesson in build_lessons(obs, answers, body.corrections, body.note):
                repo.upsert_lesson(lesson)
        except Exception:
            logger.exception("lesson_creation_failed", extra={"extra_fields": {"observation_id": obs_id}})

        answers = repo.list_answers(obs_id)  # refresh with expert_score

    new_status = _NEW_STATUS[body.action]

    one_health = None
    try:
        one_health = compute_one_health({**obs, "status": new_status}, answers, load_indicators())
    except Exception:
        logger.exception("one_health_failed", extra={"extra_fields": {"observation_id": obs_id}})

    obs = repo.update_observation(
        obs_id,
        {
            "status": new_status,
            "reviewed_by": expert.id,
            "reviewed_at": now_iso(),
            "review_note": body.note,
            "one_health": one_health,
        },
    )

    # Rejections are usually about bad photos or wrong locations, not scoring
    # judgment, so they never move the citizen's observer accuracy.
    if body.action != "reject":
        profile = repo.get_profile(obs["user_id"])
        old_accuracy = (profile or {}).get("observer_accuracy")
        new_accuracy = updated_accuracy(old_accuracy, answers, body.corrections)
        repo.update_profile(obs["user_id"], {"observer_accuracy": new_accuracy})

    audit_ok = True
    try:
        audit.append_event(
            repo, obs_id, expert.id, _EVENT[body.action], {"corrections": body.corrections, "note": body.note}
        )
    except Exception:
        logger.exception("audit_failed", extra={"extra_fields": {"observation_id": obs_id}})
        audit_ok = False

    # Everything below is a side effect of the decision. The state change above is already
    # saved, so a failure here must never undo the review (global rule 6).
    _settle_everyone(repo, obs, answers, body.action, body.corrections)

    log_event("review_action", observation_id=obs_id, action=body.action, expert_id=expert.id)

    answers = repo.list_answers(obs_id)
    return _review_detail(obs, answers, storage, repo, audit_ok=audit_ok)


def _best_effort(what: str, fn, **log_fields):
    try:
        return fn()
    except Exception:
        logger.exception(f"{what}_failed", extra={"extra_fields": log_fields})
        return None


def _settle_everyone(
    repo: RepoProtocol,
    obs: dict,
    answers: list[dict],
    action: str,
    corrections: dict[str, int],
) -> None:
    """Settle the citizen's points, judge the crowd's votes against the expert, send receipts."""
    cfg = load_game_config()
    obs_id, citizen_id = obs["id"], obs["user_id"]

    # ---- the citizen ----
    award_ids, void_ids = settle.citizen_settlement(action, answers, corrections)
    awarded_total = 0

    def _settle_citizen():
        nonlocal awarded_total
        pending = repo.list_points(citizen_id, status=points.PENDING)
        awarded_total = settle.points_awarded_total(pending, award_ids)
        updates = points.settle_rows(pending, award_ref_ids=award_ids, void_ref_ids=void_ids)
        return repo.settle_points(updates) if updates else 0

    _best_effort("citizen_points", _settle_citizen, observation_id=obs_id)
    _best_effort(
        "citizen_receipt",
        lambda: repo.insert_receipt(settle.receipt_for(action, awarded_total, obs_id, citizen_id)),
        observation_id=obs_id,
    )
    if action != settle.REJECT:
        # Same bonus, same rules as the crowd path: a rejected report earns nothing.
        _best_effort("adopted_bonus", lambda: adopted_bonus.award_if_due(repo, obs, cfg), observation_id=obs_id)

    # ---- the voters ----
    votes_by_answer = {
        a["id"]: repo.list_votes_for_answer(a["id"]) for a in answers if a.get("id")
    }
    outcomes = settle.vote_outcomes(answers, votes_by_answer, cfg)
    if not outcomes:
        return

    voter_by_vote = {v["id"]: v["voter_id"] for votes in votes_by_answer.values() for v in votes if v.get("id")}
    for vote_id, correct in outcomes.items():
        # The expert overrides any consensus already recorded on the vote.
        _best_effort(
            "vote_correct",
            lambda vid=vote_id, c=correct: repo.update_vote(vid, {"correct": c}),
            vote_id=vote_id,
        )

    rows = points.vote_consensus_rows({k: v for k, v in outcomes.items() if v}, voter_by_vote, cfg)
    if rows:
        existing = set()
        for row in rows:
            existing |= {points.dedupe_key(p) for p in repo.list_points(row["user_id"])}
        _best_effort(
            "vote_points",
            lambda: repo.insert_points(points.filter_new(rows, existing)),
            observation_id=obs_id,
        )

    caught = settle.caught_error_voters(answers, votes_by_answer, cfg)
    for voter_id in {voter_by_vote[v] for v in outcomes if v in voter_by_vote}:
        _best_effort(
            "vote_receipt",
            lambda vid=voter_id: repo.insert_receipt(settle.vote_receipt(vid, obs_id, vid in caught)),
            voter_id=voter_id,
        )

    # ---- caught_one ----
    for voter_id in caught:
        unlocked = {b["badge_id"] for b in repo.list_user_badges(voter_id)}
        new_badges = badges_svc.evaluate({"caught_errors": 1}, unlocked)
        for badge in new_badges:
            _best_effort("badge", lambda vid=voter_id, b=badge: repo.insert_user_badge(vid, b["id"]), voter_id=voter_id)
            _best_effort(
                "badge_receipt",
                lambda vid=voter_id, b=badge: repo.insert_receipt(
                    {"user_id": vid, "kind": "badge", "message": f"Badge unlocked: {b['label']}", "ref_id": obs_id}
                ),
                voter_id=voter_id,
            )


@router.post("/{obs_id}/gold", response_model=MakeGoldOut, status_code=201)
def make_gold(
    obs_id: str,
    body: MakeGoldIn,
    expert: CurrentUser = Depends(require_role("expert", "admin")),
    repo: RepoProtocol = Depends(get_repo),
):
    """Promote a reviewed answer's photo into a practice item.

    Only an expert-scored answer qualifies: a gold item's whole value is that its answer is
    known, so promoting a guess would quietly corrupt every skill measurement built on it.
    """
    obs = repo.get_observation(obs_id)
    if not obs:
        raise not_found("Observation")
    answer = repo.get_answer(obs_id, body.indicator_id)
    if not answer:
        raise not_found("Answer")
    if not answer.get("photo_path"):
        raise AppError(422, "NO_PHOTO", "This answer has no photo to promote")

    expert_score = answer.get("expert_score")
    if expert_score is None:
        expert_score = truth_score(answer) if obs["status"] == "verified" else None
    if expert_score is None:
        raise AppError(
            409,
            "NOT_EXPERT_SCORED",
            "Approve or correct this observation first, so the photo has a known expert answer",
        )

    existing = next(
        (g for g in repo.list_gold_items(active_only=False) if g.get("source_answer_id") == answer["id"]),
        None,
    )
    if existing:
        raise AppError(409, "ALREADY_GOLD", "This photo is already a practice item")

    gold = repo.insert_gold_item(
        {
            "indicator_id": body.indicator_id,
            "image_path": f"storage:{answer['photo_path']}",
            "expert_score": expert_score,
            "explanation": body.explanation,
            "source": "expert",
            "source_answer_id": answer["id"],
            "active": True,
        }
    )
    log_event("gold_promoted", observation_id=obs_id, indicator_id=body.indicator_id, expert_id=expert.id)
    return MakeGoldOut(
        id=gold["id"],
        indicator_id=gold["indicator_id"],
        expert_score=gold["expert_score"],
        explanation=gold["explanation"],
    )
