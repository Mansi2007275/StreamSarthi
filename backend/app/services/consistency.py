"""Cross-indicator contradiction rules, GPS and disagreement checks. Run at submit.

Pure functions: no DB, no FastAPI. Routers only orchestrate.
"""

import json
import operator
from functools import lru_cache
from pathlib import Path

from app.services.indicators import get_indicator, load_indicators
from app.services.scoring import final_score

RULES_FILE = Path(__file__).resolve().parent.parent / "config" / "rules.json"

STRONG_DIFF = 2
STRONG_CONF = 0.7

_OPS = {
    "<=": operator.le,
    ">=": operator.ge,
    "==": operator.eq,
    "<": operator.lt,
    ">": operator.gt,
}


@lru_cache
def load_rules() -> list[dict]:
    rules = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    known = {i.id for i in load_indicators()}
    for rule in rules:
        for cond in rule["when"]:
            if cond["indicator"] not in known:
                raise ValueError(f"rules.json: rule {rule['id']!r} references unknown indicator {cond['indicator']!r}")
    return rules


def is_strong_disagreement(answer: dict) -> bool:
    human, ai, conf = answer.get("human_score"), answer.get("ai_score"), answer.get("ai_confidence")
    if human is None or ai is None or conf is None:
        return False
    return abs(human - ai) >= STRONG_DIFF and conf > STRONG_CONF


def check_observation(obs: dict, answers: list[dict]) -> list[dict]:
    issues: list[dict] = []

    if obs.get("lat") is None or obs.get("lng") is None:
        issues.append({"code": "gps_missing", "message": "Location was not recorded"})

    for a in answers:
        if is_strong_disagreement(a):
            issues.append(
                {
                    "code": "strong_disagreement",
                    "message": f"You said {a['human_score']}, AI said {a['ai_score']} with high confidence",
                    "indicator_id": a["indicator_id"],
                }
            )
        for flag in a.get("flags") or []:
            if flag.endswith("_photo"):
                ind = get_indicator(a["indicator_id"])
                label = ind.label if ind else a["indicator_id"]
                issues.append(
                    {
                        "code": f"photo_quality:{flag}",
                        "message": f"{label}: photo issue ({flag.replace('_', ' ')})",
                        "indicator_id": a["indicator_id"],
                    }
                )

    finals = {a["indicator_id"]: final_score(a) for a in answers}
    for rule in load_rules():
        values = [finals.get(cond["indicator"]) for cond in rule["when"]]
        if any(v is None for v in values):
            continue
        if all(_OPS[cond["op"]](v, cond["value"]) for cond, v in zip(rule["when"], values, strict=True)):
            issues.append({"code": f"contradiction:{rule['id']}", "message": rule["message"]})

    return issues
