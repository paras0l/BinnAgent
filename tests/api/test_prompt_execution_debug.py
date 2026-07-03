import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.config import settings
from src.main import app
from src.models.prompt_execution import PromptExecutionRecord


@pytest.fixture(autouse=True)
def debug_prompt_settings_guard():
    original = (
        settings.debug_console_enabled,
        settings.debug_console_token,
        list(settings.debug_console_allowed_origins),
    )
    yield
    (
        settings.debug_console_enabled,
        settings.debug_console_token,
        settings.debug_console_allowed_origins,
    ) = original
    app.dependency_overrides.clear()


@pytest.fixture
def mock_session():
    session = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    return session


def _count(value: int):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _rows(values: list):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _record() -> PromptExecutionRecord:
    record = PromptExecutionRecord(
        id=uuid.uuid4(),
        learner_id=uuid.uuid4(),
        episode_id=None,
        task_id="writing_phrase_import",
        source_module="writing_phrase.import",
        prompt_id="writing_phrase.import",
        prompt_version="v1",
        prompt_hash="a" * 64,
        input_hash="b" * 64,
        input_schema=None,
        output_schema="WritingPhraseImportOutput",
        model_policy_snapshot={"temperature": 0.2},
        langfuse_trace_id="trace-1",
        langfuse_observation_id="obs-1",
        schema_validation_status="fallback",
        schema_error_summary="invalid json",
        repair_used=False,
        fallback_used=True,
        parse_mode="regex_fallback",
        confidence=0.55,
        decision="review_required",
        target_type="writing_phrase",
        target_id=None,
    )
    record.created_at = datetime.now(timezone.utc)
    return record


@pytest.mark.asyncio
async def test_prompt_execution_debug_list_requires_debug_access(client, mock_session) -> None:
    settings.debug_console_enabled = False

    response = await client.get("/api/debug/prompts/executions")

    assert response.status_code == 404
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_prompt_execution_debug_list_returns_business_record_only(
    client,
    mock_session,
) -> None:
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    record = _record()
    mock_session.execute = AsyncMock(side_effect=[_count(1), _rows([record])])

    response = await client.get(
        "/api/debug/prompts/executions"
        "?prompt_id=writing_phrase.import&decision=review_required&fallback_used=true",
        headers={"X-Debug-Token": "dev"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    item = data["executions"][0]
    assert item["prompt_id"] == "writing_phrase.import"
    assert item["langfuse_trace_id"] == "trace-1"
    assert item["decision"] == "review_required"
    assert "raw_prompt" not in item
    assert "raw_output" not in item


@pytest.mark.asyncio
async def test_prompt_execution_debug_get_returns_record(client, mock_session) -> None:
    settings.debug_console_enabled = True
    settings.debug_console_token = "dev"
    record = _record()
    mock_session.execute = AsyncMock(return_value=_one(record))

    response = await client.get(
        f"/api/debug/prompts/executions/{record.id}",
        headers={"Authorization": "Bearer dev"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(record.id)
    assert response.json()["model_policy_snapshot"] == {"temperature": 0.2}
