"""Loads app/config/game.json.

Its own module because every game service (game, consensus, points, levels,
badges, blind_spots, proof) needs the same thresholds, and nothing in here
imports another service, so there are no import cycles.

Nothing in the game layer may hard-code a threshold or a reward: read it from here.
"""

import json
from functools import lru_cache
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "game.json"

_REQUIRED_TOP = ("round_size", "gold_every", "agree_max_diff", "disagree_min_diff", "points", "levels")
_REQUIRED_POINTS = (
    "stream_check_per_indicator",
    "gold_match",
    "vote_matches_consensus",
    "adopted_site_monthly_bonus",
)
_LEVEL_THRESHOLDS = ("min_gold_votes", "min_gold_accuracy", "min_verified_checks")


def validate_config(cfg: dict) -> None:
    for key in _REQUIRED_TOP:
        if cfg.get(key) in (None, ""):
            raise ValueError(f"game.json: missing {key!r}")
    for key in _REQUIRED_POINTS:
        if cfg["points"].get(key) is None:
            raise ValueError(f"game.json: missing points.{key!r}")
    if cfg["agree_max_diff"] >= cfg["disagree_min_diff"]:
        raise ValueError("game.json: agree_max_diff must be below disagree_min_diff")

    levels = cfg["levels"]
    if not levels:
        raise ValueError("game.json: levels must not be empty")
    for field in _LEVEL_THRESHOLDS:
        values = [lv.get(field) for lv in levels]
        if any(v is None for v in values):
            raise ValueError(f"game.json: every level needs {field!r}")
        if values != sorted(values):
            raise ValueError(f"game.json: levels must be ordered by {field!r}, easiest first")

    sw = cfg.get("skill_weight") or {}
    if not sw.get("min", 0) <= sw.get("neutral", 1) <= sw.get("max", 1):
        raise ValueError("game.json: skill_weight needs min <= neutral <= max")
    if not 0 < sw.get("neutral_accuracy", 0.5) < 1:
        raise ValueError("game.json: skill_weight.neutral_accuracy must be between 0 and 1")
    if sw.get("prior_strength", 0) <= 0:
        raise ValueError("game.json: skill_weight.prior_strength must be positive")


@lru_cache
def load_game_config() -> dict:
    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    validate_config(cfg)
    return cfg
