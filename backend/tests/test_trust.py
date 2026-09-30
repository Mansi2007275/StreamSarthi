from app.services.indicators import load_indicators
from app.services.trust import REVIEW_THRESHOLD, compute_trust

IND = load_indicators()
REQUIRED_IDS = [i.id for i in IND if i.required]


def _perfect_answers():
    return [
        {
            "indicator_id": rid,
            "human_score": 3,
            "ai_score": 3,
            "ai_confidence": 0.9,
            "used_ai_answer": False,
            "photo_quality": {"score": 1.0},
        }
        for rid in REQUIRED_IDS
    ]


def test_perfect_case_is_100():
    obs = {"lat": 28.6, "lng": 77.4}
    trust = compute_trust(obs, _perfect_answers(), IND, observer_accuracy=1.0, issues=[])
    assert trust["score"] == 100.0


def test_hand_example_agreement():
    ans = [
        {
            "indicator_id": REQUIRED_IDS[0],
            "human_score": 2,
            "ai_score": 4,
            "ai_confidence": 0.8,
            "used_ai_answer": False,
        }
    ]
    trust = compute_trust({"lat": 1, "lng": 1}, ans, IND, observer_accuracy=0.5, issues=[])
    assert trust["components"]["A"] == 0.6


def test_all_low_confidence_gives_neutral_agreement():
    ans = [
        {
            "indicator_id": rid,
            "human_score": 1,
            "ai_score": 5,
            "ai_confidence": 0.1,
            "used_ai_answer": False,
        }
        for rid in REQUIRED_IDS
    ]
    trust = compute_trust({"lat": 1, "lng": 1}, ans, IND, observer_accuracy=0.5, issues=[])
    assert trust["components"]["A"] == 0.5


def test_gps_removed_drops_score_by_exactly_15():
    with_gps = compute_trust({"lat": 1, "lng": 1}, _perfect_answers(), IND, 1.0, [])
    without_gps = compute_trust({"lat": None, "lng": None}, _perfect_answers(), IND, 1.0, [])
    assert round(with_gps["score"] - without_gps["score"], 1) == 15.0


def test_strong_disagreement_forces_review_even_with_high_score():
    trust = compute_trust(
        {"lat": 1, "lng": 1},
        _perfect_answers(),
        IND,
        1.0,
        issues=[{"code": "strong_disagreement", "message": "x"}],
    )
    assert trust["score"] >= REVIEW_THRESHOLD
    assert trust["needs_review"] is True


def _boundary_answers():
    return [
        {
            "indicator_id": rid,
            "human_score": 1,
            "ai_score": 5,
            "ai_confidence": 1.0,
            "used_ai_answer": False,
            "photo_quality": {"score": 1.0},
        }
        for rid in REQUIRED_IDS
    ]


def test_needs_review_boundary():
    obs = {"lat": 1, "lng": 1}

    at_threshold = compute_trust(obs, _boundary_answers(), IND, observer_accuracy=0.5, issues=[])
    assert at_threshold["score"] == 60.0
    assert at_threshold["needs_review"] is False

    below_threshold = compute_trust(obs, _boundary_answers(), IND, observer_accuracy=0.49, issues=[])
    assert below_threshold["score"] < 60.0
    assert below_threshold["needs_review"] is True
