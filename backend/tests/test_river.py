"""The Living River: stage thresholds, cumulative scenery, and the next-stage hint."""

import copy

import pytest

from app.services.river import RIVER_METRICS, load_river_config, river_state, stage_index, validate_config
from tests.conftest import USER_A

CFG = load_river_config()
STAGES = CFG["stages"]
LAST = len(STAGES) - 1


def stats(verified=0, gold=0, caught=0):
    return {"verified_checks": verified, "gold_matches": gold, "caught_errors": caught}


def stats_for(stage: dict):
    """Exactly the requirements of one stage, and nothing more."""
    requires = stage.get("requires") or {}
    return {metric: requires.get(metric, 0) for metric in RIVER_METRICS}


# ---------------- config ----------------


def test_the_real_config_is_valid():
    validate_config(CFG)


def test_there_are_between_six_and_eight_stages():
    assert 6 <= len(STAGES) <= 8


def test_the_first_stage_needs_nothing_so_everybody_has_a_river():
    assert not (STAGES[0].get("requires") or {})


def test_a_stage_that_lowers_a_threshold_is_rejected():
    cfg = copy.deepcopy(CFG)
    cfg["stages"][3]["requires"]["verified_checks"] = 0
    with pytest.raises(ValueError, match="backwards"):
        validate_config(cfg)


def test_an_unknown_metric_is_rejected():
    cfg = copy.deepcopy(CFG)
    cfg["stages"][1]["requires"] = {"submissions": 5}
    with pytest.raises(ValueError, match="unknown metric"):
        validate_config(cfg)


def test_a_first_stage_with_requirements_is_rejected():
    cfg = copy.deepcopy(CFG)
    cfg["stages"][0]["requires"] = {"verified_checks": 1}
    with pytest.raises(ValueError, match="first stage"):
        validate_config(cfg)


def test_duplicate_stage_ids_are_rejected():
    cfg = copy.deepcopy(CFG)
    cfg["stages"][2]["id"] = cfg["stages"][1]["id"]
    with pytest.raises(ValueError, match="duplicate"):
        validate_config(cfg)


def test_the_river_is_driven_only_by_verified_work():
    # nothing in the config may key off raw submissions or points
    for stage in STAGES:
        assert set((stage.get("requires") or {})) <= set(RIVER_METRICS)


# ---------------- thresholds ----------------


def test_a_brand_new_player_starts_at_the_neglected_stream():
    assert stage_index(stats(), CFG) == 0


def test_every_stage_is_reached_at_exactly_its_own_thresholds():
    for i, stage in enumerate(STAGES):
        assert stage_index(stats_for(stage), CFG) == i, f"{stage['id']} not reached at its own thresholds"


def test_one_short_of_a_threshold_stays_on_the_previous_stage():
    for i, stage in enumerate(STAGES[1:], start=1):
        for metric, target in (stage.get("requires") or {}).items():
            if target == 0:
                continue
            short = stats_for(stage)
            short[metric] = target - 1
            assert stage_index(short, CFG) < i, f"{stage['id']} unlocked while {metric} was short"


def test_jumping_several_thresholds_lands_on_the_right_stage():
    assert stage_index(stats(verified=999, gold=999, caught=999), CFG) == LAST


def test_volume_alone_never_moves_the_river():
    # plenty of practice, but nothing confirmed by anybody else
    assert stage_index(stats(verified=0, gold=999, caught=0), CFG) <= 2


def test_missing_metrics_are_treated_as_zero():
    assert stage_index({}, CFG) == 0


def test_none_values_do_not_crash_the_river():
    assert stage_index({"verified_checks": None, "gold_matches": None, "caught_errors": None}, CFG) == 0


# ---------------- scenery and captions ----------------


def test_scenery_is_cumulative():
    state = river_state(stats_for(STAGES[LAST]), CFG)
    expected = [item for stage in STAGES for item in (stage.get("shows") or [])]
    assert state["shows"] == expected
    assert "litter_gone" in state["shows"]  # earned early, never lost


def test_an_early_river_shows_only_what_it_has_earned():
    state = river_state(stats(verified=1), CFG)
    assert state["shows"] == ["litter_gone"]
    assert "fish" not in state["shows"]


def test_the_caption_comes_from_config():
    assert river_state(stats(), CFG)["caption"] == CFG["caption"]
    assert "right" in river_state(stats(), CFG)["caption"]


def test_the_hint_names_the_next_thing_and_its_threshold():
    hint = river_state(stats(verified=3), CFG)["next_hint"]
    assert hint == "Next: fish appear at 5 verified checks."


def test_the_hint_is_singular_at_one():
    assert "1 verified check." in river_state(stats(), CFG)["next_hint"]


def test_the_hint_names_the_requirement_furthest_from_done():
    # frogs need 8 verified and 5 gold; with 7 verified and 0 gold, gold is further away
    hint = river_state(stats(verified=7, gold=0), CFG)["next_hint"]
    assert "gold match" in hint


def test_the_final_stage_has_no_hint():
    state = river_state(stats_for(STAGES[LAST]), CFG)
    assert state["stage_index"] == LAST
    assert state["next_hint"] is None
    assert state["next_stage_label"] is None


def test_the_state_reports_the_stage_count_for_a_progress_dots_row():
    assert river_state(stats(), CFG)["total_stages"] == len(STAGES)


def test_the_state_echoes_the_metrics_it_used():
    assert river_state(stats(verified=4, gold=2, caught=1), CFG)["metrics"] == {
        "verified_checks": 4,
        "gold_matches": 2,
        "caught_errors": 1,
    }


# ---------------- on the Home endpoint ----------------


def test_home_gives_a_new_player_a_neglected_river(as_user, repo):
    body = as_user(USER_A).get("/api/v1/home").json()
    assert body["river"]["stage_index"] == 0
    assert body["river"]["shows"] == []
    assert body["river"]["caption"]
    assert body["river"]["next_hint"]


def test_home_shows_a_river_before_onboarding_too(as_user, repo):
    """Somebody who has not practised yet should still see the stream they are about to mend."""
    body = as_user(USER_A).get("/api/v1/home").json()
    assert body["onboarded"] is False
    assert body["river"] is not None


def test_the_river_grows_with_gold_matches(as_user, repo):
    repo.ensure_profile(USER_A.id, "a@test.com")
    for i in range(6):
        gold = repo.add_gold_item(
            indicator_id="litter_debris", image_path=f"public:/g{i}.jpg", expert_score=3, explanation="x" * 20
        )
        repo.insert_vote(
            {
                "voter_id": USER_A.id,
                "answer_id": None,
                "gold_item_id": gold["id"],
                "indicator_id": "litter_debris",
                "score": 3,
                "confidence": "sure",
                "is_gold": True,
                "correct": True,
            }
        )
    river = as_user(USER_A).get("/api/v1/home").json()["river"]
    assert river["metrics"]["gold_matches"] == 6
    assert river["stage_index"] >= 0  # gold alone cannot outrun the verified-checks gates
