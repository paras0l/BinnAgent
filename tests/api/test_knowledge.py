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
    ExerciseAttempt,
    ExerciseQuestion,
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
            _many([source]),
            _one(source),
            _many(nodes),
            _many([]),
            _many([point]),
            _many([]),
            _many([]),
        ]
    )

    response = await client.get(f"/api/learners/{learner_id}/knowledge-base")

    assert response.status_code == 200
    data = response.json()
    assert data["source"]["title"] == "英语 七年级上册"
    assert data["sources"][0]["id"] == str(source.id)
    assert [item["ordinal"] for item in data["curriculum"]] == [1, 2]
    assert data["knowledge_points"][0]["title"] == "Good morning!"
    assert data["daily_lesson"]["estimated_minutes"] == 20
    assert data["path"][0]["status"] == "current"
    assert data["review"]["pending_count"] == 0
    assert "parser_evidence" in data


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
            _many([source]),
            _one(source),
            _many(nodes),
            _many([]),
            _many([point]),
            _many([]),
            _many([]),
        ]
    )

    response = await client.get(f"/api/learners/{learner_id}/knowledge-base?node_id={nodes[1].id}")

    assert response.status_code == 200
    assert response.json()["current_node_id"] == str(nodes[1].id)
    assert response.json()["current_unit"]["title"] == "Starter Unit 2"
    assert response.json()["knowledge_points"][0]["title"] == "What's this in English?"


@pytest.mark.asyncio
async def test_overview_can_select_source_id(client, knowledge_session):
    learner_id = uuid.uuid4()
    upper = _source()
    lower = _source()
    lower.title = "英语 七年级下册"
    lower.filename = "七年级下册.pdf"
    lower.volume = "lower"
    lower.id = uuid.uuid4()
    nodes = [_node(lower.id, 1)]
    nodes[0].title = "Unit 1"
    nodes[0].subtitle = "Can you play the guitar?"
    point = _point(lower.id, nodes[0].id)
    knowledge_session.execute = AsyncMock(
        side_effect=[
            _one(learner_id),
            _many([lower, upper]),
            _one(lower),
            _many(nodes),
            _many([]),
            _many([point]),
            _many([]),
            _many([]),
        ]
    )

    response = await client.get(
        f"/api/learners/{learner_id}/knowledge-base?source_id={lower.id}"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source"]["id"] == str(lower.id)
    assert data["source"]["volume"] == "lower"
    assert [item["title"] for item in data["sources"]] == ["英语 七年级下册", "英语 七年级上册"]


@pytest.mark.asyncio
async def test_overview_exposes_parser_review_queue(client, knowledge_session):
    learner_id = uuid.uuid4()
    source = _source()
    source.status = "review_required"
    source.metadata_ = {
        "parser": "pypdf+manifest-profile-v1",
        "parser_profile": "pep-grade7-upper-v1",
        "vocabulary_parser": "unit-sequence-with-evidence-v1",
        "rag_chunk_count": 12,
        "parser_report": {
            "warnings": ["1 vocabulary entries require review."],
            "low_confidence_entries": 1,
        },
    }
    nodes = [_node(source.id, 1)]
    point = _point(source.id, nodes[0].id)
    review_point = KnowledgePoint(
        source_id=source.id,
        curriculum_node_id=nodes[0].id,
        canonical_key="vocabulary.telephone",
        type="vocabulary",
        title="telephone",
        summary="Starter Unit 1 单元词表第 3 个词条。",
        source_page="Words and Expressions",
        status="draft",
        content={
            "origin": "unit_wordlist_sequence_parser",
            "unit_order": 3,
            "raw_line": "telephone /ˈtelɪfəʊn/",
            "confidence": 0.62,
            "warnings": ["missing_phonetic"],
            "requires_review": True,
        },
    )
    review_point.id = uuid.uuid4()
    knowledge_session.execute = AsyncMock(
        side_effect=[
            _one(learner_id),
            _many([source]),
            _one(source),
            _many(nodes),
            _many([]),
            _many([point]),
            _many([review_point]),
            _many([]),
        ]
    )

    response = await client.get(f"/api/learners/{learner_id}/knowledge-base")

    assert response.status_code == 200
    data = response.json()
    assert data["source"]["requires_review"] is True
    assert data["review"]["pending_count"] == 1
    assert data["review"]["items"][0]["raw_line"] == "telephone /ˈtelɪfəʊn/"
    assert data["review"]["items"][0]["confidence"] == 0.62
    assert data["parser_evidence"]["parser"] == "pypdf+manifest-profile-v1"
    assert data["parser_evidence"]["warnings"] == ["1 vocabulary entries require review."]


@pytest.mark.asyncio
async def test_review_knowledge_point_confirms_and_publishes(client, knowledge_session):
    learner_id = uuid.uuid4()
    source = _source()
    point = KnowledgePoint(
        source_id=source.id,
        curriculum_node_id=uuid.uuid4(),
        canonical_key="vocabulary.telephone",
        type="vocabulary",
        title="telephone",
        summary="待校对词条。",
        source_page="Words and Expressions",
        status="draft",
        content={"requires_review": True, "confidence": 0.62},
    )
    point.id = uuid.uuid4()
    source.status = "review_required"
    knowledge_session.execute = AsyncMock(
        side_effect=[_one(learner_id), _one(point), _scalar(0), _one(source)]
    )

    response = await client.patch(
        f"/api/learners/{learner_id}/knowledge-base/review-items/{point.id}",
        json={
            "action": "update",
            "title": "telephone",
            "summary": "电话；电话机。",
            "source_page": "P.104",
            "note": "按词汇表页码修正。",
        },
    )

    assert response.status_code == 200
    assert response.json()["requires_review"] is False
    assert point.status == "published"
    assert point.summary == "电话；电话机。"
    assert point.source_page == "P.104"
    assert point.content["review_decision"] == "updated"
    assert source.status == "published"


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
async def test_upload_accepts_grade8_filename(client, knowledge_session, tmp_path, monkeypatch):
    learner_id = uuid.uuid4()
    knowledge_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(None)])
    monkeypatch.setattr(settings, "knowledge_upload_dir", str(tmp_path))

    response = await client.post(
        f"/api/knowledge/sources/uploads?learner_id={learner_id}&filename=八年级英语.pdf",
        content=b"%PDF-1.7 test",
        headers={"Content-Type": "application/pdf"},
    )

    assert response.status_code == 201
    created = next(
        item for item in knowledge_session.added_objects if isinstance(item, KnowledgeSource)
    )
    assert created.grade == "grade-8"


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


