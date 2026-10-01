"""Personal blind spots: where a player is consistently off, and in which direction.

Pure functions: no DB, no FastAPI.

The **signed** mean error is the point. A player who is sometimes 2 high and sometimes 2
low is noisy, not biased, and telling them "you rate litter one point high" would be
wrong. Only a consistent lean is worth a tip, so it is reported when
|mean| >= `min_abs_error` over at least `min_votes` judgements.

Two sources, same shape `{"indicator_id", "score"|"user_score", "expert_score"}`:
gold votes (instant, plenty) and expert corrections of the player's own answers (rare,
but the strongest signal there is).
"""

from app.models.schemas import Indicator
from app.services.game_config import load_game_config

HIGHER = "higher"
LOWER = "lower"


def _signed_errors(gold_votes: list[dict], expert_corrections: list[dict]) -> dict[str, list[int]]:
    by_indicator: dict[str, list[int]] = {}
    for row in list(gold_votes) + list(expert_corrections):
        expert = row.get("expert_score")
        mine = row.get("score") if row.get("score") is not None else row.get("user_score")
        indicator_id = row.get("indicator_id")
        if expert is None or mine is None or not indicator_id:
            continue
        by_indicator.setdefault(indicator_id, []).append(mine - expert)
    return by_indicator


def compute(
    gold_votes: list[dict],
    expert_corrections: list[dict],
    indicators: list[Indicator],
    cfg: dict | None = None,
) -> list[dict]:
    """Per-indicator lean, for every indicator with any data. `reported` marks the ones
    strong and well-evidenced enough to show the player."""
    cfg = cfg or load_game_config()
    bs = cfg["blind_spot"]
    errors = _signed_errors(gold_votes, expert_corrections)
    labels = {i.id: i.label for i in indicators}

    out = []
    for ind in indicators:
        values = errors.get(ind.id) or []
        if not values:
            continue
        n = len(values)
        mean = sum(values) / n
        reported = n >= bs["min_votes"] and abs(mean) >= bs["min_abs_error"]
        direction = HIGHER if mean > 0 else LOWER
        message = None
        if reported:
            points = "a point" if abs(mean) < 1.5 else f"{round(abs(mean))} points"
            message = f"You usually rate {labels[ind.id].lower()} about {points} {direction} than the expert."
        out.append(
            {
                "indicator_id": ind.id,
                "label": ind.label,
                "n": n,
                "mean_signed_error": round(mean, 2),
                "direction": direction,
                "reported": reported,
                "message": message,
            }
        )
    out.sort(key=lambda r: abs(r["mean_signed_error"]), reverse=True)
    return out


def summary(
    gold_votes: list[dict],
    expert_corrections: list[dict],
    indicators: list[Indicator],
    cfg: dict | None = None,
) -> dict:
    """What the practice-round result screen says: one thing you are good at, one to work on.

    `strongest_indicator` is the smallest consistent error, `focus_indicator` the biggest -
    and focus is only named when it clears the reporting bar, so a new player with four
    judgements is never told to "focus" on noise.
    """
    items = compute(gold_votes, expert_corrections, indicators, cfg)
    with_data = [i for i in items if i["n"] > 0]
    reported = [i for i in items if i["reported"]]
    return {
        "items": items,
        "strongest_indicator": min(with_data, key=lambda r: abs(r["mean_signed_error"]))["indicator_id"]
        if with_data
        else None,
        "focus_indicator": reported[0]["indicator_id"] if reported else None,
        "message": reported[0]["message"] if reported else None,
    }
