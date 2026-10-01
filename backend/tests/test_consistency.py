from app.services.consistency import check_observation, is_strong_disagreement, load_rules
from app.services.indicators import load_indicators


def _answer(indicator_id, human=None, ai=None, conf=None, flags=None):
    return {
        "indicator_id": indicator_id,
        "human_score": human,
        "ai_score": ai,
        "ai_confidence": conf,
        "used_ai_answer": False,
        "flags": flags or [],
    }


def test_gps_missing_flagged():
    issues = check_observation({"lat": None, "lng": None}, [])
    assert any(i["code"] == "gps_missing" for i in issues)


def test_gps_present_not_flagged():
    issues = check_observation({"lat": 28.6, "lng": 77.4}, [])
    assert not any(i["code"] == "gps_missing" for i in issues)


def test_strong_disagreement_detected():
    ans = _answer("water_colour", human=1, ai=4, conf=0.9)
    assert is_strong_disagreement(ans) is True

    issues = check_observation({"lat": 1, "lng": 1}, [ans])
    assert any(i["code"] == "strong_disagreement" for i in issues)


def test_low_confidence_disagreement_not_flagged():
    ans = _answer("water_colour", human=1, ai=4, conf=0.5)
    assert is_strong_disagreement(ans) is False

    issues = check_observation({"lat": 1, "lng": 1}, [ans])
    assert not any(i["code"] == "strong_disagreement" for i in issues)


def test_contradiction_rule_triggers():
    answers = [
        _answer("water_colour", human=1, ai=1, conf=0.9),
        _answer("discharge_points", human=5, ai=5, conf=0.9),
    ]
    issues = check_observation({"lat": 1, "lng": 1}, answers)
    assert any(i["code"] == "contradiction:clear_water_but_heavy_discharge" for i in issues)


def test_rule_with_missing_indicator_does_not_trigger():
    answers = [_answer("water_colour", human=1, ai=1, conf=0.9)]
    issues = check_observation({"lat": 1, "lng": 1}, answers)
    assert not any(i["code"].startswith("contradiction:") for i in issues)


def test_all_rule_indicators_exist():
    known = {i.id for i in load_indicators()}
    for rule in load_rules():
        for cond in rule["when"]:
            assert cond["indicator"] in known
