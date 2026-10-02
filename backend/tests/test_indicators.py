"""Guards on indicators.json: the questions are config, so the config is what we test."""

from app.services.calibration import load_items
from app.services.indicators import get_indicator, load_indicators


def test_indicator_count_is_six_to_eight():
    assert 6 <= len(load_indicators()) <= 8


def test_ids_are_unique():
    ids = [i.id for i in load_indicators()]
    assert len(ids) == len(set(ids))


def test_scale_labels_cover_the_whole_scale():
    for ind in load_indicators():
        lo, hi = ind.scale
        assert len(ind.scale_labels) == hi - lo + 1, ind.id


def test_help_has_english_and_hinglish():
    for ind in load_indicators():
        assert ind.help.get("en") and ind.help.get("hi"), ind.id


def test_cross_exam_is_one_or_two_questions():
    for ind in load_indicators():
        assert 1 <= len(ind.cross_exam) <= 2, ind.id
        for q in ind.cross_exam:
            assert q.strip().endswith("?"), (ind.id, q)


def test_at_least_five_required_indicators():
    assert len([i for i in load_indicators() if i.required]) >= 5


def test_calibration_items_are_valid_and_distinct():
    items = load_items()
    # Phase 2 draws onboarding_gold_count=4 practice items from here.
    assert len(items) >= 4
    assert len({i["indicator_id"] for i in items}) == len(items)
    for item in items:
        ind = get_indicator(item["indicator_id"])
        assert ind is not None, item["id"]
        lo, hi = ind.scale
        assert lo <= item["expert_score"] <= hi, item["id"]
