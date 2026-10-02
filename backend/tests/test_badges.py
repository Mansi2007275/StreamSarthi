import pytest

from app.services.badges import RULES, evaluate, load_badges, validate_config, with_status

BADGES = load_badges()
BY_ID = {b["id"]: b for b in BADGES}


def ids(result):
    return {b["id"] for b in result}


def only(badge_id):
    """Evaluate one badge in isolation, so a test cannot accidentally depend on another."""
    return [BY_ID[badge_id]]


# ---------------- config ----------------


def test_config_is_valid_and_every_rule_type_is_implemented():
    validate_config(BADGES)
    for badge in BADGES:
        assert badge["rule"]["type"] in RULES


def test_config_rejects_an_unknown_rule_type():
    with pytest.raises(ValueError, match="unknown rule type"):
        validate_config([{"id": "x", "label": "X", "description": "d", "icon": "i", "rule": {"type": "vibes"}}])


def test_config_rejects_duplicate_ids():
    one = BY_ID["gold_10"]
    with pytest.raises(ValueError, match="duplicate"):
        validate_config([one, dict(one)])


def test_config_rejects_a_missing_field():
    with pytest.raises(ValueError, match="description"):
        validate_config([{"id": "x", "label": "X", "icon": "i", "rule": {"type": "onboarded"}}])


def test_no_badge_rewards_raw_volume():
    # fairness: variety and accuracy only, nothing for posting the most
    assert all("submission" not in b["rule"]["type"] for b in BADGES)


# ---------------- one test per rule ----------------


def test_first_look_needs_onboarding():
    assert ids(evaluate({"onboarded": True}, badges=only("first_look"))) == {"first_look"}
    assert evaluate({"onboarded": False}, badges=only("first_look")) == []


def test_five_indicators_counts_distinct_indicators():
    rule_min = BY_ID["five_indicators"]["rule"]["min"]
    enough = {"verified_indicators": [f"ind{i}" for i in range(rule_min)]}
    repeats = {"verified_indicators": ["flow"] * rule_min}
    assert ids(evaluate(enough, badges=only("five_indicators"))) == {"five_indicators"}
    assert evaluate(repeats, badges=only("five_indicators")) == []


def test_three_sites_counts_distinct_sites():
    rule_min = BY_ID["three_sites"]["rule"]["min"]
    assert ids(evaluate({"verified_sites": [f"s{i}" for i in range(rule_min)]}, badges=only("three_sites"))) == {
        "three_sites"
    }
    assert evaluate({"verified_sites": ["s1"] * rule_min}, badges=only("three_sites")) == []


def test_gold_10_needs_that_many_exact_matches():
    rule_min = BY_ID["gold_10"]["rule"]["min"]
    assert ids(evaluate({"gold_matches": rule_min}, badges=only("gold_10"))) == {"gold_10"}
    assert evaluate({"gold_matches": rule_min - 1}, badges=only("gold_10")) == []


def test_monsoon_check_needs_a_check_in_a_monsoon_month():
    months = BY_ID["monsoon_check"]["rule"]["months"]
    assert ids(evaluate({"verified_check_months": [months[0]]}, badges=only("monsoon_check"))) == {"monsoon_check"}
    assert evaluate({"verified_check_months": [1, 12]}, badges=only("monsoon_check")) == []


def test_caught_one_needs_a_crowd_catch_the_expert_agreed_with():
    assert ids(evaluate({"caught_errors": 1}, badges=only("caught_one"))) == {"caught_one"}
    assert evaluate({"caught_errors": 0}, badges=only("caught_one")) == []


def test_steady_guardian_needs_consecutive_monthly_checks():
    rule_min = BY_ID["steady_guardian"]["rule"]["min"]
    assert ids(evaluate({"adopted_streak": rule_min}, badges=only("steady_guardian"))) == {"steady_guardian"}
    assert evaluate({"adopted_streak": rule_min - 1}, badges=only("steady_guardian")) == []


# ---------------- evaluate() behaviour ----------------


def test_empty_stats_unlock_nothing():
    assert evaluate({}) == []


def test_already_unlocked_badges_are_not_returned_again():
    # so each badge produces exactly one celebration and one receipt, ever
    stats = {"onboarded": True}
    assert ids(evaluate(stats, badges=only("first_look"))) == {"first_look"}
    assert evaluate(stats, unlocked={"first_look"}, badges=only("first_look")) == []


def test_several_badges_can_unlock_at_once():
    stats = {"onboarded": True, "gold_matches": BY_ID["gold_10"]["rule"]["min"]}
    assert ids(evaluate(stats)) == {"first_look", "gold_10"}


def test_missing_stat_keys_are_treated_as_nothing_yet():
    assert evaluate({"onboarded": True}, badges=only("gold_10")) == []


def test_with_status_lists_every_badge_locked_and_unlocked():
    rows = with_status({"first_look"})
    assert len(rows) == len(BADGES)
    unlocked = {r["id"] for r in rows if r["unlocked"]}
    assert unlocked == {"first_look"}
    # locked ones keep their description, so the UI can say how to get there
    assert all(r["description"] for r in rows)
