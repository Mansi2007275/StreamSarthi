"""End-to-end Phase 1 flow: practice -> submit -> vote -> consensus -> expert -> proof.

Asserts on the same run that `python -m scripts.demo_flow` prints, so the unit tests and
the walkthrough cannot drift apart. The unit tests prove each service alone; this proves
they compose into the flow the game actually needs.
"""

import pytest

from app.services.consensus import AGREES, DISAGREES, DROP_LOW_SKILL, DROP_SAME_CREW, DROP_SELF
from app.services.game_config import load_game_config
from scripts.demo_flow import CITIZEN, MATE, ROOKIE, VOTERS, run_flow
from tests.fakes import FakeRepo

CFG = load_game_config()
STREAM_POINTS = CFG["points"]["stream_check_per_indicator"]


@pytest.fixture(scope="module")
def flow():
    repo = FakeRepo()
    return repo, run_flow(repo)


def test_practice_round_measures_each_player(flow):
    _, result = flow
    assert result["practice"]["player-bob"]["matched"] == 4
    assert result["practice"]["player-bob"]["accuracy"] == 1.0
    assert result["practice"]["player-ann"]["accuracy"] > 0.9
    assert "first_look" in result["practice"]["player-ann"]["badges"]


def test_a_thin_practice_record_does_not_grant_heavy_votes(flow):
    repo, _ = flow
    from app.services.game import skill_weight

    weight = skill_weight(repo.list_gold_votes("player-bob"), "litter_debris", CFG)
    assert CFG["skill_weight"]["neutral"] < weight < 1.7  # perfect, but only 4 photos deep


def test_nobody_is_offered_their_own_or_their_crews_photos(flow):
    _, result = flow
    assert result["offered"][CITIZEN] == 0
    assert result["offered"][MATE] == 0
    assert result["offered"][VOTERS[0]] > 0  # an unrelated player still gets work


def test_self_crew_and_unqualified_votes_are_all_dropped(flow):
    repo, _ = flow
    reasons = {v["voter_id"]: v.get("excluded_reason") for v in repo.votes.values() if v.get("excluded_reason")}
    assert reasons[CITIZEN] == DROP_SELF
    assert reasons[MATE] == DROP_SAME_CREW
    assert reasons[ROOKIE] == DROP_LOW_SKILL


def test_dropped_votes_are_kept_not_deleted(flow):
    repo, _ = flow
    blocked = [v for v in repo.votes.values() if v.get("excluded_reason")]
    assert len(blocked) == 3
    assert all(v["score"] is not None for v in blocked)  # the vote is on record, just not counted


def test_dropped_votes_do_not_change_the_verdict(flow):
    repo, result = flow
    litter = next(a for a in repo.list_answers(result["obs_a"]) if a["indicator_id"] == "litter_debris")
    assert litter["crowd_votes"] == 3  # six votes arrived, three counted
    assert litter["crowd_status"] == AGREES


def test_agreeing_crowd_verifies_the_observation_and_pays_out(flow):
    repo, result = flow
    assert result["outcome_a"]["outcome"] == "crowd_verified"
    obs = repo.get_observation(result["obs_a"])
    assert obs["crowd_verified"] is True
    # crowd verification is not expert sign-off, so the status must not become 'verified'
    assert obs["status"] == "submitted"


def test_settling_twice_never_pays_twice(flow):
    _, result = flow
    assert result["outcome_a"]["settled"] == 6
    assert result["outcome_a"]["resettled"] == 0


def test_a_disagreeing_crowd_sends_it_to_an_expert(flow):
    repo, result = flow
    assert result["outcome_b"]["outcome"] == "needs_review"
    assert result["outcome_b"]["reason"] == "crowd_disagrees"
    colour = next(a for a in repo.list_answers(result["obs_b"]) if a["indicator_id"] == "water_colour")
    assert colour["crowd_status"] == DISAGREES
    assert colour["crowd_score"] == 4
    assert colour["human_score"] == 1  # the citizen's own answer is never overwritten


def test_the_expert_awards_what_they_left_alone_and_voids_what_they_changed(flow):
    _, result = flow
    assert result["review"] == {"awarded": 5, "voided": 1, "settled": 6}


def test_the_citizen_is_paid_only_for_confirmed_work(flow):
    _, result = flow
    totals = result["progress"][CITIZEN]["totals"]
    assert totals["pending"] == 0
    assert totals["awarded"] == 11 * STREAM_POINTS  # 6 crowd-verified + 5 expert-kept, 1 voided
    assert result["progress"][CITIZEN]["verified_checks"] == 2


def test_voters_who_caught_the_error_get_the_badge(flow):
    _, result = flow
    for voter in VOTERS:
        assert result["progress"][voter]["caught_errors"] == 1
        assert "caught_one" in result["progress"][voter]["badges"]


def test_the_rookie_catches_nothing_because_their_vote_never_counted(flow):
    _, result = flow
    assert result["progress"][ROOKIE]["caught_errors"] == 0
    assert result["progress"][ROOKIE]["badges"] == ["first_look"]


def test_variety_badge_comes_from_distinct_verified_indicators(flow):
    _, result = flow
    assert "five_indicators" in result["progress"][CITIZEN]["badges"]
    assert "three_sites" not in result["progress"][CITIZEN]["badges"]  # one site only


def test_everyone_still_has_room_to_level_up(flow):
    _, result = flow
    assert result["progress"][VOTERS[0]]["level"]["id"] == "beginner"
    assert result["progress"][VOTERS[0]]["next"]["id"] == "sharp_eye"


def test_the_crowd_beat_the_lone_citizen_against_the_expert(flow):
    _, result = flow
    proof = result["proof"]
    assert proof["single_citizen_vs_expert"]["exact"] == 0.5
    assert proof["crowd_verified_vs_expert"]["exact"] == 1.0
    assert proof["crowd_verified_vs_expert"]["exact"] > proof["single_citizen_vs_expert"]["exact"]


def test_only_half_the_observations_needed_an_expert(flow):
    _, result = flow
    assert result["proof"]["share_needed_expert"] == 0.5
    assert result["proof"]["counts"] == {
        "total_submitted": 2,
        "needed_expert": 1,
        "crowd_verified": 1,
        "expert_scored_answers": 2,
    }


def test_receipts_were_written_for_every_milestone(flow):
    repo, result = flow
    messages = [r["message"] for r in repo.list_receipts(CITIZEN, unseen_only=True)]
    assert any("Crowd-verified" in m for m in messages)
    assert any("expert" in m.lower() for m in messages)


def test_the_flow_leaves_no_points_unaccounted_for(flow):
    repo, _ = flow
    for row in repo.points:
        assert row["amount"] >= 0  # fairness: no negative awards anywhere
        assert row["status"] in {"pending", "awarded", "void"}
        if row["status"] != "pending":
            assert row["settled_at"]
