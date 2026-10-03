"""The Living River: a stream that heals as the player's confirmed work adds up.

Pure functions: no DB, no FastAPI. Stages and thresholds live in app/config/river.json.

It is driven only by **verified** work - checks somebody else confirmed, practice photos
matched against a known expert answer, and errors the player helped catch. Submitting more
never moves it. That is the whole point of the caption: a river you could fill up by posting
would be a progress bar, not a reward for being right.

Stages are cumulative. Reaching the fish stage means the litter is gone and the water is
clear too, so a river never loses something it has already earned.
"""

import json
from functools import lru_cache
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "river.json"

RIVER_METRICS = ("verified_checks", "gold_matches", "caught_errors")


def validate_config(cfg: dict) -> None:
    stages = cfg.get("stages") or []
    if len(stages) < 2:
        raise ValueError("river.json: needs at least a starting stage and one to reach")
    if not cfg.get("caption"):
        raise ValueError("river.json: missing caption")

    seen: set[str] = set()
    previous: dict[str, int] = {}
    for stage in stages:
        for field in ("id", "label"):
            if not stage.get(field):
                raise ValueError(f"river.json: stage {stage.get('id')!r} is missing {field!r}")
        if stage["id"] in seen:
            raise ValueError(f"river.json: duplicate stage id {stage['id']!r}")
        seen.add(stage["id"])

        requires = stage.get("requires") or {}
        for metric, value in requires.items():
            if metric not in RIVER_METRICS:
                raise ValueError(f"river.json: stage {stage['id']!r} requires unknown metric {metric!r}")
            if value < previous.get(metric, 0):
                # Otherwise a later stage could unlock before an earlier one and the river
                # would appear to go backwards.
                raise ValueError(f"river.json: stage {stage['id']!r} lowers {metric!r}; stages must not go backwards")
            previous[metric] = value

    if (stages[0].get("requires") or {}):
        raise ValueError("river.json: the first stage must need nothing, so every player has a river")


@lru_cache
def load_river_config() -> dict:
    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    validate_config(cfg)
    return cfg


def _met(requires: dict, stats: dict) -> bool:
    return all(int(stats.get(metric) or 0) >= target for metric, target in requires.items())


def stage_index(stats: dict, cfg: dict | None = None) -> int:
    """The highest stage whose requirements are all met.

    Walks from the top down and stops at the first stage that qualifies, so a player who
    jumps several thresholds at once lands on the right stage rather than the next one.
    """
    cfg = cfg or load_river_config()
    stages = cfg["stages"]
    for i in range(len(stages) - 1, -1, -1):
        if _met(stages[i].get("requires") or {}, stats):
            return i
    return 0


def _next_hint(stats: dict, cfg: dict, index: int) -> tuple[str | None, str | None]:
    """(hint, next stage label). The hint names the single requirement furthest from done,
    because telling somebody three numbers at once tells them nothing."""
    stages = cfg["stages"]
    if index >= len(stages) - 1:
        return None, None

    nxt = stages[index + 1]
    requires = nxt.get("requires") or {}
    shortfalls = [
        (target - int(stats.get(metric) or 0), metric, target)
        for metric, target in requires.items()
        if int(stats.get(metric) or 0) < target
    ]
    if not shortfalls:
        return f"{nxt['label']} next.", nxt["label"]

    _, metric, target = max(shortfalls)
    what = cfg["stage_verbs"].get((nxt.get("shows") or [None])[0], nxt["label"].lower())
    # Singular and plural both come from config: guessing English plurals in code gives you
    # "1 gold matche".
    forms = cfg["metric_labels"].get(metric) or {}
    unit = forms.get("one" if target == 1 else "many") or metric.replace("_", " ")
    return f"Next: {what} at {target} {unit}.", nxt["label"]


def river_state(stats: dict, cfg: dict | None = None) -> dict:
    """Everything the Home hero needs in one object."""
    cfg = cfg or load_river_config()
    stages = cfg["stages"]
    index = stage_index(stats, cfg)

    # Cumulative: the river keeps what earlier stages brought.
    shows: list[str] = []
    for stage in stages[: index + 1]:
        for item in stage.get("shows") or []:
            if item not in shows:
                shows.append(item)

    hint, next_label = _next_hint(stats, cfg, index)
    return {
        "stage_index": index,
        "stage_id": stages[index]["id"],
        "stage_label": stages[index]["label"],
        "total_stages": len(stages),
        "shows": shows,
        "caption": cfg["caption"],
        "next_hint": hint,
        "next_stage_label": next_label,
        "metrics": {metric: int(stats.get(metric) or 0) for metric in RIVER_METRICS},
    }
