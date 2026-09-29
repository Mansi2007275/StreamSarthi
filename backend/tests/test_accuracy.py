from app.services.trust import updated_accuracy


def _answered(indicator_id, human=1):
    return {"indicator_id": indicator_id, "human_score": human, "ai_score": human, "used_ai_answer": False}


def test_all_match_moves_from_half_to_point_six():
    answers = [_answered("a"), _answered("b"), _answered("c")]
    assert updated_accuracy(0.5, answers, {}) == 0.6


def test_two_of_five_match_gives_point_four_eight():
    answers = [_answered(f"i{i}", human=i) for i in range(5)]
    corrections = {"i0": 99, "i1": 99, "i2": 99}  # 3 wrong; i3, i4 untouched -> match
    assert updated_accuracy(0.5, answers, corrections) == 0.48


def test_no_scored_answers_is_unchanged():
    answers = [{"indicator_id": "a", "human_score": None, "ai_score": None, "used_ai_answer": False}]
    assert updated_accuracy(0.5, answers, {}) == 0.5


def test_missing_old_defaults_to_half():
    answers = [_answered("a")]
    assert updated_accuracy(None, answers, {}) == 0.6
