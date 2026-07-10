import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import settings
from src.knowledge import exercise_pool
from src.knowledge.exercise_pool import (
    claim_next_exercise_run,
    get_exercise_pool,
    mark_exercise_run_failed,
    process_exercise_generation_run,
)
from src.knowledge.unit_exercise_generation import UNIT_GENERATOR_VERSION
from src.models.knowledge import (
    CurriculumNode,
    ExerciseGenerationRun,
    ExerciseQuestion,
    KnowledgePoint,
)


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value
    return result


def _many(values: list):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _point(node_id: uuid.UUID, source_id: uuid.UUID) -> KnowledgePoint:
    point = KnowledgePoint(
        source_id=source_id,
        curriculum_node_id=node_id,
        canonical_key=f"phrase.{uuid.uuid4()}",
        type="phrase",
        title="Good morning!",
        summary="早晨问候",
        source_page="P.2",
        status="published",
        difficulty=0.3,
        content={"examples": ["Good morning!"]},
    )
    point.id = uuid.uuid4()
    point.created_at = datetime.now(timezone.utc)
    return point


def _question(
    node_id: uuid.UUID,
    source_id: uuid.UUID,
    point_id: uuid.UUID,
    *,
    quality: float = 0.8,
    generator_version: str = "curated-v1",
    generated: bool = False,
) -> ExerciseQuestion:
    metadata = {"source": "curated"}
    if generated:
        metadata = {
            "source_type": "generated",
            "generator_version": generator_version,
            "quality_gate": {"status": "accepted"}
            if generator_version == UNIT_GENERATOR_VERSION
            else {},
        }
    question = ExerciseQuestion(
        source_id=source_id,
        curriculum_node_id=node_id,
        knowledge_point_id=point_id,
        question_type="choice_context",
        stem=f"Question {uuid.uuid4()} with enough context?",
        options=["Good morning!", "Good night!", "Thanks!", "Bye!"],
        answer="Good morning!",
        explanation="早晨见面使用 Good morning。",
        difficulty=0.4,
        quality_score=quality,
        quality_status="accepted",
        generator_version=generator_version,
        status="published",
        metadata_=metadata,
    )
    question.id = uuid.uuid4()
    question.created_at = datetime.now(timezone.utc)
    return question


@pytest.mark.asyncio
async def test_pool_returns_curated_questions_immediately_and_queues_refill() -> None:
    source_id = uuid.uuid4()
    node_id = uuid.uuid4()
    learner_id = uuid.uuid4()
    point = _point(node_id, source_id)
    questions = [_question(node_id, source_id, point.id) for _ in range(6)]
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _many(questions),
            _one(None),
            _many([point]),
            _one(None),
        ]
    )
    added: list[object] = []
    db.add = MagicMock(side_effect=added.append)

    async def flush() -> None:
        for item in added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()

    db.flush = AsyncMock(side_effect=flush)

    pool = await get_exercise_pool(
        db,
        source_id=source_id,
        curriculum_node_id=node_id,
        learner_id=learner_id,
    )

    assert {question.id for question in pool.questions} == {question.id for question in questions}
    assert pool.status == "refreshing"
    assert pool.available_count == 6
    assert isinstance(pool.generation_run, ExerciseGenerationRun)
    assert pool.generation_run.status == "queued"
    assert pool.generation_run.requested_count == 16


@pytest.mark.asyncio
async def test_ready_pool_does_not_enqueue_more_work() -> None:
    source_id = uuid.uuid4()
    node_id = uuid.uuid4()
    point = _point(node_id, source_id)
    questions = [
        _question(
            node_id,
            source_id,
            point.id,
            generator_version=UNIT_GENERATOR_VERSION,
            generated=True,
        )
        for _ in range(settings.exercise_pool_refill_threshold)
    ]
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_many(questions), _one(None)])
    db.add = MagicMock()

    pool = await get_exercise_pool(
        db,
        source_id=source_id,
        curriculum_node_id=node_id,
        learner_id=uuid.uuid4(),
    )

    assert pool.status == "ready"
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_claim_marks_job_running_with_lease() -> None:
    run = ExerciseGenerationRun(
        source_id=uuid.uuid4(),
        curriculum_node_id=uuid.uuid4(),
        dedupe_key="dedupe",
        input_hash="a" * 64,
        generator_version=UNIT_GENERATOR_VERSION,
        status="queued",
        priority=100,
        requested_count=16,
    )
    run.id = uuid.uuid4()
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_one(run))

    claimed = await claim_next_exercise_run(db)

    assert claimed is run
    assert run.status == "running"
    assert run.attempt_count == 1
    assert run.lease_expires_at is not None


@pytest.mark.asyncio
async def test_failed_run_retries_once_then_moves_to_failed() -> None:
    run = ExerciseGenerationRun(
        source_id=uuid.uuid4(),
        curriculum_node_id=uuid.uuid4(),
        dedupe_key="dedupe",
        input_hash="a" * 64,
        generator_version=UNIT_GENERATOR_VERSION,
        status="running",
        priority=100,
        requested_count=16,
        attempt_count=1,
    )
    db = AsyncMock()

    await mark_exercise_run_failed(db, run=run, error=RuntimeError("model timeout"))
    assert run.status == "queued"
    assert run.error_message == "model timeout"

    run.status = "running"
    run.attempt_count = settings.exercise_worker_max_attempts
    await mark_exercise_run_failed(db, run=run, error=RuntimeError("still unavailable"))
    assert run.status == "failed"
    assert run.completed_at is not None


@pytest.mark.asyncio
async def test_worker_publishes_scored_questions_and_archives_unreviewed_legacy(
    monkeypatch,
) -> None:
    source_id = uuid.uuid4()
    node_id = uuid.uuid4()
    point = _point(node_id, source_id)
    node = CurriculumNode(
        source_id=source_id,
        node_type="unit",
        title="Starter Unit 1",
        ordinal=1,
    )
    node.id = node_id
    legacy = _question(
        node_id,
        source_id,
        point.id,
        generator_version="legacy-template-generator",
        generated=True,
    )
    curated = _question(node_id, source_id, point.id)
    generated = [
        _question(
            node_id,
            source_id,
            point.id,
            quality=0.91,
            generator_version=UNIT_GENERATOR_VERSION,
            generated=True,
        )
        for _ in range(8)
    ]
    run = ExerciseGenerationRun(
        source_id=source_id,
        curriculum_node_id=node_id,
        requested_by_learner_id=uuid.uuid4(),
        dedupe_key="dedupe",
        input_hash="b" * 64,
        generator_version=UNIT_GENERATOR_VERSION,
        status="running",
        priority=100,
        requested_count=8,
        attempt_count=1,
        metrics={},
    )
    run.id = uuid.uuid4()
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_one(node), _many([point]), _many([legacy, curated])])
    db.add = MagicMock()
    monkeypatch.setattr(
        exercise_pool,
        "generate_reviewed_unit_pool",
        AsyncMock(return_value=generated),
    )

    result = await process_exercise_generation_run(db, run=run, model_router=AsyncMock())

    assert result == generated
    assert run.status == "completed"
    assert run.accepted_count == 8
    assert run.metrics["average_quality_score"] == 0.91
    assert legacy.status == "archived"
    assert legacy.quality_status == "retired"
    assert curated.status == "published"
