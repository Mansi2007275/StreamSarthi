from app.services.blind_spots import HIGHER, LOWER, compute, summary
from app.services.game_config import load_game_config
from app.services.indicators import load_indicators

CFG = load_game_config()
IND = load_indicators()
BS = CFG["blind_spot"]
LITTER = "litter_debris"
FLOW = "flow"


def gold_vote(score, expert, indicator_id=LITTER):
    return {"indicator_id": indicator_id, "score": score, "expert_score": expert}


def correction(user_score, expert, indicator_id=LITTER):
    return {"indicator_id": indicator_id, "user_score": user_score, "expert_score": expert}


def row_for(items, indicator_id=LITTER, corrections=None):
    rows = compute(items, corrections or [], IND, CFG)
    return next((r for r in rows if r["indicator_id"] == indicator_id), None)


def test_no_data_reports_nothing():
    assert compute([], [], IND, CFG) == []


def test_a_consistent_lean_is_reported_with_a_direction():
    row = row_for([gold_vote(4, 3) for _ in range(BS["min_votes"])])
    assert row["mean_signed_error"] == 1.0
    assert row["direction"] == HIGHER
    assert row["reported"] is True
    assert "higher" in row["message"]


def test_rating_low_is_reported_as_lower():
    row = row_for([gold_vote(2, 3) for _ in range(BS["min_votes"])])
    assert row["direction"] == LOWER
    assert "lower" in row["message"]


def test_noise_in_both_directions_is_not_a_blind_spot():
    # +2 and -2 average to zero: inconsistent, not biased, so no tip
    row = row_for([gold_vote(5, 3), gold_vote(1, 3), gold_vote(3, 3)])
    assert row["mean_signed_error"] == 0.0
    assert row["reported"] is False
    assert row["message"] is None


def test_too_few_judgements_is_measured_but_not_reported():
    row = row_for([gold_vote(5, 3)] * (BS["min_votes"] - 1))
    assert row["n"] == BS["min_votes"] - 1
    assert row["mean_signed_error"] == 2.0
    assert row["reported"] is False


def test_a_lean_below_the_threshold_is_not_reported():
    # mean 0.5 is under min_abs_error, with plenty of data
    row = row_for([gold_vote(4, 3), gold_vote(3, 3), gold_vote(4, 3), gold_vote(3, 3)])
    assert row["mean_signed_error"] == 0.5
    assert abs(row["mean_signed_error"]) < BS["min_abs_error"]
    assert row["reported"] is False


def test_expert_corrections_count_as_well_as_gold_votes():
    rows = compute([gold_vote(4, 3)], [correction(4, 3), correction(4, 3)], IND, CFG)
    row = next(r for r in rows if r["indicator_id"] == LITTER)
    assert row["n"] == BS["min_votes"]
    assert row["reported"] is True


def test_errors_are_kept_per_indicator():
    rows = compute(
        [gold_vote(5, 3, LITTER)] * 3 + [gold_vote(3, 3, FLOW)] * 3,
        [],
        IND,
        CFG,
    )
    by_id = {r["indicator_id"]: r for r in rows}
    assert by_id[LITTER]["reported"] is True
    assert by_id[FLOW]["reported"] is False


def test_indicators_without_data_are_left_out():
    rows = compute([gold_vote(4, 3)], [], IND, CFG)
    assert [r["indicator_id"] for r in rows] == [LITTER]


def test_biggest_lean_comes_first():
    rows = compute([gold_vote(5, 3, LITTER)] * 3 + [gold_vote(4, 3, FLOW)] * 3, [], IND, CFG)
    assert rows[0]["indicator_id"] == LITTER


def test_rows_with_missing_scores_are_skipped():
    rows = compute([{"indicator_id": LITTER, "score": None, "expert_score": 3}], [], IND, CFG)
    assert rows == []


def test_summary_names_a_strength_and_a_focus():
    votes = [gold_vote(3, 3, FLOW)] * 3 + [gold_vote(5, 3, LITTER)] * 3
    result = summary(votes, [], IND, CFG)
    assert result["strongest_indicator"] == FLOW
    assert result["focus_indicator"] == LITTER
    assert result["message"]


def test_summary_does_not_invent_a_focus_from_noise():
    # a new player with four near-perfect judgements should not be told to "focus" on anything
    result = summary([gold_vote(3, 3)] * 4, [], IND, CFG)
    assert result["focus_indicator"] is None
    assert result["message"] is None
    assert result["strongest_indicator"] == LITTER


def test_summary_of_no_data_is_empty_but_safe():
    result = summary([], [], IND, CFG)
    assert result == {"items": [], "strongest_indicator": None, "focus_indicator": None, "message": None}
