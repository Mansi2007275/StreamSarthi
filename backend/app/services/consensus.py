"""Crowd consensus on a citizen's answer, weighted by each voter's measured skill.

Pure functions: no DB, no FastAPI.

The weighted median, not the mean: one player who taps 5 on everything then shifts a mean,
but barely moves a median. With equal weights this reduces exactly to the plain median,
so the simple behaviour is a special case of the weighted one.

Each vote's weight is the snapshot taken when it was cast (`validation_votes.weight`).
Recomputing weights now would quietly change consensus results people have already been
shown, and would make a past decision impossible to reproduce for an audit.
"""

from app.services.game import is_eligible_voter
from app.services.game_config import load_game_config

PENDING = "pending"
AGREES = "agrees"
DISAGREES = "disagrees"
INCONCLUSIVE = "inconclusive"
NOT_NEEDED = "not_needed"

DROP_SELF = "self"
DROP_SAME_CREW = "same_crew"
DROP_LOW_SKILL = "low_skill"

# Statuses that hand the observation to an expert (Phase 2 routing reads this, so the
# decision lives in one place). `inconclusive` is in here on purpose: a crowd that cannot
# settle a real disagreement is exactly what an expert is for, and leaving it out would
# strand the citizen's pending points with no way to resolve them.
ROUTE_TO_EXPERT_STATUSES = (DISAGREES, INCONCLUSIVE)
ROUTING_REASONS = {DISAGREES: "crowd_disagrees", INCONCLUSIVE: "crowd_inconclusive"}


def eligible_votes(
    votes: list[dict],
    *,
    submitter_id: str | None,
    submitter_crew_id: str | None = None,
    voter_crew_ids: dict[str, str | None] | None = None,
    voter_stats: dict[str, dict] | None = None,
    cfg: dict | None = None,
) -> tuple[list[dict], list[dict]]:
    """Split votes into (counted, dropped). Dropped rows carry the reason.

    This repeats the checks `game.eligible_candidates` already made when the round was
    built, on purpose. A player can join the submitter's crew after voting, and a vote
    that was fair when cast is not fair when counted. Dropped votes are kept and
    labelled rather than deleted, so an expert can see the call that was made.
    """
    cfg = cfg or load_game_config()
    exclude_crew = cfg["anti_cheat"].get("exclude_own_crew", True)
    voter_crew_ids = voter_crew_ids or {}

    counted, dropped = [], []
    for v in votes:
        voter = v.get("voter_id")
        if voter is not None and voter == submitter_id:
            reason = DROP_SELF
        elif (
            exclude_crew
            and submitter_crew_id is not None
            and voter_crew_ids.get(voter) is not None
            and voter_crew_ids.get(voter) == submitter_crew_id
        ):
            reason = DROP_SAME_CREW
        elif voter_stats is not None and not is_eligible_voter(voter_stats.get(voter) or {}, cfg):
            reason = DROP_LOW_SKILL
        else:
            counted.append(v)
            continue
        dropped.append({"vote_id": v.get("id"), "voter_id": voter, "reason": reason})
    return counted, dropped


def weighted_median(pairs: list[tuple[float, float]]) -> float | None:
    """Median where each value carries a weight. Equal weights == statistics.median,
    including the "average the middle two" rule for even counts."""
    usable = [(s, w) for s, w in pairs if s is not None and w is not None and w > 0]
    if not usable:
        return None
    usable.sort(key=lambda p: p[0])
    total = sum(w for _, w in usable)
    half = total / 2
    cumulative = 0.0
    for i, (score, weight) in enumerate(usable):
        cumulative += weight
        if cumulative > half:
            return float(score)
        if cumulative == half:
            # The weight splits exactly in two: take the midpoint of the two sides.
            nxt = usable[i + 1][0] if i + 1 < len(usable) else score
            return (score + nxt) / 2
    return float(usable[-1][0])


def _weight_of(vote: dict, cfg: dict) -> float:
    weight = vote.get("weight")
    return float(weight) if weight is not None else float(cfg["skill_weight"]["neutral"])


def compute_consensus(
    votes: list[dict],
    final_score: int | None,
    cfg: dict | None = None,
    *,
    submitter_id: str | None = None,
    submitter_crew_id: str | None = None,
    voter_crew_ids: dict[str, str | None] | None = None,
    voter_stats: dict[str, dict] | None = None,
) -> dict:
    """What the crowd thinks of one answer.

    Returns the fields to write onto the answer (`crowd_score`, `crowd_votes`,
    `crowd_status`) plus what the caller needs to act: how many more votes are wanted,
    which votes were dropped and why, and which voters got it right.
    """
    cfg = cfg or load_game_config()
    consensus_cfg = cfg["consensus"]

    counted, dropped = eligible_votes(
        votes,
        submitter_id=submitter_id,
        submitter_crew_id=submitter_crew_id,
        voter_crew_ids=voter_crew_ids,
        voter_stats=voter_stats,
        cfg=cfg,
    )
    pairs = [(v.get("score"), _weight_of(v, cfg)) for v in counted]
    total_weight = round(sum(w for s, w in pairs if s is not None), 4)

    result = {
        "crowd_score": None,
        "crowd_votes": len(counted),
        "crowd_status": PENDING,
        "total_weight": total_weight,
        "votes_needed": max(consensus_cfg["min_votes"] - len(counted), 0),
        "dropped": dropped,
        "vote_correct": {},
    }

    # Nothing to compare against: the citizen never gave this indicator a score.
    if final_score is None:
        result["crowd_status"] = NOT_NEEDED
        result["votes_needed"] = 0
        return result

    enough_votes = len(counted) >= consensus_cfg["min_votes"]
    enough_weight = total_weight >= consensus_cfg["min_total_weight"]
    if not (enough_votes and enough_weight):
        return result

    median = weighted_median(pairs)
    if median is None:
        return result

    diff = abs(median - final_score)
    if diff <= cfg["agree_max_diff"]:
        status = AGREES
    elif diff >= cfg["disagree_min_diff"]:
        status = DISAGREES
    else:
        # Between the two thresholds: real disagreement, but not enough to overrule a
        # citizen who was standing at the stream. An expert decides, the crowd does not.
        status = INCONCLUSIVE

    result["crowd_score"] = round(median, 2)
    result["crowd_status"] = status
    result["votes_needed"] = 0
    result["vote_correct"] = {
        v["id"]: abs(v["score"] - median) <= cfg["agree_max_diff"]
        for v in counted
        if v.get("id") is not None and v.get("score") is not None
    }
    return result
