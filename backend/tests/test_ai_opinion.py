import pytest

from app.services.ai_opinion import build_prompt, parse_opinion
from app.services.indicators import get_indicator

IND = get_indicator("water_colour")


def test_parses_json_inside_markdown_fences():
    raw = (
        '```json\n{"suggested_score": 4, "confidence": 0.7, "visible_evidence": ["brown"], '
        '"reason": "Cloudy", "can_assess": true, "retake_tip": ""}\n```'
    )
    op = parse_opinion(raw, IND)
    assert op.suggested_score == 4
    assert op.confidence == 0.7
    assert op.visible_evidence == ["brown"]


def test_parses_json_with_extra_text_around_it():
    raw = 'Sure! {"suggested_score": 2, "confidence": 0.5, "can_assess": true} hope that helps'
    assert parse_opinion(raw, IND).suggested_score == 2


def test_out_of_range_score_is_rejected():
    raw = '{"suggested_score": 9, "confidence": 0.9, "can_assess": true}'
    op = parse_opinion(raw, IND)
    assert op.suggested_score is None
    assert op.can_assess is False


def test_cannot_assess_drops_score():
    raw = '{"suggested_score": 3, "confidence": 0.2, "can_assess": false, "retake_tip": "Get closer"}'
    op = parse_opinion(raw, IND)
    assert op.suggested_score is None
    assert op.retake_tip == "Get closer"


def test_garbage_raises():
    with pytest.raises(ValueError):
        parse_opinion("I cannot help with that", IND)


def test_prompt_contains_scale_labels():
    p = build_prompt(IND)
    # Derived from config, so relabelling an indicator cannot silently break the prompt.
    for i, label in enumerate(IND.scale_labels, start=IND.scale[0]):
        assert f"{i}={label}" in p


@pytest.mark.anyio
async def test_missing_api_key_returns_fallback():
    from app.core.config import Settings
    from app.services.ai_opinion import get_opinion

    op = await get_opinion(b"x", IND, Settings(ai_api_key=""))
    assert op.can_assess is False and op.suggested_score is None
