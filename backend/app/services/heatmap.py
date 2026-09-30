"""Per-indicator human/AI disagreement stats, for the expert insights page.

Pure function: no DB, no FastAPI. Mirrors the indicator_disagreement SQL view
(migrations/004) but computed in Python so it stays unit-testable without a DB.
"""

from app.models.schemas import Indicator

STRONG_DIFF = 2
STRONG_CONF = 0.7


def compute_disagreement(answers: list[dict], indicators: list[Indicator]) -> list[dict]:
    by_indicator: dict[str, list[dict]] = {}
    for a in answers:
        by_indicator.setdefault(a["indicator_id"], []).append(a)

    results = []
    for ind in indicators:
        rows = by_indicator.get(ind.id, [])
        lo, hi = ind.scale
        size = hi - lo + 1

        with_ai = [r for r in rows if r.get("human_score") is not None and r.get("ai_score") is not None]
        n = len(with_ai)
        diffs = [abs(r["human_score"] - r["ai_score"]) for r in with_ai]
        biases = [r["human_score"] - r["ai_score"] for r in with_ai]
        strong = [
            r
            for r in with_ai
            if abs(r["human_score"] - r["ai_score"]) >= STRONG_DIFF and (r.get("ai_confidence") or 0) > STRONG_CONF
        ]

        reviewed = [r for r in rows if r.get("expert_score") is not None]
        human_wrong = [r for r in reviewed if r.get("human_score") != r["expert_score"]]
        ai_reviewed = [r for r in reviewed if r.get("ai_score") is not None]
        ai_wrong = [r for r in ai_reviewed if r["ai_score"] != r["expert_score"]]

        matrix = [[0] * size for _ in range(size)]
        for r in with_ai:
            h_idx, a_idx = r["human_score"] - lo, r["ai_score"] - lo
            if 0 <= h_idx < size and 0 <= a_idx < size:
                matrix[h_idx][a_idx] += 1

        results.append(
            {
                "indicator_id": ind.id,
                "label": ind.label,
                "n": n,
                "mean_abs_diff": round(sum(diffs) / n, 2) if n else None,
                "mean_bias": round(sum(biases) / n, 2) if n else None,
                "strong_rate": round(len(strong) / n, 3) if n else None,
                "human_wrong_rate": round(len(human_wrong) / len(reviewed), 3) if reviewed else None,
                "ai_wrong_rate": round(len(ai_wrong) / len(ai_reviewed), 3) if ai_reviewed else None,
                "matrix": matrix,
                "scale": [lo, hi],
            }
        )
    return results
