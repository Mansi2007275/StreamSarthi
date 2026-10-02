"""Adopt-a-Stream: streaks, when a check is due, and when a monthly bonus is owed.

Pure functions: no DB, no FastAPI. Thresholds come from game.json.

The point of adoption is the **same** stretch of water checked again and again. One visit is
a snapshot; twelve monthly visits are a trend somebody can act on. So the streak is what the
UI celebrates, and it is deliberately forgiving about the month you are still in.
"""

from datetime import date, datetime, timedelta, timezone

from app.services.game_config import load_game_config

OK = "ok"
DUE_SOON = "due_soon"
DUE = "due"


def as_date(value: str | date | datetime | None) -> date | None:
    """DB timestamps arrive as ISO strings; tests pass dates. Accept both, return a date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _month_key(value: date) -> tuple[int, int]:
    return value.year, value.month


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def streak_months(check_dates: list[str | date | datetime | None], today: date | None = None) -> int:
    """Consecutive calendar months, ending at the current one, with at least one check.

    The month you are in does not count against you until it is over: on the 2nd of October
    somebody with checks in August and September has a 2-month streak, not a broken one.
    Counting it as broken would punish people for the calendar rather than for their work.
    """
    today = today or today_utc()
    months = {_month_key(d) for d in (as_date(c) for c in check_dates) if d is not None}
    if not months:
        return 0

    cursor = _month_key(today)
    if cursor not in months:
        cursor = _previous_month(*cursor)  # this month is still in progress

    streak = 0
    while cursor in months:
        streak += 1
        cursor = _previous_month(*cursor)
    return streak


def due_status(
    last_check: str | date | datetime | None,
    today: date | None = None,
    cfg: dict | None = None,
) -> str:
    """Whether this site wants a visit: ok, due_soon, or due.

    Never checked counts as due - an adopted site with no data is the most useful visit
    somebody could make.
    """
    cfg = cfg or load_game_config()
    interval = cfg["adopted_check_interval_days"]
    warn = cfg["adopted_due_soon_days"]

    last = as_date(last_check)
    if last is None:
        return DUE
    days = ((today or today_utc()) - last).days
    if days >= interval:
        return DUE
    if days >= interval - warn:
        return DUE_SOON
    return OK


def next_check_due(
    last_check: str | date | datetime | None,
    cfg: dict | None = None,
) -> str | None:
    """ISO date the next check is wanted, or None when one is already overdue."""
    cfg = cfg or load_game_config()
    last = as_date(last_check)
    if last is None:
        return None
    return (last + timedelta(days=cfg["adopted_check_interval_days"])).isoformat()


def can_adopt(active_count: int, cfg: dict | None = None) -> bool:
    """Three sites is the cap, so that adoption means a commitment somebody can keep."""
    cfg = cfg or load_game_config()
    return active_count < cfg["max_adopted_sites"]


def month_key_of(value: str | date | datetime | None) -> str | None:
    """'2026-10', the granularity the monthly bonus is paid at."""
    parsed = as_date(value)
    return f"{parsed.year:04d}-{parsed.month:02d}" if parsed else None


def should_award_bonus(site_id: str | None, month_key: str | None, already_paid: set[tuple[str, str]]) -> bool:
    """Once per adopted site per calendar month, however many checks were verified in it.

    `already_paid` holds (site_id, month) pairs the ledger has paid before. Paying per
    verified check instead would reward doing five checks in one afternoon, which is exactly
    the volume-chasing this design avoids.
    """
    if not site_id or not month_key:
        return False
    return (site_id, month_key) not in already_paid


def streak_for_badge(check_dates_by_site: dict[str, list], today: date | None = None) -> int:
    """The best streak across adopted sites, for the steady_guardian badge."""
    if not check_dates_by_site:
        return 0
    return max(streak_months(dates, today) for dates in check_dates_by_site.values())
