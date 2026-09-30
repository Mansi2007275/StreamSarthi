"""A citizen's micro-lessons: what an expert corrected, and why. Logged-in users only."""

from fastapi import APIRouter, Depends, Query

from app.core.auth import CurrentUser, get_current_user
from app.core.errors import not_found
from app.models.schemas import LessonOut, LessonsPage
from app.services.db import RepoProtocol, get_repo
from app.services.indicators import get_indicator

router = APIRouter(prefix="/api/v1/lessons", tags=["lessons"])


def _score_label(score: int | None, ind) -> str | None:
    if score is None or ind is None:
        return None
    return f"{score} · {ind.scale_labels[score - ind.scale[0]]}"


def _lesson_out(row: dict) -> LessonOut:
    ind = get_indicator(row["indicator_id"])
    return LessonOut(
        id=row["id"],
        observation_id=row["observation_id"],
        indicator_id=row["indicator_id"],
        indicator_label=ind.label if ind else row["indicator_id"],
        your_score=row.get("your_score"),
        your_label=_score_label(row.get("your_score"), ind),
        expert_score=row["expert_score"],
        expert_label=_score_label(row["expert_score"], ind),
        why=row["why"],
        tip=ind.help.get("en", "") if ind else "",
        created_at=row.get("created_at"),
        seen=bool(row.get("seen")),
    )


@router.get("", response_model=LessonsPage)
def my_lessons(
    unseen: bool = Query(False),
    limit: int = Query(5, ge=1, le=50),
    user: CurrentUser = Depends(get_current_user),
    repo: RepoProtocol = Depends(get_repo),
):
    rows = repo.list_lessons(user.id, unseen, limit)
    return LessonsPage(items=[_lesson_out(r) for r in rows], unseen_count=repo.count_unseen_lessons(user.id))


@router.post("/{lesson_id}/seen", response_model=LessonOut)
def mark_seen(
    lesson_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: RepoProtocol = Depends(get_repo),
):
    lesson = repo.get_lesson(lesson_id)
    if not lesson or lesson["user_id"] != user.id:
        raise not_found("Lesson")
    return _lesson_out(repo.mark_lesson_seen(lesson_id))
