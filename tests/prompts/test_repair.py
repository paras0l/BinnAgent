from src.prompts.repair import (
    extract_json_from_fence,
    parse_json_object_with_repair,
    slice_json_object,
    strip_model_explanation,
)


def test_extract_json_from_fence() -> None:
    assert extract_json_from_fence('```json\n{"ok": true}\n```') == '{"ok": true}'


def test_slice_json_object_from_model_explanation() -> None:
    text = 'Here is the result:\n{"ok": true}\nDone.'

    assert slice_json_object(text) == '{"ok": true}'
    assert strip_model_explanation(text) == '{"ok": true}'


def test_parse_json_object_with_repair_marks_explanation_slice() -> None:
    result = parse_json_object_with_repair('说明：{"ok": true} 请查收。')

    assert result.payload == {"ok": True}
    assert result.repair_used is True
    assert result.parse_mode == "json_repair"


def test_parse_json_object_with_repair_rejects_invalid_json() -> None:
    result = parse_json_object_with_repair("not json")

    assert result.payload is None
    assert result.error
