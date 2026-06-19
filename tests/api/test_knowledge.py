import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.config import settings
from src.main import app
from src.models.knowledge import (
    CurriculumNode,
    KnowledgeLearningEvent,
    KnowledgePoint,
    KnowledgeSource,
    LearnerKnowledgeState,
)
from src.models.session import LearningSession, LearningTask
from src.models.vocabulary import ReviewSchedule


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _many(values: list):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _scalar(value):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


@pytest.fixture
def knowledge_session():
    session = AsyncMock()
    added: list[object] = []
    session.add = MagicMock(side_effect=added.append)

    async def flush():
        for item in added:
            if getattr(item, "id", None) is None:
                item.id = uuid.uuid4()

    session.flush = AsyncMock(side_effect=flush)
    session.added_objects = added
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


def _source() -> KnowledgeSource:
    source = KnowledgeSource(
        title="英语 七年级上册",
        filename="义务教育教科书·英语七年级上册.pdf",
        publisher="人民教育出版社（PEP）",
        edition="人教版",
        grade="grade-7",
        volume="upper",
        status="published",
        visibility="public",
        sha256="7" * 64,
        file_size=100,
        page_count=138,
        unit_count=12,
        knowledge_count=428,
    )
    source.id = uuid.uuid4()
    source.created_at = datetime.now(timezone.utc)
    return source


def _node(source_id: uuid.UUID, ordinal: int = 1) -> CurriculumNode:
    node = CurriculumNode(
        source_id=source_id,
        node_type="unit",
        title=f"Starter Unit {ordinal}",
        subtitle="Good morning!" if ordinal == 1 else "What's this in English?",
        ordinal=ordinal,
        estimated_minutes=20,
    )
    node.id = uuid.uuid4()
    return node


def _point(source_id: uuid.UUID, node_id: uuid.UUID) -> KnowledgePoint:
    point = KnowledgePoint(
        source_id=source_id,
        curriculum_node_id=node_id,
        canonical_key="phrase.good-morning",
        type="phrase",
        title="Good morning!",
        summary="用于早晨向他人问好。",
        source_page="P.2",
        status="published",
    )
    point.id = uuid.uuid4()
    point.created_at = datetime.now(timezone.utc)
    return point


@pytest.mark.asyncio
async def test_overview_returns_ordered_curriculum_and_knowledge(client, knowledge_session):
    learner_id = uuid.uuid4()
    source = _source()
    nodes = [_node(source.id, 1), _node(source.id, 2)]
    point = _point(source.id, nodes[0].id)
    knowledge_session.execute = AsyncMock(
        side_effect=[
            _one(learner_id),
            _one(source),
            _many(nodes),
            _many([]),
            _many([point]),
            _many([]),
        ]
    )

    response = await client.get(f"/api/learners/{learner_id}/knowledge-base")

    assert response.status_code == 200
    data = response.json()
    assert data["source"]["title"] == "英语 七年级上册"
    assert [item["ordinal"] for item in data["curriculum"]] == [1, 2]
    assert data["knowledge_points"][0]["title"] == "Good morning!"
    assert data["daily_lesson"]["estimated_minutes"] == 20
    assert data["path"][0]["status"] == "current"


@pytest.mark.asyncio
async def test_overview_switches_content_to_requested_curriculum_node(client, knowledge_session):
    learner_id = uuid.uuid4()
    source = _source()
    nodes = [_node(source.id, 1), _node(source.id, 2)]
    point = _point(source.id, nodes[1].id)
    point.title = "What's this in English?"
    knowledge_session.execute = AsyncMock(
        side_effect=[
            _one(learner_id),
            _one(source),
            _many(nodes),
            _many([]),
            _many([point]),
            _many([]),
        ]
    )

    response = await client.get(f"/api/learners/{learner_id}/knowledge-base?node_id={nodes[1].id}")

    assert response.status_code == 200
    assert response.json()["current_node_id"] == str(nodes[1].id)
    assert response.json()["current_unit"]["title"] == "Starter Unit 2"
    assert response.json()["knowledge_points"][0]["title"] == "What's this in English?"


