"""A site's history, aggregated by month. Pure functions: no DB, no FastAPI.

Shared by the owner-facing timeline (routers/my_stream.py) and the public station page
(routers/stations.py), so both tell the same story about the same water. The public caller
passes `include_mine=False` and gets a structure with no per-person counts in it at all.

Months are the unit because adoption asks for one check a month. Within a month the most
recent check wins the One Health reading, and the month counts as verified if any check in
it was - a single confirmed report is enough to trust the month.
"""

from collections import defaultdict

from app.services import adoption

VERIFIED_STATUSES = ("verified", "corrected")


def is_verified(obs: dict) -> bool:
    return bool(obs.get("crowd_verified")) or obs.get("status") in VERIFIED_STATUSES


def monthly_entries(observations: list[dict], user_id: str | None = None) -> list[dict]:
    """One entry per month a site was checked, newest first.

    `user_id` only ever adds a `mine` count; it never filters, because a site's history is
    everybody's checks, not just yours.
    """
    by_month: dict[str, list[dict]] = defaultdict(list)
    for obs in observations:
        month = adoption.month_key_of(obs.get("submitted_at"))
        if month:
            by_month[month].append(obs)

    entries = []
    for month in sorted(by_month, reverse=True):
        rows = sorted(by_month[month], key=lambda o: o.get("submitted_at") or "", reverse=True)
        newest = rows[0]
        health = newest.get("one_health") or {}
        stamp = adoption.as_date(newest.get("submitted_at"))
        entries.append(
            {
                "month": month,
                "date": stamp.isoformat() if stamp else None,
                "one_health_level": health.get("level"),
                "worst_indicators": [d["label"] for d in (health.get("drivers") or [])][:3],
                "verified": any(is_verified(o) for o in rows),
                "checks": len(rows),
                "mine": sum(1 for o in rows if user_id and o.get("user_id") == user_id),
            }
        )
    return entries


def recent_levels(entries: list[dict], months: int = 6) -> list[dict]:
    """The last N months as dots for the poster page, oldest first so it reads left to right."""
    return [{"month": e["month"], "level": e["one_health_level"]} for e in entries[:months]][::-1]


def headline(entries: list[dict], months: int = 2) -> str | None:
    """One plain sentence about the recent state, for somebody who has never used the app.

    Built from the stored One Health drivers, never from a model, so the same data always
    produces the same sentence and nobody has to trust a generated claim on a public sign.
    """
    recent = [e for e in entries[:months] if e["one_health_level"]]
    if not recent:
        return None

    drivers: list[str] = []
    for entry in recent:
        for label in entry["worst_indicators"]:
            if label.lower() not in [d.lower() for d in drivers]:
                drivers.append(label)
    level = recent[0]["one_health_level"]

    if not drivers:
        return f"Recent checks rated this stretch {level}."
    listed = drivers[0].lower() if len(drivers) == 1 else " and ".join([d.lower() for d in drivers[:2]])
    when = "the last check" if len(recent) == 1 else f"the last {len(recent)} checks"
    return f"{listed.capitalize()} stood out in {when}, rating this stretch {level}."


def last_check_date(observations: list[dict]) -> str | None:
    stamps = [o["submitted_at"] for o in observations if o.get("submitted_at")]
    if not stamps:
        return None
    latest = adoption.as_date(max(stamps))
    return latest.isoformat() if latest else None


def total_checks(observations: list[dict]) -> int:
    return sum(1 for o in observations if o.get("submitted_at"))
