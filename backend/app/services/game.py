"""Spot Check round building and player skill, as pure functions. No DB, no FastAPI.

Two ideas carry the whole game:

1. **Gold items** are photos an expert has already scored. Mixed blindly into rounds,
   they are the only honest way to measure a player without an expert in the loop.
2. **Skill weight** turns that measurement into voting power, per indicator. Somebody
   who reads litter well but guesses at channel form should count more on litter.

Skill weight is deliberately **not** `profiles.observer_accuracy`. That number says how
much to trust a submission (and feeds the Trust Score's O component); this one says how
much a person's vote counts. Taking good photos and judging other people's photos are
different abilities, so they stay separate numbers with separate inputs.

Vote dicts come from the repo. A gold vote carries at least
``{"indicator_id", "score", "expert_score"}``; ``gold_item_id`` and ``correct`` are
ignored here, so the same shape works for expert-settled votes later (Phase 4).
"""

import random

from app.models.schemas import Indicator
from app.services.game_config import load_game_config
from app.services.indicators import get_indicator

GOLD = "gold"
ANSWER = "answer"


def _span(indicator_id: str) -> int | None:
    """Scale width, used to turn a point error into a 0-1 closeness. None if unknown."""
    ind = get_indicator(indicator_id)
    if ind is None:
        return None
    lo, hi = ind.scale
    return hi - lo if hi > lo else None


def _closeness(vote: dict) -> float | None:
    """1.0 for a perfect match, 0.0 for the worst possible miss. Same measure as calibration."""
    expert, score = vote.get("expert_score"), vote.get("score")
    if expert is None or score is None:
        return None
    span = _span(vote.get("indicator_id", ""))
    if span is None:
        return None
    return 1 - abs(score - expert) / span


def gold_accuracy(votes: list[dict]) -> float | None:
    """Mean closeness over all gold votes. None (not 0.0) when there is nothing to judge:
    "unknown" and "always wrong" must not collapse into the same number."""
    values = [c for c in (_closeness(v) for v in votes) if c is not None]
    return round(sum(values) / len(values), 4) if values else None


def indicator_accuracy(votes: list[dict], indicator_id: str) -> tuple[float | None, int]:
    """(accuracy, n) for one indicator. This pair is what the skill map shows."""
    subset = [v for v in votes if v.get("indicator_id") == indicator_id]
    values = [c for c in (_closeness(v) for v in subset) if c is not None]
    if not values:
        return None, 0
    return round(sum(values) / len(values), 4), len(values)


def gold_match_count(votes: list[dict]) -> int:
    """Exact expert matches, for the gold_10 badge and the round summary."""
    return sum(1 for v in votes if v.get("expert_score") is not None and v.get("score") == v["expert_score"])


def _raw_weight(accuracy: float, sw: dict) -> float:
    """Accuracy -> weight, piecewise-linear through the neutral pivot.

    neutral_accuracy maps to exactly `neutral`, 1.0 to `max`, 0.0 to `min`. Two segments
    rather than one straight line so that "average" always means "counts once", whatever
    min and max are set to.
    """
    pivot, neutral = sw["neutral_accuracy"], sw["neutral"]
    if accuracy <= pivot:
        return sw["min"] + (accuracy / pivot) * (neutral - sw["min"])
    return neutral + ((accuracy - pivot) / (1 - pivot)) * (sw["max"] - neutral)


def skill_weight(votes: list[dict], indicator_id: str, cfg: dict | None = None) -> float:
    """This player's voting power on this indicator.

    Shrunk toward a prior by sample size: ``w = (n*w_raw + k*prior) / (n + k)``. So a brand
    new player is exactly neutral, and one lucky gold match cannot make anybody a heavyweight.
    The prior is the player's overall record once they have enough gold votes overall
    (`fallback_to_global`), otherwise neutral - that way being good in general counts for
    something on an indicator you have not seen yet.

    The global prior is shrunk toward neutral by the *same* rule before it is used. Without
    that, somebody who has only done the 4-photo practice round would get a prior as
    confident as their raw estimate (both come from those same 4 photos) and would walk out
    at close to maximum voting power. Shrinking twice means weight only approaches the
    extremes when both the overall and the per-indicator record are genuinely large.
    """
    cfg = cfg or load_game_config()
    sw = cfg["skill_weight"]
    k = sw["prior_strength"]

    prior = sw["neutral"]
    if sw.get("fallback_to_global"):
        overall = gold_accuracy(votes)
        total = len([v for v in votes if _closeness(v) is not None])
        if overall is not None and total >= k:
            prior = (total * _raw_weight(overall, sw) + k * sw["neutral"]) / (total + k)

    accuracy, n = indicator_accuracy(votes, indicator_id)
    if n == 0 or accuracy is None:
        weight = prior
    else:
        weight = (n * _raw_weight(accuracy, sw) + k * prior) / (n + k)
    return round(min(sw["max"], max(sw["min"], weight)), 4)