@pytest.mark.asyncio
async def test_upload_does_not_reuse_private_duplicate_from_other_learner(
    client, knowledge_session, tmp_path, monkeypatch
):
    learner_id = uuid.uuid4()
    other_learner_id = uuid.uuid4()
    duplicate = KnowledgeSource(
        owner_learner_id=other_learner_id,
        title="七年级英语补充",
        filename="七年级英语补充.pdf",
        grade="grade-7",
        status="uploaded",
        visibility="private",
        sha256="b" * 64,
        file_size=10,
    )
    duplicate.id = uuid.uuid4()
    knowledge_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(None)])
    monkeypatch.setattr(settings, "knowledge_upload_dir", str(tmp_path))

    response = await client.post(
        f"/api/knowledge/sources/uploads?learner_id={learner_id}&filename=七年级英语补充.pdf",
        content=b"%PDF-1.7 same private file",
        headers={"Content-Type": "application/pdf"},
    )

    assert response.status_code == 201
    created = next(
        item for item in knowledge_session.added_objects if isinstance(item, KnowledgeSource)
    )
    assert created.owner_learner_id == learner_id
    assert created.id != duplicate.id


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


@pytest.mark.asyncio
async def test_start_unit_exercises_generates_questions(client, knowledge_session):
    learner_id = uuid.uuid4()
    source = _source()
    node = _node(source.id)
    point = _point(source.id, node.id)
    knowledge_session.execute = AsyncMock(
        side_effect=[_one(learner_id), _one(node), _many([]), _many([point])]
    )

    response = await client.post(
        f"/api/learners/{learner_id}/knowledge-base/units/{node.id}/exercises"
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["questions"]) == 8
    assert {item["question_type"] for item in payload["questions"]} == {
        "choice_context",
        "fill_blank",
        "dialogue_complete",
        "error_fix",
    }
    first_question = payload["questions"][0]
    assert first_question["target"] == {
        "type": "curriculum_node",
        "id": str(node.id),
        "label": node.title,
    }
    assert first_question["source"] == {
        "type": "curriculum",
        "name": "knowledge_base",
        "refId": first_question["id"],
    }
    assert first_question["prompt"] == first_question["stem"]
    assert first_question["correctAnswer"]
    assert point.title in first_question["options"]
    assert first_question["metadata"]["scenario"]
    assert any(isinstance(item, ExerciseQuestion) for item in knowledge_session.added_objects)


