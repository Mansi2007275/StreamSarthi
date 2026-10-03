"""My Stream: adopt a stretch of water, and watch what happens to it over months.

Adoption is what turns scattered observations into a trend, so these responses are built
around time rather than around any one report.

**Everything here is aggregated.** A site's timeline mixes in checks by other Guardians,
because that is what the site's history is - but no response carries a user id, a name, an
email or a photo. Coordinates are rounded to roughly 100 m: enough to find the stream, not
enough to point at whoever stood there.
"""

import logging

from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user
from app.core.errors import AppError, not_found
from app.core.logging import log_event
from app.models.schemas import (
    AdoptedSiteOut,
    AdoptionOut,
    MyStreamOut,
    SiteTimelineOut,
    TimelineEntryOut,
)
from app.services import adoption, site_history
from app.services.db import RepoProtocol, get_repo
from app.services.game_config import load_game_config

logger = logging.getLogger("streamsaathi")

router = APIRouter(prefix="/api/v1", tags=["my-stream"])

COORD_PRECISION = 3  # ~100 m


def _round(value: float | None) -> float | None:
    return round(value, COORD_PRECISION) if value is not None else None


def _my_check_dates(observations: list[dict], user_id: str) -> list[str]:
    return [o["submitted_at"] for o in observations if o["user_id"] == user_id and o.get("submitted_at")]


def _site_summary(repo: RepoProtocol, user_id: str, row: dict, cfg: dict, today) -> AdoptedSiteOut:
    site = row.get("site") or {}
    site_id = row["site_id"]
    observations = repo.list_site_observations(site_id)

    mine = _my_check_dates(observations, user_id)
    last_check = max(mine) if mine else None
    this_month = adoption.month_key_of(today)
    others = sum(
        1
        for o in observations
        if o["user_id"] != user_id and adoption.month_key_of(o.get("submitted_at")) == this_month
    )
    latest = next((o for o in observations if o.get("one_health")), None)

    return AdoptedSiteOut(
        site_id=site_id,
        name=site.get("name"),
        lat=_round(site.get("lat")),
        lng=_round(site.get("lng")),
        adopted_at=row.get("adopted_at"),
        last_check=adoption.as_date(last_check).isoformat() if last_check else None,
        next_check_due=adoption.next_check_due(last_check, cfg),
        due_status=adoption.due_status(last_check, today, cfg),
        streak_months=adoption.streak_months(mine, today),
        checks=len(mine),
        one_health_level=(latest or {}).get("one_health", {}).get("level") if latest else None,
        others_this_month=others,
    )


@router.get("/my-stream", response_model=MyStreamOut)
def my_stream(
    user: CurrentUser = Depends(get_current_user),
    repo: RepoProtocol = Depends(get_repo),
):
    cfg = load_game_config()
    repo.ensure_profile(user.id, user.email)
    today = adoption.today_utc()
    rows = repo.list_adoptions(user.id)
    return MyStreamOut(
        sites=[_site_summary(repo, user.id, row, cfg, today) for row in rows],
        max_sites=cfg["max_adopted_sites"],
        can_adopt_more=adoption.can_adopt(len(rows), cfg),
    )


@router.post("/sites/{site_id}/adopt", response_model=AdoptionOut)
def adopt(
    site_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: RepoProtocol = Depends(get_repo),
):
    cfg = load_game_config()
    repo.ensure_profile(user.id, user.email)
    site = repo.get_site(site_id)
    if not site:
        raise not_found("Site")

    active = repo.list_adoptions(user.id)
    existing = repo.get_adoption(user.id, site_id)
    if existing is None:
        if not adoption.can_adopt(len(active), cfg):
            raise AppError(
                409,
                "ADOPTION_LIMIT",
                f"You can look after {cfg['max_adopted_sites']} streams at a time. "
                "Release one before adopting another.",
            )
        repo.insert_adoption(user.id, site_id)
        active = repo.list_adoptions(user.id)
        log_event("site_adopted", site_id=site_id, user_id=user.id)

    return AdoptionOut(
        site_id=site_id,
        name=site.get("name"),
        adopted=True,
        adopted_count=len(active),
        max_sites=cfg["max_adopted_sites"],
    )


@router.post("/sites/{site_id}/release", response_model=AdoptionOut)
def release(
    site_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: RepoProtocol = Depends(get_repo),
):
    cfg = load_game_config()
    site = repo.get_site(site_id)
    if not site:
        raise not_found("Site")

    existing = repo.get_adoption(user.id, site_id)
    if existing:
        # Released, not deleted: the history of who looked after what is worth keeping, and
        # re-adopting later should not look like it never lapsed.
        repo.release_adoption(existing["id"])
        log_event("site_released", site_id=site_id, user_id=user.id)

    active = repo.list_adoptions(user.id)
    return AdoptionOut(
        site_id=site_id,
        name=site.get("name"),
        adopted=False,
        adopted_count=len(active),
        max_sites=cfg["max_adopted_sites"],
    )


@router.get("/sites/{site_id}/timeline", response_model=SiteTimelineOut)
def timeline(
    site_id: str,
    user: CurrentUser = Depends(get_current_user),
    repo: RepoProtocol = Depends(get_repo),
):
    """One entry per month this site was checked, newest first.

    Months are the unit because that is the rhythm adoption asks for. Within a month the
    most recent check wins for the One Health reading, and a month counts as verified if any
    check in it was.
    """
    cfg = load_game_config()
    site = repo.get_site(site_id)
    if not site:
        raise not_found("Site")

    today = adoption.today_utc()
    observations = repo.list_site_observations(site_id)
    entries = [TimelineEntryOut(**e) for e in site_history.monthly_entries(observations, user_id=user.id)]

    mine = _my_check_dates(observations, user.id)
    return SiteTimelineOut(
        site_id=site_id,
        name=site.get("name"),
        lat=_round(site.get("lat")),
        lng=_round(site.get("lng")),
        adopted=repo.get_adoption(user.id, site_id) is not None,
        streak_months=adoption.streak_months(mine, today),
        due_status=adoption.due_status(max(mine) if mine else None, today, cfg),
        entries=entries,
    )
