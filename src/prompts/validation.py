from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from src.prompts.repair import parse_json_object_with_repair


@dataclass(frozen=True)
class SchemaValidationResult:
    valid: bool
    error_summary: str | None = None


@dataclass(frozen=True)
class JsonTextValidationResult:
    payload: dict[str, Any] | None
    valid: bool
    repair_used: bool
    parse_mode: str
    error_summary: str | None = None


def validate_output_schema(
    payload: dict[str, Any],
    schema_json: dict[str, Any] | None,
) -> SchemaValidationResult:
    if schema_json is None:
        return SchemaValidationResult(valid=True)
    try:
        Draft202012Validator(schema_json).validate(payload)
    except ValidationError as exc:
        return SchemaValidationResult(valid=False, error_summary=summarize_schema_error(exc))
    return SchemaValidationResult(valid=True)


def summarize_schema_error(error: ValidationError) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    location = path or "$"
    return f"{location}: {error.message}"[:500]


def maybe_validate_json_text(
    raw_text: str,
    schema_json: dict[str, Any] | None,
) -> JsonTextValidationResult:
    if schema_json is None:
        return JsonTextValidationResult(
            payload=None,
            valid=True,
            repair_used=False,
            parse_mode="text_only",
        )

    parsed = parse_json_object_with_repair(raw_text)
    if parsed.payload is None:
        return JsonTextValidationResult(
            payload=None,
            valid=False,
            repair_used=parsed.repair_used,
            parse_mode=parsed.parse_mode,
            error_summary=parsed.error,
        )

    validation = validate_output_schema(parsed.payload, schema_json)
    return JsonTextValidationResult(
        payload=parsed.payload if validation.valid else None,
        valid=validation.valid,
        repair_used=parsed.repair_used,
        parse_mode=parsed.parse_mode,
        error_summary=validation.error_summary,
    )
