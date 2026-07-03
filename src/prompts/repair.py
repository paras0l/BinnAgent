import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JsonRepairResult:
    payload: dict[str, Any] | None
    repair_used: bool
    parse_mode: str
    error: str | None = None


def extract_json_from_fence(raw_text: str) -> str | None:
    text = raw_text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S | re.I)
    if not match:
        return None
    return match.group(1).strip()


def slice_json_object(raw_text: str) -> str | None:
    text = raw_text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    return text[start : end + 1]


def strip_model_explanation(raw_text: str) -> str:
    fenced = extract_json_from_fence(raw_text)
    if fenced is not None:
        return fenced
    sliced = slice_json_object(raw_text)
    return sliced if sliced is not None else raw_text.strip()


def parse_json_object_with_repair(raw_text: str) -> JsonRepairResult:
    text = raw_text.strip()
    last_error: str | None = None
    attempts: list[tuple[str | None, bool, str]] = [
        (text, False, "json_schema"),
        (extract_json_from_fence(text), False, "json_schema"),
        (strip_model_explanation(text), True, "json_repair"),
        (slice_json_object(text), True, "json_repair"),
    ]

    seen: set[str] = set()
    for candidate, repair_used, parse_mode in attempts:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = f"{exc.msg} at line {exc.lineno} column {exc.colno}"
            continue
        if isinstance(parsed, dict):
            return JsonRepairResult(
                payload=parsed,
                repair_used=repair_used,
                parse_mode=parse_mode,
            )
        last_error = f"Expected JSON object, got {type(parsed).__name__}"

    return JsonRepairResult(
        payload=None,
        repair_used=False,
        parse_mode="json_repair",
        error=last_error or "No JSON object found",
    )
