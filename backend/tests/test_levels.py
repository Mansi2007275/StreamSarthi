from app.services.game_config import load_game_config
from app.services.levels import level_for, next_level_progress

CFG = load_game_config()
LEVELS = CFG["levels"]
TOP = LEVELS[-1]


def stats(gold_votes=0, gold_accuracy=None, verified_checks=0):
    return {"gold_votes": gold_votes, "gold_accuracy": gold_accuracy, "verified_checks": verified_checks}


def test_a_brand_new_player_is_the_first_level():
    assert level_for(stats(), CFG)["id"] == LEVELS[0]["id"]
    assert level_for(stats(), CFG)["index"] == 0


def test_unknown_accuracy_still_clears_a_zero_threshold():
    # gold_accuracy None means "not measured yet", and the first level asks for nothing
    assert level_for(stats(gold_accuracy=None), CFG)["id"] == LEVELS[0]["id"]


def test_each_level_is_reached_at_its_own_thresholds():
    for i, level in enumerate(LEVELS):
        reached = level_for(
            stats(level["min_gold_votes"], max(level["min_gold_accuracy"], 0.01), level["min_verified_checks"]),
            CFG,
        )
        assert reached["index"] == i, f"{level['id']} not reached at its own thresholds"


def test_volume_alone_does_not_level_you_up():
    # the whole point: accuracy and verified work, not how much you post
    second = LEVELS[1]
    assert level_for(stats(gold_votes=999, gold_accuracy=0.1), CFG)["index"] == 0
    assert level_for(stats(gold_votes=second["min_gold_votes"], gold_accuracy=second["min_gold_accuracy"]), CFG)[
        "index"
    ] == 1


def test_missing_verified_checks_blocks_the_level():
    third = LEVELS[2]
    short = stats(third["min_gold_votes"], third["min_gold_accuracy"], third["min_verified_checks"] - 1)
    assert level_for(short, CFG)["index"] == 1


def test_top_level_has_no_next_level():
    maxed = stats(TOP["min_gold_votes"], 1.0, TOP["min_verified_checks"])
    assert level_for(maxed, CFG)["id"] == TOP["id"]
    assert next_level_progress(maxed, CFG) is None


def test_progress_names_the_next_level_and_what_is_left():
    progress = next_level_progress(stats(), CFG)
    assert progress["id"] == LEVELS[1]["id"]
    keys = {r["key"] for r in progress["requirements"]}
    assert keys == {"gold_votes", "gold_accuracy"}  # level 2 asks for no verified checks
    assert all(r["met"] is False for r in progress["requirements"])


def test_progress_percent_moves_as_requirements_are_met():
    second = LEVELS[1]
    nothing = next_level_progress(stats(), CFG)["percent"]
    halfway = next_level_progress(stats(gold_votes=second["min_gold_votes"]), CFG)["percent"]
    assert nothing == 0
    assert 0 < halfway < 100


def test_progress_marks_met_requirements():
    second = LEVELS[1]
    progress = next_level_progress(stats(gold_votes=second["min_gold_votes"]), CFG)
    by_key = {r["key"]: r for r in progress["requirements"]}
    assert by_key["gold_votes"]["met"] is True
    assert by_key["gold_accuracy"]["met"] is False


def test_progress_never_exceeds_the_target_fraction():
    second = LEVELS[1]
    progress = next_level_progress(stats(gold_votes=second["min_gold_votes"] * 10), CFG)
    assert progress["percent"] <= 100


def test_requirements_report_current_and_target():
    progress = next_level_progress(stats(gold_votes=3), CFG)
    gold = next(r for r in progress["requirements"] if r["key"] == "gold_votes")
    assert gold["current"] == 3
    assert gold["target"] == LEVELS[1]["min_gold_votes"]
