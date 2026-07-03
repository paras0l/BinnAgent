import uuid

import pytest

from src.extraction import (
    writing_phrase_regex_fallback_payload,
    writing_phrase_result_from_payload,
)
from src.models.prompt_execution import PromptExecutionRecord
from src.prompts.executor import PromptExecutionContext, PromptExecutor


class FakeDb:
    def __init__(self) -> None:
        self.records: list[PromptExecutionRecord] = []

    def add(self, record: PromptExecutionRecord) -> None:
        self.records.append(record)

    async def flush(self) -> None:
        return None


async def _execute(raw_output: str, topic: str = "online learning"):
    db = FakeDb()
    result = await PromptExecutor(db=db).execute_with_raw_output(
        prompt_id="writing_phrase.import",
        version="v1",
        variables={"topic": topic, "task_type": "extract_phrases"},
        raw_output=raw_output,
        context=PromptExecutionContext(
            learner_id=uuid.uuid4(),
            source_module="writing_phrase.import",
            target_type="writing_phrase",
        ),
        fallback_parser=lambda value: writing_phrase_regex_fallback_payload(value, topic),
    )
    return result, db.records[0]


@pytest.mark.asyncio
async def test_writing_phrase_import_executor_accepts_valid_json_schema() -> None:
    result, record = await _execute(
        '{"candidates": [{"text": "What matters most is that...", "quality_score": 0.88}]}'
    )

    assert result.decision == "accepted"
    assert result.schema_validation_status == "passed"
    assert result.parse_mode == "json_schema"
    assert record.prompt_id == "writing_phrase.import"


@pytest.mark.asyncio
async def test_writing_phrase_import_executor_extracts_markdown_fence_json() -> None:
    result, _record = await _execute(
        '```json\n{"candidates": [{"text": "What matters most is that..."}]}\n```'
    )

    assert result.decision == "accepted"
    assert result.parse_mode == "json_schema"
    assert result.repair_used is False


@pytest.mark.asyncio
async def test_writing_phrase_import_executor_slices_explanation_json() -> None:
    result, record = await _execute(
        '整理如下：{"candidates": [{"text": "What matters most is that...", "quality_score": 0.84}]}'
    )

    assert result.decision == "accepted"
    assert result.schema_validation_status == "repaired"
    assert result.parse_mode == "json_repair"
    assert result.repair_used is True
    assert record.repair_used is True


@pytest.mark.asyncio
async def test_writing_phrase_import_executor_fallback_is_not_accepted() -> None:
    result, record = await _execute(
        """
1. 英文句式：What matters most is that...
例句：What matters most is that students build confidence.
""",
    )

    assert result.fallback_used is True
    assert result.parse_mode == "regex_fallback"
    assert result.decision != "accepted"
    assert result.decision == "review_required"
    assert record.fallback_used is True
    assert record.decision == "review_required"

    extraction_result = writing_phrase_result_from_payload(
        result.validated_output or {},
        "online learning",
        parse_mode=result.parse_mode,
        repair_used=result.repair_used,
    )
    assert extraction_result.candidates[0].parse_mode == "regex_fallback"
