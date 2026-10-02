import statistics

from app.services.consensus import (
    AGREES,
    DISAGREES,
    DROP_LOW_SKILL,
    DROP_SAME_CREW,
    DROP_SELF,
    INCONCLUSIVE,
    NOT_NEEDED,
    PENDING,
    compute_consensus,
    eligible_votes,
    weighted_median,
)
from app.services.game_config import load_game_config

CFG = load_game_config()
NEUTRAL = CFG["skill_weight"]["neutral"]
MIN_VOTES = CFG["consensus"]["min_votes"]


def vote(vote_id, score, voter=None, weight=NEUTRAL):
    return {"id": vote_id, "voter_id": voter or f"voter-{vote_id}", "score": score, "weight": weight}


def votes_for(scores, weight=NEUTRAL):
    return [vote(f"v{i}", score, weight=weight) for i, score in enumerate(scores)]


# ---------------- weighted median ----------------


def test_equal_weights_match_plain_median_odd():
    scores = [1, 2, 5]
    assert weighted_median([(s, 1.0) for s in scores]) == statistics.median(scores)


def test_equal_weights_match_plain_median_even():
    scores = [1, 2, 3, 4]
    assert weighted_median([(s, 1.0) for s in scores]) == statistics.median(scores)


def test_weight_shifts_the_median_toward_the_skilled_voter():
    pairs = [(2, 2.0), (4, 0.5), (5, 0.5)]
    assert weighted_median(pairs) == 2
    assert statistics.median([2, 4, 5]) == 4  # unweighted would have said 4


def test_one_tapper_barely_moves_a_weighted_median():
    pairs = [(2, 1.0), (2, 1.0), (5, 0.4)]
    assert weighted_median(pairs) == 2


def test_weighted_median_ignores_zero_weight_and_missing_scores():
    assert weighted_median([(2, 1.0), (5, 0.0), (None, 1.0)]) == 2


def test_weighted_median_of_nothing_is_none():
    assert weighted_median([]) is None


def test_weighted_median_single_vote():
    assert weighted_median([(3, 1.5)]) == 3


# ---------------- anti-cheat filtering ----------------


def test_your_own_vote_never_counts():
    votes = [vote("v1", 3, voter="me"), vote("v2", 3, voter="other")]
    kept, dropped = eligible_votes(votes, submitter_id="me", cfg=CFG)
    assert [v["id"] for v in kept] == ["v2"]
    assert dropped == [{"vote_id": "v1", "voter_id": "me", "reason": DROP_SELF}]


def test_a_crewmates_vote_never_counts():
    votes = [vote("v1", 3, voter="mate"), vote("v2", 3, voter="stranger")]
    kept, dropped = eligible_votes(
        votes,
        submitter_id="me",
        submitter_crew_id="crew-1",
        voter_crew_ids={"mate": "crew-1", "stranger": "crew-2"},
        cfg=CFG,
    )
    assert [v["id"] for v in kept] == ["v2"]
    assert dropped[0]["reason"] == DROP_SAME_CREW


def test_crew_filter_catches_someone_who_joined_after_voting():
    # the whole reason consensus re-checks what pick_round already checked
    votes = [vote("v1", 5, voter="late-joiner")]
    kept, dropped = eligible_votes(
        votes, submitter_id="me", submitter_crew_id="crew-1", voter_crew_ids={"late-joiner": "crew-1"}, cfg=CFG
    )
    assert kept == []
    assert dropped[0]["reason"] == DROP_SAME_CREW


def test_crewless_voter_and_crewless_submitter_are_not_the_same_crew():
    votes = [vote("v1", 3, voter="stranger")]
    kept, _ = eligible_votes(votes, submitter_id="me", submitter_crew_id=None, voter_crew_ids={}, cfg=CFG)
    assert len(kept) == 1


def test_unskilled_voters_are_dropped_when_stats_are_supplied():
    votes = [vote("v1", 3, voter="rookie"), vote("v2", 3, voter="pro")]
    stats = {
        "rookie": {"gold_votes": 0, "gold_accuracy": None},
        "pro": {"gold_votes": 20, "gold_accuracy": 0.9},
    }
    kept, dropped = eligible_votes(votes, submitter_id="me", voter_stats=stats, cfg=CFG)
    assert [v["id"] for v in kept] == ["v2"]
    assert dropped[0]["reason"] == DROP_LOW_SKILL


