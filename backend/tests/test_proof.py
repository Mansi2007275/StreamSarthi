from app.services.game_config import load_game_config
from app.services.indicators import load_indicators
from app.services.proof import compute_proof

CFG = load_game_config()
IND = load_indicators()
LITTER = "litter_debris"
FLOW = "flow"


def answer(human=3, expert=None, crowd=None, indicator_id=LITTER, used_ai=False, ai=None):
    return {
        "indicator_id": indicator_id,
        "human_score": human,
        "ai_score": ai,
        "used_ai_answer": used_ai,
        "expert_score": expert,
        "crowd_score": crowd,
    }


def obs(status="submitted", crowd_verified=False, reviewed_at=None):
    return {"status": status, "crowd_verified": crowd_verified, "reviewed_at": reviewed_at}


def by_indicator(result, indicator_id):
    return next(r for r in result["per_indicator"] if r["indicator_id"] == indicator_id)


# ---------------- no data must not look like bad data ----------------


def test_nothing_measured_yet_gives_none_not_zero():
    result = compute_proof([], [], IND, CFG)
    assert result["single_citizen_vs_expert"] == {"n": 0, "exact": None, "within_1": None, "mean_abs_error": None}
    assert result["crowd_verified_vs_expert"]["exact"] is None
    assert result["share_needed_expert"] is None


def test_answers_without_an_expert_score_are_not_measured():
    # only expert-scored rows can be checked, so citizen and crowd are judged on the same rows
    result = compute_proof([obs()], [answer(human=3, expert=None)], IND, CFG)
    assert result["single_citizen_vs_expert"]["n"] == 0
    assert result["counts"]["expert_scored_answers"] == 0


# ---------------- claim 1: single citizen vs expert ----------------


def test_single_citizen_agreement_counts_exact_matches():
    answers = [answer(human=3, expert=3), answer(human=5, expert=3)]
    result = compute_proof([obs()], answers, IND, CFG)
    assert result["single_citizen_vs_expert"] == {"n": 2, "exact": 0.5, "within_1": 0.5, "mean_abs_error": 1.0}


def test_one_point_off_counts_as_within_1_but_not_exact():
    result = compute_proof([obs()], [answer(human=4, expert=3)], IND, CFG)
    assert result["single_citizen_vs_expert"]["exact"] == 0.0
    assert result["single_citizen_vs_expert"]["within_1"] == 1.0


def test_citizen_who_took_the_ai_answer_is_judged_on_what_was_saved():
    # final_score = ai_score when used_ai_answer, so the proof reflects the submitted data
    result = compute_proof([obs()], [answer(human=1, used_ai=True, ai=3, expert=3)], IND, CFG)
    assert result["single_citizen_vs_expert"]["exact"] == 1.0


# ---------------- claim 2: crowd vs expert ----------------


def test_crowd_agreement_is_measured_separately():
    answers = [answer(human=5, crowd=3, expert=3), answer(human=5, crowd=3, expert=3)]
    result = compute_proof([obs()], answers, IND, CFG)
    assert result["crowd_verified_vs_expert"]["exact"] == 1.0
    assert result["single_citizen_vs_expert"]["exact"] == 0.0  # the crowd beat the lone citizen


def test_a_half_point_crowd_median_is_within_1_not_exact():
    # 2.5 sits between two scores, so calling it an exact match would be dishonest
    result = compute_proof([obs()], [answer(human=1, crowd=2.5, expert=3)], IND, CFG)
    assert result["crowd_verified_vs_expert"]["exact"] == 0.0
    assert result["crowd_verified_vs_expert"]["within_1"] == 1.0


def test_answers_the_crowd_never_scored_are_left_out_of_the_crowd_claim():
    answers = [answer(human=3, expert=3, crowd=None), answer(human=3, expert=3, crowd=3)]
    result = compute_proof([obs()], answers, IND, CFG)
    assert result["single_citizen_vs_expert"]["n"] == 2
    assert result["crowd_verified_vs_expert"]["n"] == 1


# ---------------- claim 3: per indicator ----------------


def test_per_indicator_covers_every_indicator():
    result = compute_proof([], [], IND, CFG)
    assert len(result["per_indicator"]) == len(IND)
    assert by_indicator(result, FLOW)["single_citizen_vs_expert"]["n"] == 0


def test_per_indicator_separates_a_reliable_indicator_from_a_hard_one():
    answers = [
        answer(human=3, expert=3, indicator_id=LITTER),
        answer(human=3, expert=3, indicator_id=LITTER),
        answer(human=1, expert=4, indicator_id=FLOW),
        answer(human=5, expert=2, indicator_id=FLOW),
    ]
    result = compute_proof([obs()], answers, IND, CFG)
    assert by_indicator(result, LITTER)["single_citizen_vs_expert"]["exact"] == 1.0
    assert by_indicator(result, FLOW)["single_citizen_vs_expert"]["exact"] == 0.0
    assert by_indicator(result, FLOW)["single_citizen_vs_expert"]["mean_abs_error"] == 3.0


def test_per_indicator_reports_the_crowd_too():
    answers = [answer(human=5, crowd=3, expert=3, indicator_id=LITTER)]
    result = compute_proof([obs()], answers, IND, CFG)
    assert by_indicator(result, LITTER)["crowd_verified_vs_expert"]["exact"] == 1.0


# ---------------- claim 4: how little the expert was needed ----------------


def test_share_needed_expert_counts_every_route_to_an_expert():
    observations = [obs(), obs(), obs("needs_review"), obs("corrected")]
    result = compute_proof(observations, [], IND, CFG)
    assert result["share_needed_expert"] == 0.5
    assert result["counts"] == {
        "total_submitted": 4,
        "needed_expert": 2,
        "crowd_verified": 0,
        "expert_scored_answers": 0,
    }


def test_drafts_are_not_part_of_the_denominator():
    result = compute_proof([obs("draft"), obs()], [], IND, CFG)
    assert result["counts"]["total_submitted"] == 1
    assert result["share_needed_expert"] == 0.0


def test_a_reviewed_observation_counts_even_if_its_status_moved_on():
    result = compute_proof([obs("submitted", reviewed_at="2026-10-01T00:00:00Z")], [], IND, CFG)
    assert result["share_needed_expert"] == 1.0


def test_crowd_verified_observations_are_counted():
    result = compute_proof([obs(crowd_verified=True), obs()], [], IND, CFG)
    assert result["counts"]["crowd_verified"] == 1


def test_an_observation_is_never_counted_twice():
    observations = [obs("corrected", crowd_verified=True, reviewed_at="2026-10-01T00:00:00Z")]
    result = compute_proof(observations, [], IND, CFG)
    assert result["counts"]["needed_expert"] == 1
    assert result["share_needed_expert"] == 1.0
