from src.extraction.schemas import WRITING_PHRASE_IMPORT_SCHEMA
from src.prompts.validation import maybe_validate_json_text, validate_output_schema


def test_validate_output_schema_passes_valid_payload() -> None:
    result = validate_output_schema(
        {"candidates": [{"text": "What matters most is that..."}]},
        WRITING_PHRASE_IMPORT_SCHEMA,
    )

    assert result.valid is True
    assert result.error_summary is None


def test_validate_output_schema_returns_structured_error() -> None:
    result = validate_output_schema({"items": []}, WRITING_PHRASE_IMPORT_SCHEMA)

    assert result.valid is False
    assert "$:" in result.error_summary
    assert "candidates" in result.error_summary


def test_maybe_validate_json_text_extracts_markdown_fence() -> None:
    result = maybe_validate_json_text(
        '```json\n{"candidates": [{"text": "What matters most is that..."}]}\n```',
        WRITING_PHRASE_IMPORT_SCHEMA,
    )

    assert result.valid is True
    assert result.parse_mode == "json_schema"
    assert result.repair_used is False


def test_maybe_validate_json_text_slices_explanation_text() -> None:
    result = maybe_validate_json_text(
        '可以，结果如下：{"candidates": [{"text": "What matters most is that..."}]}',
        WRITING_PHRASE_IMPORT_SCHEMA,
    )

    assert result.valid is True
    assert result.parse_mode == "json_repair"
    assert result.repair_used is True