def test_skill_filter_is_skipped_when_no_stats_are_given():
    kept, dropped = eligible_votes([vote("v1", 3, voter="unknown")], submitter_id="me", cfg=CFG)
    assert len(kept) == 1 and dropped == []


# ---------------- consensus status ----------------


def test_not_enough_votes_stays_pending_and_asks_for_more():
    result = compute_consensus(votes_for([3, 3]), final_score=3, cfg=CFG, submitter_id="me")
    assert result["crowd_status"] == PENDING
    assert result["crowd_score"] is None
    assert result["votes_needed"] == MIN_VOTES - 2


def test_crowd_agreeing_with_the_citizen():
    result = compute_consensus(votes_for([3, 3, 4]), final_score=3, cfg=CFG, submitter_id="me")
    assert result["crowd_status"] == AGREES
    assert result["crowd_score"] == 3
    assert result["votes_needed"] == 0


def test_one_point_off_still_agrees():
    result = compute_consensus(votes_for([4, 4, 4]), final_score=3, cfg=CFG, submitter_id="me")
    assert result["crowd_status"] == AGREES


def test_two_points_off_disagrees():
    result = compute_consensus(votes_for([5, 5, 5]), final_score=3, cfg=CFG, submitter_id="me")
    assert result["crowd_status"] == DISAGREES
    assert result["crowd_score"] == 5


def test_half_point_gap_is_inconclusive_not_a_verdict():
    # median 4.5 vs citizen 3: diff 1.5 sits between agree_max_diff and disagree_min_diff
    result = compute_consensus(votes_for([4, 4, 5, 5]), final_score=3, cfg=CFG, submitter_id="me")
    assert result["crowd_score"] == 4.5
    assert result["crowd_status"] == INCONCLUSIVE


def test_unanswered_indicator_needs_no_crowd():
    result = compute_consensus(votes_for([3, 3, 3]), final_score=None, cfg=CFG, submitter_id="me")
    assert result["crowd_status"] == NOT_NEEDED
    assert result["votes_needed"] == 0


def test_dropped_votes_do_not_count_toward_the_threshold():
    votes = [vote("v1", 5, voter="me"), vote("v2", 5), vote("v3", 5)]
    result = compute_consensus(votes, final_score=3, cfg=CFG, submitter_id="me")
    assert result["crowd_votes"] == 2
    assert result["crowd_status"] == PENDING
    assert result["votes_needed"] == 1


def test_total_weight_floor_blocks_a_crowd_of_weak_voters():
    weak = votes_for([5, 5, 5], weight=0.4)  # 3 votes but only 1.2 total weight
    result = compute_consensus(weak, final_score=3, cfg=CFG, submitter_id="me")
    assert result["crowd_status"] == PENDING
    assert result["total_weight"] == 1.2


def test_skilled_crowd_overrules_an_unskilled_majority():
    votes = [vote("v1", 5, weight=2.0), vote("v2", 5, weight=2.0), vote("v3", 2, weight=0.4), vote("v4", 2, weight=0.4)]
    result = compute_consensus(votes, final_score=2, cfg=CFG, submitter_id="me")
    assert result["crowd_score"] == 5
    assert result["crowd_status"] == DISAGREES


def test_missing_weight_snapshot_falls_back_to_neutral():
    votes = [{"id": f"v{i}", "voter_id": f"u{i}", "score": 3} for i in range(MIN_VOTES)]
    result = compute_consensus(votes, final_score=3, cfg=CFG, submitter_id="me")
    assert result["total_weight"] == NEUTRAL * MIN_VOTES
    assert result["crowd_status"] == AGREES


def test_voters_are_marked_correct_against_the_consensus():
    votes = [vote("v1", 5), vote("v2", 5), vote("v3", 2)]
    result = compute_consensus(votes, final_score=5, cfg=CFG, submitter_id="me")
    assert result["crowd_score"] == 5
    assert result["vote_correct"] == {"v1": True, "v2": True, "v3": False}


def test_no_voter_is_marked_before_consensus_is_reached():
    result = compute_consensus(votes_for([3, 3]), final_score=3, cfg=CFG, submitter_id="me")
    assert result["vote_correct"] == {}


def test_consensus_counts_and_weight_are_reported():
    result = compute_consensus(votes_for([3, 3, 3]), final_score=3, cfg=CFG, submitter_id="me")
    assert result["crowd_votes"] == 3
    assert result["total_weight"] == NEUTRAL * 3
