"""Indicators are config-driven: edit app/config/indicators.json, not code."""

import json
from functools import lru_cache
from pathlib import Path

from app.models.schemas import Indicator

INDICATORS_FILE = Path(__file__).resolve().parent.parent / "config" / "indicators.json"


@lru_cache
def load_indicators() -> list[Indicator]:
    data = json.loads(INDICATORS_FILE.read_text(encoding="utf-8"))
    return [Indicator.model_validate(item) for item in data]


def get_indicator(indicator_id: str) -> Indicator | None:
    return next((i for i in load_indicators() if i.id == indicator_id), None)
