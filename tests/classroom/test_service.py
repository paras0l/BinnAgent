from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from src.classroom.service import load_classroom_progress, save_classroom_progress
from src.models.learning_progress import LearningProgressItem


class FakeDb:
    def __init__(self, *, node: Any = None, progress: Any = None) -> None:
        self.node = node
        self.progress = progress
        self.added: list[Any] = []
        self.flush_count = 0

    async def get(self, _model: Any, _identifier: Any) -> Any:
        return self.node

    async def scalar(self, _statement: Any) -> Any:
        return self.progress

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flush_count += 1


@pytest.mark.asyncio
async def test_save_classroom_progress_creates_learning_progress_item() -> None:
    learner_id = uuid.uuid4()
    node_id = uuid.uuid4()
    db = FakeDb(node=SimpleNamespace(title="Starter Unit 1", subtitle="Hello!"))

    result = await save_classroom_progress(
        db,
        learner_id=learner_id,
        curriculum_node_id=node_id,
        classroom_id=f"{node_id}:v1",
        current_phase_id="listen",
        completed_phase_ids=["launch", "notice", "notice"],
        flipped_card_ids=["word-0"],
        listened_cue_ids=["cue-001", "cue-001", "cue-002"],
        grammar_answers={"g1": "Good morning."},
        grammar_transfer="Good morning. I'm Emma.",
        completed=False,
    )

    assert result["status"] == "in_progress"
    assert db.flush_count == 1
    item = db.added[0]
    assert isinstance(item, LearningProgressItem)
    assert item.skill == "daily_classroom"
    assert item.metadata_["completed_phase_ids"] == ["launch", "notice"]
    assert item.metadata_["listened_cue_ids"] == ["cue-001", "cue-002"]
    assert item.metadata_["grammar_answers"] == {"g1": "Good morning."}
    assert item.metadata_["grammar_transfer"] == "Good morning. I'm Emma."


@pytest.mark.asyncio
async def test_load_classroom_progress_returns_resumable_ui_state() -> None:
    updated_at = datetime.now(UTC)
    progress = SimpleNamespace(
        status="in_progress",
        updated_at=updated_at,
        metadata_={
            "current_phase_id": "practice",
            "completed_phase_ids": ["launch", "notice", "listen"],
            "flipped_card_ids": ["word-0"],
            "listened_cue_ids": ["cue-001"],
            "grammar_answers": {"g1": "are"},
            "grammar_transfer": "They are under the desk.",
        },
    )

    result = await load_classroom_progress(
        FakeDb(progress=progress),
        learner_id=uuid.uuid4(),
        classroom_id="classroom:v1",
    )

    assert result is not None
    assert result["current_phase_id"] == "practice"
    assert result["flipped_card_ids"] == ["word-0"]
    assert result["grammar_answers"] == {"g1": "are"}
    assert result["grammar_transfer"] == "They are under the desk."
    assert result["updated_at"] == updated_at.isoformat()
