"""Stream Stations: the one page in this app that needs no login.

A poster at the water's edge is read by people who have never heard of StreamSaathi, so this
endpoint has to be safe to hand to anybody: aggregates only, a rounded location, and not one
field that could identify who stood there. It is also the only unauthenticated route, which
makes it the only one an anonymous caller can hammer - hence the per-IP rate limit.
"""

import logging
from functools import lru_cache

from fastapi import APIRouter, Depends, Request

from app.core.errors import not_found
from app.core.ratelimit import RateLimiter
from app.models.schemas import StationDotOut, StationOut
from app.services import adoption, site_history
from app.services.db import RepoProtocol, get_repo
from app.services.game_config import load_game_config

logger = logging.getLogger("streamsaathi")

router = APIRouter(prefix="/api/v1/stations", tags=["stations"])

COORD_PRECISION = 3  # ~100 m: enough to find the stream, not to point at a person
RECENT_MONTHS = 6


@lru_cache
def get_station_limiter() -> RateLimiter:
    cfg = load_game_config()
    return RateLimiter(
        cfg["stations"]["public_rate_limit_per_minute"],
        60,
        "Too many requests. Wait a minute and try again.",
    )


def _client_key(request: Request) -> str:
    """No login here, so the limiter keys on the caller's address."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/{site_id}", response_model=StationOut)
def station(
    site_id: str,
    request: Request,
    repo: RepoProtocol = Depends(get_repo),
    limiter: RateLimiter = Depends(get_station_limiter),
):
    limiter.check(_client_key(request))
    cfg = load_game_config()

    site = repo.get_site(site_id)
    if not site:
        raise not_found("Station")

    observations = repo.list_site_observations(site_id)
    entries = site_history.monthly_entries(observations)
    last_check = site_history.last_check_date(observations)

    days_since = None
    if last_check:
        parsed = adoption.as_date(last_check)
        if parsed:
            days_since = (adoption.today_utc() - parsed).days

    return StationOut(
        site_id=site_id,
        station_number=site.get("station_number"),
        name=site.get("name"),
        lat=round(site["lat"], COORD_PRECISION) if site.get("lat") is not None else None,
        lng=round(site["lng"], COORD_PRECISION) if site.get("lng") is not None else None,
        last_check=last_check,
        days_since_check=days_since,
        total_checks=site_history.total_checks(observations),
        # Reuses the same interval adoption reminders use, so "waiting" and "due" never disagree.
        waiting_for_check=adoption.due_status(last_check, cfg=cfg) == adoption.DUE,
        one_health_level=entries[0]["one_health_level"] if entries else None,
        headline=site_history.headline(entries, cfg["stations"]["headline_months"]),
        recent_months=[StationDotOut(**d) for d in site_history.recent_levels(entries, RECENT_MONTHS)],
    )
