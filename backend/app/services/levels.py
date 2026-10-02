"""Levels: Beginner -> Sharp Eye -> Calibrated Observer -> Stream Guardian.

Pure functions: no DB, no FastAPI. Thresholds live in game.json.

Levels grow with **accuracy and verified work, not volume**, which is why every
threshold is about gold accuracy or confirmed checks and none of them count submissions.

`stats` carries `{"gold_votes", "gold_accuracy", "verified_checks"}`. A player with no
gold votes yet has `gold_accuracy = None` ("unknown"), which must not read as 0.0.
"""

from app.services.game_config import load_game_config

_REQUIREMENTS = (
    ("min_gold_votes", "gold_votes", "Practice photos checked"),
    ("min_gold_accuracy", "gold_accuracy", "Accuracy on practice photos"),
    ("min_verified_checks", "verified_checks", "Verified stream checks"),
)


def _meets(level: dict, stats: dict) -> bool:
    for threshold_key, stat_key, _ in _REQUIREMENTS:
        target = level[threshold_key]
        if target in (0, 0.0):
            continue  # nothing required, so "unknown" still passes
        current = stats.get(stat_key)
        if current is None or current < target:
            return False
    return True


def level_for(stats: dict, cfg: dict | None = None) -> dict:
    """The highest level whose thresholds are all met. Levels are ordered easiest first,
    and game_config validates that ordering, so the first level always qualifies."""
    cfg = cfg or load_game_config()
    levels = cfg["levels"]
    current = levels[0]
    for level in levels:
        if _meets(level, stats):
            current = level
    return {"id": current["id"], "label": current["label"], "index": levels.index(current)}


def next_level_progress(stats: dict, cfg: dict | None = None) -> dict | None:
    """What is left to reach the next level, requirement by requirement.

    None at the top level. `percent` is the mean of the per-requirement fractions, so the
    ring on the profile moves when any one of them moves, not only the slowest.
    """
    cfg = cfg or load_game_config()
    levels = cfg["levels"]
    index = level_for(stats, cfg)["index"]
    if index >= len(levels) - 1:
        return None

    nxt = levels[index + 1]
    requirements, fractions = [], []
    for threshold_key, stat_key, label in _REQUIREMENTS:
        target = nxt[threshold_key]
        if target in (0, 0.0):
            continue
        current = stats.get(stat_key) or 0
        fraction = min(1.0, current / target)
        fractions.append(fraction)
        requirements.append(
            {
                "key": stat_key,
                "label": label,
                "current": round(current, 4),
                "target": target,
                "met": current >= target,
            }
        )

    return {
        "id": nxt["id"],
        "label": nxt["label"],
        "requirements": requirements,
        "percent": round(100 * sum(fractions) / len(fractions)) if fractions else 100,
    }
