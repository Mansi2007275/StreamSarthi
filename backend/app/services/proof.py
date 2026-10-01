"""Data-quality proof: the numbers that answer "why should a researcher trust this?".

Pure function: no DB, no FastAPI. Endpoint comes later (Phase 4's /review/stats).

Four claims, each measured against the expert score as truth:

1. **single_citizen_vs_expert** - how often one citizen on their own matched the expert.
   This is the baseline, the thing citizen science is usually criticised for.
2. **crowd_verified_vs_expert** - how often the skill-weighted crowd matched the expert.
   The whole design is worth something only if this beats the line above.
3. **per_indicator** - the same pair per indicator, so "litter is reliable, channel form
   needs an expert" is a measurement rather than an opinion.
4. **share_needed_expert** - the cost claim: what fraction of observations an expert had
   to touch at all.

Comparisons are only ever made on answers an expert actually scored, so (1) and (2) are
measured on the same rows and can be compared honestly. Empty denominators give None, not
0.0 - "we have no evidence yet" must never render as "0% accurate".
"""

from app.models.schemas import Indicator
from app.services.game_config import load_game_config
from app.services.scoring import final_score

EXPERT_TOUCHED_STATUSES = ("needs_review", "verified", "corrected", "rejected")
_EXACT_TOLERANCE = 0.5


def _agreement(pairs: list[tuple[float, int]], tolerance: int) -> dict:
    """pairs of (predicted, expert). `exact` requires landing on the expert's score; a
    crowd median of 2.5 sits between two scores, so it counts as within-1, not exact."""
    n = len(pairs)
    if n == 0:
        return {"n": 0, "exact": None, "within_1": None, "mean_abs_error": None}
    diffs = [abs(predicted - expert) for predicted, expert in pairs]
    return {
        "n": n,
        "exact": round(sum(1 for d in diffs if d < _EXACT_TOLERANCE) / n, 3),
        "within_1": round(sum(1 for d in diffs if d <= tolerance) / n, 3),
        "mean_abs_error": round(sum(diffs) / n, 2),
    }


def _pairs(answers: list[dict]) -> tuple[list[tuple[float, int]], list[tuple[float, int]]]:
    """(citizen pairs, crowd pairs) over expert-scored answers only."""
    citizen, crowd = [], []
    for a in answers:
        expert = a.get("expert_score")
        if expert is None:
            continue
        own = final_score(a)
        if own is not None:
            citizen.append((own, expert))
        if a.get("crowd_score") is not None:
            crowd.append((float(a["crowd_score"]), expert))
    return citizen, crowd


def compute_proof(
    observations: list[dict],
    answers: list[dict],
    indicators: list[Indicator],
    cfg: dict | None = None,
) -> dict:
    cfg = cfg or load_game_config()
    tolerance = cfg["agree_max_diff"]

    citizen_pairs, crowd_pairs = _pairs(answers)

    by_indicator: dict[str, list[dict]] = {}
    for a in answers:
        by_indicator.setdefault(a["indicator_id"], []).append(a)

    per_indicator = []
    for ind in indicators:
        rows = by_indicator.get(ind.id) or []
        ind_citizen, ind_crowd = _pairs(rows)
        per_indicator.append(
            {
                "indicator_id": ind.id,
                "label": ind.label,
                "single_citizen_vs_expert": _agreement(ind_citizen, tolerance),
                "crowd_verified_vs_expert": _agreement(ind_crowd, tolerance),
            }
        )

    submitted = [o for o in observations if o.get("status") != "draft"]
    needed_expert = [
        o for o in submitted if o.get("reviewed_at") is not None or o.get("status") in EXPERT_TOUCHED_STATUSES
    ]
    crowd_verified = [o for o in submitted if o.get("crowd_verified")]

    return {
        "single_citizen_vs_expert": _agreement(citizen_pairs, tolerance),
        "crowd_verified_vs_expert": _agreement(crowd_pairs, tolerance),
        "per_indicator": per_indicator,
        "share_needed_expert": round(len(needed_expert) / len(submitted), 3) if submitted else None,
        "counts": {
            "total_submitted": len(submitted),
            "needed_expert": len(needed_expert),
            "crowd_verified": len(crowd_verified),
            "expert_scored_answers": len([a for a in answers if a.get("expert_score") is not None]),
        },
    }
