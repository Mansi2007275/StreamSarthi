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
from app.models.schemas import ReviewAction, ReviewDetail, ReviewQueuePage
from app.routers.observations import _observation_out
from app.services import audit
from app.services.db import RepoProtocol, get_repo, now_iso
from app.services.indicators import get_indicator, load_indicators
from app.services.lessons import build_lessons
from app.services.one_health import compute_one_health
from app.services.scoring import truth_score
from app.services.storage import StorageProtocol, get_storage
from app.services.trust import updated_accuracy

logger = logging.getLogger("streamsaathi")

router = APIRouter(prefix="/api/v1/review", tags=["review"])

_NEW_STATUS = {"approve": "verified", "correct": "corrected", "reject": "rejected"}
_EVENT = {"approve": "expert_approved", "correct": "expert_corrected", "reject": "expert_rejected"}


def _review_detail(
    obs: dict, answers: list[dict], storage: StorageProtocol, repo: RepoProtocol, audit_ok: bool = True
) -> ReviewDetail:
    base = _observation_out(obs, answers, storage)
    citizen = repo.get_profile(obs["user_id"]) or {}
    return ReviewDetail(
        **base.model_dump(),
        citizen_display_name=citizen.get("display_name"),
        citizen_observer_accuracy=citizen.get("observer_accuracy"),
        audit_ok=audit_ok,
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

    log_event("review_action", observation_id=obs_id, action=body.action, expert_id=expert.id)

    return _review_detail(obs, answers, storage, repo, audit_ok=audit_ok)
