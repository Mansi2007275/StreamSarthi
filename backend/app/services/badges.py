"""Badges: rule-based, config-driven (app/config/badges.json). No DB, no FastAPI.

The rules reward **variety and good science**, not grinding: different indicators,
different sites, a monsoon visit, catching somebody else's mistake. There is deliberately
no "most submissions" badge.

`stats` is assembled by the caller (Phase 5's /me/progress) and holds:
    onboarded, verified_indicators, verified_sites, gold_matches,
    verified_check_months, caught_errors, adopted_streak
"""

import json
from functools import lru_cache
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "badges.json"


def _onboarded(rule, stats):
    return bool(stats.get("onboarded"))


def _distinct_verified_indicators(rule, stats):
    return len(set(stats.get("verified_indicators") or ())) >= rule["min"]


def _distinct_verified_sites(rule, stats):
    return len(set(stats.get("verified_sites") or ())) >= rule["min"]


def _gold_matches(rule, stats):
    return (stats.get("gold_matches") or 0) >= rule["min"]


def _verified_check_in_months(rule, stats):
    return bool(set(stats.get("verified_check_months") or ()) & set(rule["months"]))


def _caught_errors(rule, stats):
    return (stats.get("caught_errors") or 0) >= rule["min"]


def _adopted_streak(rule, stats):
    return (stats.get("adopted_streak") or 0) >= rule["min"]


RULES = {
    "onboarded": _onboarded,
    "distinct_verified_indicators": _distinct_verified_indicators,
    "distinct_verified_sites": _distinct_verified_sites,
    "gold_matches": _gold_matches,
    "verified_check_in_months": _verified_check_in_months,
    "caught_errors": _caught_errors,
    "adopted_streak": _adopted_streak,
}

_REQUIRED_FIELDS = ("id", "label", "description", "icon", "rule")


def validate_config(badges: list[dict]) -> None:
    seen = set()
    for badge in badges:
        for field in _REQUIRED_FIELDS:
            if not badge.get(field):
                raise ValueError(f"badges.json: badge {badge.get('id')!r} is missing {field!r}")
        if badge["id"] in seen:
            raise ValueError(f"badges.json: duplicate badge id {badge['id']!r}")
        seen.add(badge["id"])
        rule_type = badge["rule"].get("type")
        if rule_type not in RULES:
            raise ValueError(f"badges.json: badge {badge['id']!r} has unknown rule type {rule_type!r}")


@lru_cache
def load_badges() -> list[dict]:
    badges = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    validate_config(badges)
    return badges


def evaluate(stats: dict, unlocked: set[str] | None = None, badges: list[dict] | None = None) -> list[dict]:
    """Badges newly earned by these stats. Already-unlocked ones are never returned again,
    so the caller can turn each result straight into one celebration and one receipt."""
    unlocked = unlocked or set()
    out = []
    for badge in badges if badges is not None else load_badges():
        if badge["id"] in unlocked:
            continue
        if RULES[badge["rule"]["type"]](badge["rule"], stats):
            out.append(badge)
    return out


def with_status(unlocked: set[str], badges: list[dict] | None = None) -> list[dict]:
    """Every badge plus whether it is earned - locked ones stay visible, with the
    description telling the player how to get there."""
    return [
        {
            "id": b["id"],
            "label": b["label"],
            "description": b["description"],
            "icon": b["icon"],
            "unlocked": b["id"] in unlocked,
        }
        for b in (badges if badges is not None else load_badges())
    ]
