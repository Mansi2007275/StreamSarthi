"""Home and Profile: what a volunteer sees when they open the app.

One call each, on purpose. Home is the first screen on a phone, often on a slow connection,
and five round-trips there would be five chances to show a half-built page.

Nothing here invents a measurement. Levels come from services/levels, standings from
game.skill_map, leanings from blind_spots, badge rules from badges, quest progress from
quests, and the shared stats dict from progress.player_stats.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from app.core.auth import CurrentUser, get_current_user
from app.core.errors import not_found
from app.models.schemas import (
    BadgeOut,
    BlindSpotOut,
    HomeOut,
    LessonOut,
    LevelOut,
    NextLevelOut,
    PointsOut,
    ProfileOut,
    ReceiptOut,
    ReceiptsPage,
    SkillRowOut,
    WeeklyAccuracyOut,
)
from app.routers.lessons import _lesson_out
from app.services import badges as badges_svc
from app.services import blind_spots, points, progress, quests
from app.services.db import RepoProtocol, get_repo
from app.services.game import skill_map
from app.services.game_config import load_game_config
from app.services.indicators import load_indicators
from app.services.levels import level_for, next_level_progress

logger = logging.getLogger("streamsaathi")

router = APIRouter(prefix="/api/v1", tags=["home"])

HOME_RECEIPTS = 3
# blind_spots calls a consistent lean "weak"; the UI says "focus", which is kinder and
# tells the player what to do about it.
_STANDING_LABEL = {"weak": "focus"}


def _receipt_out(row: dict) -> ReceiptOut:
    return ReceiptOut(
        id=str(row["id"]),
        kind=row["kind"],
        message=row["message"],
        ref_id=row.get("ref_id"),
        seen=bool(row.get("seen")),
        created_at=row.get("created_at"),
    )


def _points_out(repo: RepoProtocol, user_id: str) -> PointsOut:
    totals = points.totals(repo.list_points(user_id))
    return PointsOut(awarded=totals["awarded"], pending=totals["pending"])


def _gather(repo: RepoProtocol, user_id: str) -> tuple[dict, list[dict], dict]:
    """(stats, gold votes, profile) - the three things both screens are built from."""
    cfg = load_game_config()
    profile = repo.get_profile(user_id) or {}
    gold_votes = repo.list_gold_votes(user_id)

    observations, _ = repo.list_observations(user_id, 0, 200)
    answers = repo.list_answers_for_user(user_id)
    answers_by_obs: dict[str, list[dict]] = {}
    for answer in answers:
        answers_by_obs.setdefault(answer["observation_id"], []).append(answer)

    # Only the player's own votes are needed, so this reads their votes, not everyone's.
    my_votes = [v for v in repo.list_votes_by_voter(user_id) if v.get("answer_id")]
    votes_by_answer: dict[str, list[dict]] = {}
    for vote in my_votes:
        votes_by_answer.setdefault(vote["answer_id"], []).append(vote)
    judged_answers = [repo.get_answer_by_id(aid) for aid in votes_by_answer]
    caught = progress.caught_error_count(
        [a for a in judged_answers if a], votes_by_answer, user_id, cfg["agree_max_diff"]
    )

    stats = progress.player_stats(gold_votes, observations, answers_by_obs, profile, caught_errors=caught)
    return stats, gold_votes, profile


def _quest_counts(repo: RepoProtocol, user_id: str, now: datetime | None = None) -> dict[str, int]:
    """Counted from rows every time - never a stored counter that can drift."""
    now = now or datetime.now(timezone.utc)
    today = quests.window_start("today", now).isoformat()
    week = quests.window_start("week", now).isoformat()

    votes = repo.list_votes_by_voter(user_id)
    spot_checks = sum(1 for v in votes if (v.get("created_at") or "") >= today)
    submitted = [o for o in repo.list_observations_since(user_id, week) if o.get("submitted_at")]
    return {"spot_check_count": spot_checks, "stream_checks_week": len(submitted)}


def _next_level_out(stats: dict, cfg: dict) -> NextLevelOut | None:
    nxt = next_level_progress(stats, cfg)
    if nxt is None:
        return None
    missing = [r for r in nxt["requirements"] if not r["met"]]
    if missing:
        parts = [f"{r['label'].lower()} {round(r['current'], 2)} of {r['target']}" for r in missing]
        summary = f"To reach {nxt['label']}: " + ", ".join(parts) + "."
    else:
        summary = f"You have met everything for {nxt['label']}."
    return NextLevelOut(**nxt, summary=summary)


@router.get("/home", response_model=HomeOut)
def home(
    user: CurrentUser = Depends(get_current_user),
    repo: RepoProtocol = Depends(get_repo),
):
    cfg = load_game_config()
    repo.ensure_profile(user.id, user.email)
    stats, _, profile = _gather(repo, user.id)

    if not stats["onboarded"]:
        # A brand new player gets one instruction and nothing to scroll past.
        return HomeOut(
            display_name=profile.get("display_name"),
            level=LevelOut(**level_for(stats, cfg)),
            points=_points_out(repo, user.id),
            onboarded=False,
        )

    receipts = repo.list_receipts(user.id, unseen_only=True, limit=HOME_RECEIPTS)
    lesson = next(iter(repo.list_lessons(user.id, True, 1)), None)
    quest = quests.todays_quest(_quest_counts(repo, user.id))

    return HomeOut(
        display_name=profile.get("display_name"),
        level=LevelOut(**level_for(stats, cfg)),
        points=_points_out(repo, user.id),
        onboarded=True,
        receipts=[_receipt_out(r) for r in receipts],
        unseen_receipts=repo.count_receipts(user.id, unseen_only=True),
        lesson=_lesson_out(lesson) if lesson else None,
        quest=quest,
    )


@router.get("/me/profile", response_model=ProfileOut)
def my_profile(
    user: CurrentUser = Depends(get_current_user),
    repo: RepoProtocol = Depends(get_repo),
):
    cfg = load_game_config()
    repo.ensure_profile(user.id, user.email)
    stats, gold_votes, profile = _gather(repo, user.id)
    indicators = load_indicators()

    corrections = [
        {
            "indicator_id": lesson["indicator_id"],
            "user_score": lesson.get("your_score"),
            "expert_score": lesson["expert_score"],
        }
        for lesson in repo.list_lessons(user.id, False, 100)
    ]
    leanings = [
        BlindSpotOut(
            indicator_id=row["indicator_id"],
            label=row["label"],
            n=row["n"],
            mean_signed_error=row["mean_signed_error"],
            direction=row["direction"],
            message=row["message"],
        )
        for row in blind_spots.compute(gold_votes, corrections, indicators, cfg)
        if row["reported"]
    ][:2]

    return ProfileOut(
        display_name=profile.get("display_name"),
        role=profile.get("role", "citizen"),
        level=LevelOut(**level_for(stats, cfg)),
        next_level=_next_level_out(stats, cfg),
        points=_points_out(repo, user.id),
        gold_votes=stats["gold_votes"],
        gold_accuracy=stats["gold_accuracy"],
        verified_checks=stats["verified_checks"],
        accuracy_by_week=[WeeklyAccuracyOut(**w) for w in progress.weekly_accuracy(gold_votes)],
        skill_map=[
            SkillRowOut(**{**row, "standing": _STANDING_LABEL.get(row["standing"], row["standing"])})
            for row in skill_map(gold_votes, indicators, cfg)
        ],
        blind_spots=leanings,
        badges=[
            BadgeOut(**row)
            for row in badges_svc.with_progress(stats, {b["badge_id"] for b in repo.list_user_badges(user.id)})
        ],
    )


@router.get("/receipts", response_model=ReceiptsPage)
def my_receipts(
    unseen: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(get_current_user),
    repo: RepoProtocol = Depends(get_repo),
):
    rows = repo.list_receipts(user.id, unseen_only=unseen, limit=limit, offset=offset)
    return ReceiptsPage(
        items=[_receipt_out(r) for r in rows],
        total=repo.count_receipts(user.id, unseen_only=unseen),
        unseen_count=repo.count_receipts(user.id, unseen_only=True),
        offset=offset,
        limit=limit,
    )


@router.post("/receipts/{receipt_id}/seen", response_model=ReceiptOut)
def mark_seen(
    receipt_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: RepoProtocol = Depends(get_repo),
):
    receipt = repo.get_receipt(receipt_id)
    # 404 rather than 403 when it is somebody else's: don't confirm that the id exists.
    if not receipt or receipt["user_id"] != user.id:
        raise not_found("Receipt")
    return _receipt_out(repo.mark_receipt_seen(receipt_id))


# LessonOut is re-exported for the response model above.
__all__ = ["router", "LessonOut"]
