"""One Health: what an observation means for ecosystem, animals and people.

Deterministic and config-driven (app/config/one_health.json) - never an LLM,
so the same input always gives the same text. Pure functions: no DB, no FastAPI.
"""

import json
from functools import lru_cache
from pathlib import Path

from app.models.schemas import Indicator
from app.services.scoring import truth_score

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "one_health.json"

_REQUIRED_LEVEL_FIELDS = ("level", "max_severity", "color", "ecosystem", "animals", "people")


def _text(value: str | dict) -> str:
    """Text fields may be a plain string, or an {en, hi, ...} object for future translation."""
    if isinstance(value, dict):
        return value.get("en", "")
    return value


def validate_config(cfg: dict) -> None:
    levels = cfg.get("levels") or []
    if not levels:
        raise ValueError("one_health.json: levels must not be empty")
    thresholds = [lv.get("max_severity") for lv in levels]
    if thresholds != sorted(thresholds):
        raise ValueError("one_health.json: levels must be sorted by max_severity")
    if levels[-1].get("max_severity") != 1.0:
        raise ValueError("one_health.json: the last level's max_severity must be 1.0")
    for lv in levels:
        for field in _REQUIRED_LEVEL_FIELDS:
            if lv.get(field) in (None, ""):
                raise ValueError(f"one_health.json: level {lv.get('level')!r} is missing {field!r}")
    if not cfg.get("disclaimer"):
        raise ValueError("one_health.json: missing disclaimer")


@lru_cache
def load_config() -> dict:
    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    validate_config(cfg)
    return cfg


def severity(score: int, indicator: Indicator) -> float:
    lo, hi = indicator.scale
    frac = (score - lo) / (hi - lo)
    return frac if indicator.higher_is_worse else 1 - frac


def compute_one_health(observation: dict, answers: list[dict], indicators: list[Indicator]) -> dict | None:
    if observation.get("status") in ("draft", "rejected"):
        return None

    cfg = load_config()
    indicators_by_id = {i.id: i for i in indicators}
    required_ids = {i.id for i in indicators if i.required}
    if not required_ids:
        return None

    # (indicator_id, severity, was_expert_truth)
    scored: list[tuple[str, float, bool]] = []
    for a in answers:
        ind = indicators_by_id.get(a["indicator_id"])
        if not ind:
            continue
        score = truth_score(a)
        if score is None:
            continue
        scored.append((a["indicator_id"], severity(score, ind), a.get("expert_score") is not None))

    answered_required = {ind_id for ind_id, _, _ in scored} & required_ids
    if len(answered_required) / len(required_ids) < cfg["min_answered_ratio"]:
        return None

    avg = sum(s for _, s, _ in scored) / len(scored)
    level = next(lv for lv in cfg["levels"] if avg <= lv["max_severity"])

    drivers = [
        {"indicator_id": ind_id, "label": indicators_by_id[ind_id].label, "severity": round(s, 2)}
        for ind_id, s, _ in sorted(scored, key=lambda t: t[1], reverse=True)
        if s >= 0.5
    ][:2]

    return {
        "level": level["level"],
        "color": level["color"],
        "severity": round(avg, 2),
        "ecosystem": _text(level["ecosystem"]),
        "animals": _text(level["animals"]),
        "people": _text(level["people"]),
        "disclaimer": _text(cfg["disclaimer"]),
        "drivers": drivers,
        "based_on": "expert" if any(was_expert for _, _, was_expert in scored) else "citizen",
    }