@pytest.mark.asyncio
async def test_start_lesson_persists_session_and_tasks(client, knowledge_session):
    learner_id = uuid.uuid4()
    source = _source()
    node = _node(source.id)
    point = _point(source.id, node.id)
    knowledge_session.execute = AsyncMock(
        side_effect=[
            _one(learner_id),
            _one(node),
            _many([point]),
            _scalar(source),
            _many([]),
        ]
    )

    response = await client.post(
        f"/api/learners/{learner_id}/knowledge-base/lessons/{node.id}/start"
    )

    assert response.status_code == 201
    assert response.json()["knowledge_points"][0]["id"] == str(point.id)
    assert response.json()["vocabulary_enrollment"]["total"] == 0
    assert sum(isinstance(item, LearningSession) for item in knowledge_session.added_objects) == 1
    assert sum(isinstance(item, LearningTask) for item in knowledge_session.added_objects) == 3


@pytest.mark.asyncio
async def test_complete_lesson_marks_session_and_tasks_and_recommends_next(
    client, knowledge_session
):
    learner_id = uuid.uuid4()
    source = _source()
    current_node = _node(source.id, 1)
    next_node = _node(source.id, 2)
    session = LearningSession(
        learner_id=learner_id,
        session_type="textbook_lesson",
        active_skill="knowledge",
        status="in_progress",
    )
    session.id = uuid.uuid4()
    tasks = [
        LearningTask(
            learner_id=learner_id,
            session_id=session.id,
            task_type="textbook_knowledge",
            skill="knowledge",
            title="知识讲解",
            status="pending",
            input_ref=f"curriculum:{current_node.id}",
        )
    ]
    knowledge_session.execute = AsyncMock(
        side_effect=[
            _one(learner_id),
            _one(session),
            _many(tasks),
            _one(current_node),
            _one(next_node),
        ]
    )

    response = await client.post(
        f"/api/learners/{learner_id}/knowledge-base/lessons/{session.id}/complete"
    )

    assert response.status_code == 200
    assert response.json()["next_node_id"] == str(next_node.id)
    assert session.status == "completed"
    assert session.completed_at is not None
    assert tasks[0].status == "completed"


@pytest.mark.asyncio
async def test_attempt_updates_mastery_and_writes_memory_events(client, knowledge_session):
    learner_id = uuid.uuid4()
    source = _source()
    node = _node(source.id)
    point = _point(source.id, node.id)
    knowledge_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(point), _one(None)])

    response = await client.post(
        f"/api/learners/{learner_id}/knowledge-base/attempts",
        json={"knowledge_point_id": str(point.id), "correct": True, "hint_count": 0},
    )

    assert response.status_code == 200
    assert response.json()["mastery_score"] == pytest.approx(0.18)
    assert any(isinstance(item, LearnerKnowledgeState) for item in knowledge_session.added_objects)
    assert any(isinstance(item, KnowledgeLearningEvent) for item in knowledge_session.added_objects)
    assert any(isinstance(item, ReviewSchedule) for item in knowledge_session.added_objects)


@pytest.mark.asyncio
async def test_upload_rejects_non_grade7_filename(client, knowledge_session):
    learner_id = uuid.uuid4()
    knowledge_session.execute = AsyncMock(return_value=_one(learner_id))

    response = await client.post(
        f"/api/knowledge/sources/uploads?learner_id={learner_id}&filename=八年级英语.pdf",
        content=b"%PDF-1.7 test",
        headers={"Content-Type": "application/pdf"},
    )

    assert response.status_code == 422
    assert "七年级" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_stores_grade7_pdf(client, knowledge_session, tmp_path, monkeypatch):
    learner_id = uuid.uuid4()
    knowledge_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(None)])
    monkeypatch.setattr(settings, "knowledge_upload_dir", str(tmp_path))

    response = await client.post(
        f"/api/knowledge/sources/uploads?learner_id={learner_id}&filename=七年级英语补充.pdf",
        content=b"%PDF-1.7 textbook",
        headers={"Content-Type": "application/pdf"},
    )

    assert response.status_code == 201
    created = next(
        item for item in knowledge_session.added_objects if isinstance(item, KnowledgeSource)
    )
    assert created.grade == "grade-7"
    assert created.status == "uploaded"
    assert Path(created.object_key).exists()


def test_knowledge_migration_creates_source_graph_and_memory_tables() -> None:
    migration = Path("alembic/versions/b2c3d4e5f6a7_add_grade7_knowledge_base.py").read_text()
    for table in [
        "knowledge_sources",
        "curriculum_nodes",
        "knowledge_points",
        "learner_knowledge_states",
        "knowledge_learning_events",
    ]:
        assert table in migration
    assert "英语 七年级上册" in migration
