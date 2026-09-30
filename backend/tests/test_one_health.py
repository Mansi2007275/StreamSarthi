import pytest

from app.models.schemas import Indicator
from app.services.indicators import load_indicators
from app.services.one_health import compute_one_health, severity, validate_config

IND = load_indicators()
REQUIRED_IDS = [i.id for i in IND if i.required]


def _answers(score, expert_scores=None):
    expert_scores = expert_scores or {}
    return [
        {
            "indicator_id": rid,
            "human_score": score,
            "ai_score": score,
            "used_ai_answer": False,
            "expert_score": expert_scores.get(rid),
        }
        for rid in REQUIRED_IDS
    ]


def test_all_best_scores_is_good():
    obs = {"status": "submitted"}
    result = compute_one_health(obs, _answers(1), IND)
    assert result is not None
    assert result["level"] == "good"


def test_all_worst_scores_is_poor_with_two_drivers():
    obs = {"status": "submitted"}
    result = compute_one_health(obs, _answers(5), IND)
    assert result["level"] == "poor"
    assert len(result["drivers"]) == 2


def test_middle_scores_is_moderate():
    obs = {"status": "submitted"}
    result = compute_one_health(obs, _answers(3), IND)
    assert result["level"] == "moderate"


def test_higher_is_worse_false_inverts_severity():
    ind = Indicator(
        id="x",
        label="X",
        help={},
        scale=(1, 5),
        scale_labels=["a", "b", "c", "d", "e"],
        higher_is_worse=False,
    )
    assert severity(1, ind) == 1.0
    assert severity(5, ind) == 0.0


def test_expert_score_overrides_and_marks_based_on_expert():
    # Citizens say everything is best; the expert corrects half the required indicators to worst.
    corrected = REQUIRED_IDS[: len(REQUIRED_IDS) // 2]
    obs = {"status": "corrected"}
    answers = _answers(1, expert_scores=dict.fromkeys(corrected, 5))
    result = compute_one_health(obs, answers, IND)
    assert result["based_on"] == "expert"
    # not all-good any more since half the truths are now the worst
    assert result["level"] != "good"


def test_rejected_and_draft_return_none():
    answers = _answers(1)
    assert compute_one_health({"status": "rejected"}, answers, IND) is None
    assert compute_one_health({"status": "draft"}, answers, IND) is None


def test_too_few_answered_indicators_returns_none():
    obs = {"status": "submitted"}
    answers = [
        {
            "indicator_id": REQUIRED_IDS[0],
            "human_score": 1,
            "ai_score": 1,
            "used_ai_answer": False,
            "expert_score": None,
        }
    ]
    assert compute_one_health(obs, answers, IND) is None


def test_config_validation_catches_unsorted_levels():
    cfg = {
        "min_answered_ratio": 0.5,
        "disclaimer": "x",
        "levels": [
            {
                "level": "poor",
                "max_severity": 1.0,
                "color": "red",
                "ecosystem": "a",
                "animals": "b",
                "people": "c",
            },
            {
                "level": "good",
                "max_severity": 0.3,
                "color": "green",
                "ecosystem": "a",
                "animals": "b",
                "people": "c",
            },
        ],
    }
    with pytest.raises(ValueError):
        validate_config(cfg)


def test_config_validation_catches_missing_text_field():
    cfg = {
        "min_answered_ratio": 0.5,
        "disclaimer": "x",
        "levels": [
            {"level": "good", "max_severity": 1.0, "color": "green", "ecosystem": "a", "animals": "b", "people": ""},
        ],
    }
    with pytest.raises(ValueError):
        validate_config(cfg)