@pytest.mark.asyncio
async def test_list_exercises_for_curriculum_target_returns_unified_items(client, knowledge_session):
    learner_id = uuid.uuid4()
    source = _source()
    node = _node(source.id)
    point = _point(source.id, node.id)
    question = ExerciseQuestion(
        source_id=source.id,
        curriculum_node_id=node.id,
        knowledge_point_id=point.id,
        question_type="choice_context",
        stem="Which answer is correct?",
        options=[point.title, "Other"],
        answer=point.title,
        explanation=point.summary,
        difficulty=0.3,
        metadata_={"scenario": {"name": "Classroom"}},
    )
    question.id = uuid.uuid4()
    knowledge_session.execute = AsyncMock(
        side_effect=[_one(learner_id), _one(node), _many([question])]
    )

    response = await client.get(
        f"/api/learners/{learner_id}/exercises",
        params={"target_type": "curriculum_node", "target_id": str(node.id), "limit": 3},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(question.id),
            "target": {
                "type": "curriculum_node",
                "id": str(node.id),
                "label": node.title,
            },
            "skill": "vocabulary",
            "type": "single_choice",
            "prompt": question.stem,
            "options": [point.title, "Other"],
            "correctAnswer": point.title,
            "acceptedAnswers": [],
            "explanation": point.summary,
            "difficulty": "easy",
            "source": {
                "type": "curriculum",
                "name": "knowledge_base",
                "refId": str(question.id),
            },
            "metadata": {
                "scenario": {"name": "Classroom"},
                "knowledge_point_id": str(point.id),
                "source_id": str(source.id),
                "question_type": "choice_context",
            },
        }
    ]


@pytest.mark.asyncio
async def test_submit_exercise_attempt_records_result(client, knowledge_session):
    learner_id = uuid.uuid4()
    source = _source()
    node = _node(source.id)
    point = _point(source.id, node.id)
    question = ExerciseQuestion(
        source_id=source.id,
        curriculum_node_id=node.id,
        knowledge_point_id=point.id,
        question_type="multiple_choice",
        stem="Which answer is correct?",
        options=[point.title, "Other"],
        answer=point.title,
        explanation=point.summary,
    )
    question.id = uuid.uuid4()
    knowledge_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(question)])

    response = await client.post(
        f"/api/learners/{learner_id}/knowledge-base/exercises/{question.id}/attempts",
        json={"answer": point.title},
    )

    assert response.status_code == 200
    assert response.json()["correct"] is True
    assert response.json()["score"] == 1.0
    attempt = next(item for item in knowledge_session.added_objects if isinstance(item, ExerciseAttempt))
    assert attempt.exercise_id == str(question.id)
    assert attempt.target_type == "curriculum_node"
    assert attempt.target_id == str(question.curriculum_node_id)
    assert attempt.result == "correct"


@pytest.mark.asyncio
async def test_submit_exercise_attempt_returns_feedback_and_review_signal(client, knowledge_session):
    learner_id = uuid.uuid4()
    source = _source()
    node = _node(source.id)
    point = _point(source.id, node.id)
    question = ExerciseQuestion(
        source_id=source.id,
        curriculum_node_id=node.id,
        knowledge_point_id=point.id,
        question_type="fill_blank",
        stem="B: ______",
        options=[],
        answer="Good morning!",
        explanation="Use the greeting in context.",
        metadata_={
            "interaction": {"type": "fill_blank", "input_mode": "text", "allow_retry": True},
            "rubric": {
                "target_expression": "Good morning!",
                "acceptable_answers": ["Good morning!"],
                "error_types": ["missing_target_expression"],
                "hint": "Use the morning greeting.",
            },
        },
    )
    question.id = uuid.uuid4()
    knowledge_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(question)])

    response = await client.post(
        f"/api/learners/{learner_id}/knowledge-base/exercises/{question.id}/attempts",
        json={"answer": "Hello", "attempt_index": 0, "hint_used": 0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["correct"] is False
    assert payload["can_retry"] is True
    assert payload["hint"] == "Use the morning greeting."
    assert payload["next_review_signal"] == "urgent"
    event = next(
        item for item in knowledge_session.added_objects if isinstance(item, KnowledgeLearningEvent)
    )
    assert event.payload["error_type"] == "missing_target_expression"
    assert event.payload["next_review_signal"] == "urgent"