def skill_map(votes: list[dict], indicators: list[Indicator], cfg: dict | None = None) -> list[dict]:
    """Per-indicator standing: "strong on litter, weak on channel form"."""
    cfg = cfg or load_game_config()
    sm = cfg["skill_map"]
    out = []
    for ind in indicators:
        accuracy, n = indicator_accuracy(votes, ind.id)
        if n < sm["min_votes"] or accuracy is None:
            standing = "unknown"
        elif accuracy >= sm["strong_accuracy"]:
            standing = "strong"
        elif accuracy <= sm["weak_accuracy"]:
            standing = "weak"
        else:
            standing = "ok"
        out.append(
            {
                "indicator_id": ind.id,
                "label": ind.label,
                "n": n,
                "accuracy": accuracy,
                "weight": skill_weight(votes, ind.id, cfg),
                "standing": standing,
            }
        )
    return out


def is_eligible_voter(stats: dict, cfg: dict | None = None) -> bool:
    """Whether this player's votes count toward consensus at all.

    Everyone may play - this only gates whether a vote moves real data.
    """
    cfg = cfg or load_game_config()
    accuracy = stats.get("gold_accuracy")
    return (
        stats.get("gold_votes", 0) >= cfg["voter_min_gold_votes"]
        and accuracy is not None
        and accuracy >= cfg["voter_min_gold_accuracy"]
    )


def gold_item(item: dict) -> dict:
    return {
        "item_type": GOLD,
        "id": item["id"],
        "indicator_id": item["indicator_id"],
        "image_ref": item["image_path"],
    }


def _answer_item(answer: dict) -> dict:
    return {
        "item_type": ANSWER,
        "id": answer["id"],
        "indicator_id": answer["indicator_id"],
        "image_ref": f"storage:{answer['photo_path']}",
        # Deliberately absent: submitter, crew, location, human_score, ai_score.
    }


def eligible_candidates(user_stats: dict, candidate_answers: list[dict], cfg: dict | None = None) -> list[dict]:
    """Answers this player is allowed to vote on, best first.

    The anti-cheat rules live here: never your own observation, never a crew-mate's (they
    were probably standing next to you), never one you already voted on, never one without
    a photo. Consensus re-checks all of this (services/consensus.py) because crew
    membership can change after a vote was cast.
    """
    cfg = cfg or load_game_config()
    exclude_crew = cfg["anti_cheat"].get("exclude_own_crew", True)
    user_id = user_stats.get("user_id")
    crew_id = user_stats.get("crew_id")
    voted = set(user_stats.get("voted_answer_ids") or ())

    allowed = []
    for a in candidate_answers:
        if not a.get("photo_path"):
            continue
        if a["id"] in voted:
            continue
        if a.get("user_id") == user_id:
            continue
        if exclude_crew and crew_id is not None and a.get("crew_id") == crew_id:
            continue
        allowed.append(a)

    # Fewest votes first, so attention spreads instead of piling onto one photo.
    allowed.sort(key=lambda a: (a.get("crowd_votes") or 0, a.get("created_at") or ""))
    return allowed


def pick_round(
    user_stats: dict,
    candidate_answers: list[dict],
    gold_items: list[dict],
    cfg: dict | None = None,
    rng: random.Random | None = None,
) -> list[dict]:
    """One Spot Check round: gold items mixed blindly into real answers.

    New players get gold only, so their first experience is instant feedback and their
    first real votes already carry a measured weight. After that it is one gold every
    `gold_every` items, dropped at a position drawn from `rng`: a fixed slot would be
    guessable, and a player who knows which photo is scored is no longer being measured.
    Gold and real items come back in exactly the same shape for the same reason.
    """
    cfg = cfg or load_game_config()
    rng = rng or random.Random()
    size = cfg["round_size"]

    voted_gold = set(user_stats.get("voted_gold_ids") or ())
    gold_pool = [g for g in gold_items if g.get("active", True) and g["id"] not in voted_gold]
    rng.shuffle(gold_pool)

    if user_stats.get("gold_votes", 0) < cfg["new_player_gold_only_until"]:
        return [gold_item(g) for g in gold_pool[:size]]

    gold_count = min(size // cfg["gold_every"], len(gold_pool))
    answers = eligible_candidates(user_stats, candidate_answers, cfg)[: size - gold_count]

    items = [_answer_item(a) for a in answers]
    for g in gold_pool[:gold_count]:
        items.insert(rng.randint(0, len(items)), gold_item(g))
    return items[:size]


def gold_rows_from_calibration(items: list[dict]) -> list[dict]:
    """calibration.json -> gold_items rows, so the practice photos we already have
    become the onboarding round instead of a second parallel set of images."""
    return [
        {
            "indicator_id": item["indicator_id"],
            "image_path": f"public:{item['image']}",
            "expert_score": item["expert_score"],
            "explanation": item["explanation"],
            "source": "seed",
            "active": True,
        }
        for item in items
    ]
