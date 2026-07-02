import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.runtime import AgentEpisode, ToolCallRecord
from src.tools.registry import ToolRegistry, build_default_tool_registry
from src.tools.types import ToolExecutionInput, ToolSpec


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


def _episode() -> AgentEpisode:
    episode = AgentEpisode(
        learner_id=uuid.uuid4(),
        source="test",
        entrypoint="tool-registry",
        status="running",
        task_spec={},
        tool_call_ids=[],
        started_at=datetime.now(timezone.utc),
    )
    episode.id = uuid.uuid4()
    episode.created_at = datetime.now(timezone.utc)
    episode.updated_at = datetime.now(timezone.utc)
    return episode


def _db_with_episode(episode):
    db = AsyncMock()
    added = []
    db.add = MagicMock(side_effect=added.append)
    db.execute = AsyncMock(return_value=FakeResult(episode))

    async def _flush():
        for item in added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()
            if getattr(item, "created_at", None) is None:
                item.created_at = datetime.now(timezone.utc)

    db.flush = AsyncMock(side_effect=_flush)
    db.added_objects = added
    return db


@pytest.mark.asyncio
async def test_register_and_execute_tool_success_records_call():
    episode = _episode()
    db = _db_with_episode(episode)
    registry = ToolRegistry(db=db)
    registry.register(
        ToolSpec(
            name="demo.echo",
            description="Echo payload",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            risk_level="low",
        ),
        lambda payload: {"echo": payload["value"]},
    )

    result = await registry.execute(
        ToolExecutionInput(
            tool_name="demo.echo",
            episode_id=str(episode.id),
            payload={"value": "ok"},
        )
    )

    assert result.status == "success"
    assert result.output == {"echo": "ok"}
    assert any(isinstance(item, ToolCallRecord) for item in db.added_objects)
    assert episode.tool_call_ids


@pytest.mark.asyncio
async def test_execute_tool_failure_records_failed_call():
    episode = _episode()
    db = _db_with_episode(episode)
    registry = ToolRegistry(db=db)
    registry.register(
        ToolSpec(
            name="demo.fail",
            description="Fail payload",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            risk_level="low",
        ),
        lambda payload: (_ for _ in ()).throw(ValueError("boom")),
    )

    result = await registry.execute(
        ToolExecutionInput(
            tool_name="demo.fail",
            episode_id=str(episode.id),
            payload={},
        )
    )

    assert result.status == "failed"
    record = next(item for item in db.added_objects if isinstance(item, ToolCallRecord))
    assert record.status == "failed"
    assert record.error == "boom"


def test_default_registry_lists_tools():
    tools = build_default_tool_registry().list_tools()

    assert "exercise.grade" in {tool.name for tool in tools}
    assert "verification.verify_episode" in {tool.name for tool in tools}
