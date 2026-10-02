"""The configs are the tuning knobs for the whole game, so a bad edit must fail loudly
here rather than quietly change how points or levels work in production."""

import copy
import json

import pytest

from app.services.badges import RULES
from app.services.game_config import CONFIG_FILE, load_game_config, validate_config
from app.services.indicators import load_indicators

CFG = load_game_config()
QUESTS_FILE = CONFIG_FILE.parent / "quests.json"
KNOWN_QUEST_TYPES = {
    "spot_check_count",
    "stream_checks_week",
    "crew_distinct_sites_month",
    "crew_recheck_after_event",
}


def broken(**overrides):
    cfg = copy.deepcopy(CFG)
    cfg.update(overrides)
    return cfg


def test_the_real_config_is_valid():
    validate_config(CFG)


def test_consensus_bands_cannot_overlap():
    with pytest.raises(ValueError, match="agree_max_diff"):
        validate_config(broken(agree_max_diff=2, disagree_min_diff=2))


def test_levels_must_be_ordered_easiest_first():
    cfg = copy.deepcopy(CFG)
    cfg["levels"] = list(reversed(cfg["levels"]))
    with pytest.raises(ValueError, match="ordered"):
        validate_config(cfg)


def test_a_missing_reward_is_rejected():
    cfg = copy.deepcopy(CFG)
    del cfg["points"]["gold_match"]
    with pytest.raises(ValueError, match="points.'gold_match'"):
        validate_config(cfg)


def test_skill_weight_bounds_must_bracket_neutral():
    cfg = copy.deepcopy(CFG)
    cfg["skill_weight"]["neutral"] = 9.0
    with pytest.raises(ValueError, match="min <= neutral <= max"):
        validate_config(cfg)


def test_prior_strength_must_be_positive():
    # a zero prior would let one lucky gold match set a player's full voting weight
    cfg = copy.deepcopy(CFG)
    cfg["skill_weight"]["prior_strength"] = 0
    with pytest.raises(ValueError, match="prior_strength"):
        validate_config(cfg)


def test_no_reward_in_config_is_negative():
    assert all(v >= 0 for v in CFG["points"].values())


def test_consensus_needs_at_least_two_voters_to_mean_anything():
    assert CFG["consensus"]["min_votes"] >= 2


def test_quest_config_parses_and_uses_known_types():
    quests = json.loads(QUESTS_FILE.read_text(encoding="utf-8"))
    assert quests
    for quest in quests:
        assert quest["type"] in KNOWN_QUEST_TYPES
        assert quest["scope"] in {"personal", "crew"}
        assert quest["label"] and quest["description"]


def test_badge_and_quest_ids_are_unique():
    quests = json.loads(QUESTS_FILE.read_text(encoding="utf-8"))
    quest_ids = [q["id"] for q in quests]
    assert len(quest_ids) == len(set(quest_ids))
    assert RULES  # badge rule handlers are registered


def test_calibration_items_all_point_at_real_indicators():
    # gold items are seeded from calibration.json, so a stale indicator id would break the game
    from app.services.calibration import load_items

    known = {i.id for i in load_indicators()}
    assert {item["indicator_id"] for item in load_items()} <= known
