"""Calibration Mode: 3 practice photos with a known expert answer.

Seeds a new citizen's starting observer_accuracy instead of the 0.5 default,
so the Trust Score's O component is meaningful from day one.
"""

import json
from functools import lru_cache
from pathlib import Path

from app.services.indicators import get_indicator

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "calibration.json"


@lru_cache
def load_items() -> list[dict]:
    items = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    for item in items:
        if not get_indicator(item["indicator_id"]):
            raise ValueError(f"calibration.json: unknown indicator {item['indicator_id']!r}")
    return items


def public_items() -> list[dict]:
    """Strips expert_score/explanation so the client can't cheat via the network tab."""
    return [{"id": i["id"], "image": i["image"], "indicator_id": i["indicator_id"]} for i in load_items()]


def score_item(item_id: str, user_score: int) -> dict | None:
    item = next((i for i in load_items() if i["id"] == item_id), None)
    if item is None:
        return None
    return {
        "expert_score": item["expert_score"],
        "explanation": item["explanation"],
        "correct": user_score == item["expert_score"],
    }


def compute_accuracy(answers: dict[str, int]) -> float:
    """Mean of 1 - |user - expert| / (hi - lo) over the answered items. No answers -> 0.5 (neutral)."""
    items_by_id = {i["id"]: i for i in load_items()}
    scores = []
    for item_id, user_score in answers.items():
        item = items_by_id.get(item_id)
        if not item:
            continue
        ind = get_indicator(item["indicator_id"])
        lo, hi = ind.scale
        scores.append(1 - abs(user_score - item["expert_score"]) / (hi - lo))
    return round(sum(scores) / len(scores), 4) if scores else 0.5
