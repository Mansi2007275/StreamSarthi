"""Quests: small, repeatable goals read from app/config/quests.json.

Pure functions: no DB, no FastAPI.

Progress is always **computed from data**, never stored as a counter. A stored counter can
drift from reality, and once it has, nobody can tell whether the number or the data is
wrong. Counting rows every time is slower and always right.

Crew quests are declared in the config but inactive until crews exist (Phase 7), so Home
never offers a goal nobody can work toward.
"""

import json
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "quests.json"

PERSONAL = "personal"
CREW = "crew"

# Types this build can actually measure. A crew type stays in the config, listed but never
# offered, until Phase 7 gives it something to count.
SUPPORTED_TYPES = ("spot_check_count", "stream_checks_week")
_KNOWN_TYPES = SUPPORTED_TYPES + ("crew_distinct_sites_month", "crew_recheck_after_event")
_REQUIRED_FIELDS = ("id", "scope", "label", "description", "type", "window")


def validate_config(quests: list[dict]) -> None:
    seen = set()
    for quest in quests:
        for field in _REQUIRED_FIELDS:
            if not quest.get(field):
                raise ValueError(f"quests.json: quest {quest.get('id')!r} is missing {field!r}")
        if quest["id"] in seen:
            raise ValueError(f"quests.json: duplicate quest id {quest['id']!r}")
        seen.add(quest["id"])
        if quest["type"] not in _KNOWN_TYPES:
            raise ValueError(f"quests.json: quest {quest['id']!r} has unknown type {quest['type']!r}")
        if quest["scope"] not in (PERSONAL, CREW):
            raise ValueError(f"quests.json: quest {quest['id']!r} has unknown scope {quest['scope']!r}")
        if quest["scope"] == PERSONAL and not quest.get("target"):
            raise ValueError(f"quests.json: personal quest {quest['id']!r} needs a target")


@lru_cache
def load_quests() -> list[dict]:
    quests = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    validate_config(quests)
    return quests


def window_start(window: str, now: datetime | None = None) -> datetime:
    """When the current counting window opened. Weeks start Monday, months on the 1st."""
    now = now or datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if window == "today":
        return midnight
    if window == "week":
        return midnight - timedelta(days=midnight.weekday())
    if window == "month":
        return midnight.replace(day=1)
    return midnight


def compute(quest: dict, counts: dict[str, int]) -> dict:
    """One quest with live progress. `counts` is keyed by quest type."""
    target = int(quest["target"])
    current = min(int(counts.get(quest["type"], 0)), target)
    return {
        "id": quest["id"],
        "label": quest["label"],
        "description": quest["description"],
        "type": quest["type"],
        "window": quest["window"],
        "target": target,
        "current": current,
        "done": current >= target,
        "percent": round(100 * current / target) if target else 100,
    }


def personal_quests(counts: dict[str, int]) -> list[dict]:
    """Every measurable personal quest, with progress."""
    return [
        compute(q, counts)
        for q in load_quests()
        if q["scope"] == PERSONAL and q["type"] in SUPPORTED_TYPES
    ]


def todays_quest(counts: dict[str, int]) -> dict | None:
    """What Home shows: the first personal quest still worth doing.

    Finished quests are skipped rather than shown ticked, because the card exists to give
    somebody their next action, not to congratulate them. None when everything is done.
    """
    return next((q for q in personal_quests(counts) if not q["done"]), None)
