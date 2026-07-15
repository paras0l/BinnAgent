import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

import src.api.reading as reading_api
from src.api import deps
from src.main import app
from src.models.knowledge import CurriculumNode, KnowledgePoint, KnowledgeSource
from src.models.learner import Learner, LearnerProfile
from src.models.knowledge import ExerciseAttempt
from src.models.reading import ReadingMaterialHistory
from src.providers.base import ChatRequest, ChatResponse


@pytest.fixture
def mock_session():
    session = AsyncMock()
    added_objects = []
    session.add = MagicMock(side_effect=added_objects.append)
    session.flush = AsyncMock()

    class _NestedTransaction:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    session.begin_nested = MagicMock(return_value=_NestedTransaction())

    async def _refresh(instance):
        if getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()
        if getattr(instance, "created_at", None) is None:
            instance.created_at = datetime.now(timezone.utc)
        if getattr(instance, "updated_at", None) is None:
            instance.updated_at = datetime.now(timezone.utc)

    session.refresh = AsyncMock(side_effect=_refresh)
    session.added_objects = added_objects
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _many(values: list):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def _first(value):
    result = MagicMock()
    result.first.return_value = value
    return result


def _learner(learner_id: uuid.UUID, owner_user_id: uuid.UUID) -> Learner:
    learner = Learner(nickname=f"learner-{learner_id.hex[:6]}", tenant_id=owner_user_id)
    learner.id = learner_id
    return learner


def _history(learner_id: uuid.UUID) -> ReadingMaterialHistory:
    material = ReadingMaterialHistory(
        learner_id=learner_id,
        title="How Effective Readers Work",
        text="Many students read for the main idea. Effective readers slow down for hard sentences.",
        text_hash="hash",
        level="general",
        goal="mixed",
        material_type="passage",
        word_count=14,
        sentence_count=2,
        source="reading_workshop",
        generation_context={},
    )
    material.id = uuid.uuid4()
    material.created_at = datetime.now(timezone.utc)
    material.updated_at = datetime.now(timezone.utc)
    return material


class FakeReadingModelRouter:
    async def chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            provider="fake",
            model="fake-reading",
            content=(
                '{"title":"A New Friend At School","material_type":"passage",'
                '"text":"Lily is new at school. She meets Tom in her classroom. Tom is friendly and helps Lily find the library. They talk about their teachers, their timetable, and their favorite books. After lunch, Lily feels happy because she has a kind classmate and a new friend.",'
                '"theme":"school life","grammar_focus":["be 动词"],'
                '"vocabulary_used":["friend","classmate","school","teacher"],'
                '"level_rationale":"句子较短，适合初中学习者。",'
                '"comprehension_checks":[{"question":"Who helps Lily?","answer":"Tom helps Lily."}],'
                '"confidence":0.9}'
            ),
        )


class FakeDialogueAsPassageModelRouter:
    async def chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            provider="fake",
            model="fake-reading",
            content=(
                '{"title":"A Fun Day At School","material_type":"passage",'
                '"text":"Lily: Hi, Tom! Today is a fun day at school because we have a music lesson and a library visit.\\nTom: Hi, Lily! I like music too, and I want to read a story about a clever student after lunch.\\nLily: Great! We can meet our teacher, ask questions, and talk with our new classmates.",'
                '"theme":"school life","grammar_focus":["be 动词"],'
                '"vocabulary_used":["school","teacher","classmate","library"],'
                '"level_rationale":"句子较短，适合初中学习者。",'
                '"comprehension_checks":[{"question":"Where are Lily and Tom?","answer":"They are at school."}],'
                '"confidence":0.9}'
            ),
        )


class FakeSelectionTranslationRouter:
    async def chat(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            provider="fake",
            model="fake-translation",
            content=(
                '{"translation":"为……腾出空间","context_note":'
                '"这里表示让人类有更多时间和注意力。","confidence":0.96}'
            ),
        )


@pytest.mark.asyncio
async def test_translate_reading_selection_uses_sentence_context(client, mock_session):
    learner_id = uuid.uuid4()
    mock_session.execute = AsyncMock(return_value=_one(learner_id))
    app.dependency_overrides[deps.get_model_router] = lambda: FakeSelectionTranslationRouter()

    with patch(
        "src.api.reading.get_base_dictionary_entry",
        new=AsyncMock(return_value=None),
    ):
        response = await client.post(
            f"/api/learners/{learner_id}/reading-workshop/selection-translation",
            json={
                "selection": "create space for",
                "sentence": "Good technology can create space for human attention rather than remove it.",
                "learner_level": "b1",
            },
        )

    assert response.status_code == 200
    assert response.json()["translation"] == "为……腾出空间"
    assert response.json()["confidence"] == 0.96
    assert response.json()["source"] == "model"


@pytest.mark.asyncio
async def test_translate_reading_selection_prefers_shared_dictionary(client, mock_session):
    learner_id = uuid.uuid4()
    mock_session.execute = AsyncMock(return_value=_one(learner_id))
    shared = {
        "build_version": "2026-07-12.1",
        "senses": [
            {
                "part_of_speech": "noun",
                "definition_en": "a place where books are kept",
                "definition_zh": "图书馆",
                "confidence": 0.99,
            }
        ],
    }

    with patch(
        "src.api.reading.get_base_dictionary_entry",
        new=AsyncMock(return_value=shared),
    ):
        response = await client.post(
            f"/api/learners/{learner_id}/reading-workshop/selection-translation",
            json={
                "selection": "library",
                "sentence": "Tom helps Lily find the library.",
                "learner_level": "a2",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "selection": "library",
        "translation": "图书馆",
        "context_note": "noun · a place where books are kept",
        "confidence": 0.99,
        "source": "base_dictionary",
        "build_version": "2026-07-12.1",
    }


@pytest.mark.asyncio
async def test_translate_reading_selection_rejects_text_outside_sentence(client, mock_session):
    learner_id = uuid.uuid4()
    mock_session.execute = AsyncMock(return_value=_one(learner_id))

    response = await client.post(
        f"/api/learners/{learner_id}/reading-workshop/selection-translation",
        json={"selection": "unrelated phrase", "sentence": "This is the original sentence."},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_suggest_reading_title_for_complete_material(client):
    response = await client.post(
        "/api/reading-workshop/title-suggestion",
        json={
            "text": (
                "Many students believe that reading faster simply means moving their eyes quickly across a page. "
                "However, effective readers do more than race through words. "
                "They first notice the title, predict the topic, and look for sentences that show the writer's main point."
            ),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_complete"] is True
    assert data["suggested_title"]
    assert data["word_count"] >= 30
    assert data["sentence_count"] == 3


@pytest.mark.asyncio
async def test_suggest_reading_title_keeps_incomplete_material_pending(client):
    response = await client.post(
        "/api/reading-workshop/title-suggestion",
        json={"text": "Reading faster is useful"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "is_complete": False,
        "suggested_title": None,
        "reason": "material_too_short",
        "word_count": 4,
        "sentence_count": 1,
    }


@pytest.mark.asyncio
async def test_save_reading_material_history(client, mock_session):
    learner_id = uuid.uuid4()
    mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(None)])

    response = await client.post(
        f"/api/learners/{learner_id}/reading-workshop/materials",
        json={
            "title": "  Reading Strategies  ",
            "text": "Many students read for the main idea. Effective readers slow down for hard sentences.",
            "level": "cet4",
            "goal": "mixed",
            "generation_context": {"prompt_id": "forged-client-prompt"},
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["learner_id"] == str(learner_id)
    assert data["title"] == "Reading Strategies"
    assert data["level"] == "cet4"
    assert data["goal"] == "mixed"
    assert data["material_type"] == "passage"
    assert data["word_count"] == 14
    assert data["sentence_count"] == 2
    assert data["source"] == "reading_workshop"
    assert data["generation_context"] == {}
    created = mock_session.added_objects[0]
    assert isinstance(created, ReadingMaterialHistory)


@pytest.mark.asyncio
async def test_resaving_generated_material_preserves_provenance(client, mock_session):
    learner_id = uuid.uuid4()
    original_node_id = uuid.uuid4()
    material = _history(learner_id)
    material.source = "unit_llm_generation"
    material.curriculum_node_id = original_node_id
    material.generation_context = {
        "prompt_id": "reading.material_generation",
        "prompt_version": "2.1.0",
        "source_title": "Grade 7 English",
    }
    original_generation_context = dict(material.generation_context)
    mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(material)])

    response = await client.post(
        f"/api/learners/{learner_id}/reading-workshop/materials",
        json={
            "title": "Updated reading title",
            "text": material.text,
            "level": "cet4",
            "goal": "intensive",
            "curriculum_node_id": str(uuid.uuid4()),
            "source": "reading_workshop",
            "generation_context": {"prompt_id": "forged-client-prompt"},
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "unit_llm_generation"
    assert data["curriculum_node_id"] == str(original_node_id)
    assert data["generation_context"] == original_generation_context
    assert material.source == "unit_llm_generation"
    assert material.curriculum_node_id == original_node_id
    assert material.generation_context == original_generation_context


@pytest.mark.asyncio
async def test_list_reading_material_history(client, mock_session):
    learner_id = uuid.uuid4()
    material = _history(learner_id)
    mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _many([material])])

    response = await client.get(f"/api/learners/{learner_id}/reading-workshop/materials")

    assert response.status_code == 200
    data = response.json()
    assert data[0]["id"] == str(material.id)
    assert data[0]["title"] == "How Effective Readers Work"


@pytest.mark.asyncio
async def test_list_reading_material_history_filters_by_curriculum_node(client, mock_session):
    learner_id = uuid.uuid4()
    source_id = uuid.uuid4()
    node_id = uuid.uuid4()
    source = KnowledgeSource(
        id=source_id,
        owner_learner_id=None,
        title="Grade 7 English",
        filename="book.pdf",
        publisher="PEP",
        edition="2026",
        grade="grade-7",
        volume="upper",
        status="published",
        visibility="public",
        sha256="x" * 64,
        file_size=100,
        unit_count=1,
        knowledge_count=3,
    )
    node = CurriculumNode(
        id=node_id,
        source_id=source_id,
        parent_id=None,
        node_type="unit",
        title="Unit 1",
        subtitle="Making new friends",
        ordinal=1,
    )
    material = _history(learner_id)
    material.curriculum_node_id = node_id
    mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _first((node, source)), _many([material])])

    response = await client.get(
        f"/api/learners/{learner_id}/reading-workshop/materials",
        params={"curriculum_node_id": str(node_id)},
    )

    assert response.status_code == 200
    assert response.json()[0]["curriculum_node_id"] == str(node_id)


@pytest.mark.asyncio
async def test_list_reading_material_history_unknown_learner_returns_404(client, mock_session):
    learner_id = uuid.uuid4()
    mock_session.execute = AsyncMock(return_value=_one(None))

    response = await client.get(f"/api/learners/{learner_id}/reading-workshop/materials")

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path_suffix", "payload"),
    [
        (
            "POST",
            "selection-translation",
            {"selection": "library", "sentence": "Tom visits the library."},
        ),
        ("GET", "materials", None),
        ("POST", "materials", {"text": "A short reading material."}),
        ("POST", "generated-materials", {}),
        ("POST", "materials/{material_id}/complete", {}),
    ],
)
async def test_reading_workshop_routes_reject_cross_user_access(
    client,
    mock_session,
    method,
    path_suffix,
    payload,
):
    owner_user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    learner_id = uuid.uuid4()
    material_id = uuid.uuid4()
    mock_session.execute = AsyncMock(
        return_value=_one(_learner(learner_id, owner_user_id))
    )

    response = await client.request(
        method,
        (
            f"/api/learners/{learner_id}/reading-workshop/"
            f"{path_suffix.format(material_id=material_id)}"
        ),
        headers={"X-User-Id": str(other_user_id)},
        json=payload,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_generate_unit_reading_material(client, mock_session):
    learner_id = uuid.uuid4()
    source_id = uuid.uuid4()
    node_id = uuid.uuid4()
    source = KnowledgeSource(
        id=source_id,
        owner_learner_id=None,
        title="Grade 7 English",
        filename="book.pdf",
        publisher="PEP",
        edition="2026",
        grade="grade-7",
        volume="upper",
        status="published",
        visibility="public",
        sha256="x" * 64,
        file_size=100,
        unit_count=1,
        knowledge_count=3,
    )
    node = CurriculumNode(
        id=node_id,
        source_id=source_id,
        parent_id=None,
        node_type="unit",
        title="Unit 1",
        subtitle="Making new friends",
        ordinal=1,
        learning_objectives=["Introduce yourself"],
    )
    points = [
        KnowledgePoint(
            id=uuid.uuid4(),
            source_id=source_id,
            curriculum_node_id=node_id,
            canonical_key="grammar.be",
            type="grammar",
            title="be 动词",
            summary="用 am/is/are 介绍身份。",
            source_page="1",
            content={"unit_order": 1},
        ),
        KnowledgePoint(
            id=uuid.uuid4(),
            source_id=source_id,
            curriculum_node_id=node_id,
            canonical_key="vocab.friend",
            type="vocabulary",
            title="friend",
            summary="朋友。",
            source_page="2",
            content={"unit_order": 1},
        ),
    ]
    profile = LearnerProfile(learner_id=learner_id, current_level="a2")
    mock_session.execute = AsyncMock(
        side_effect=[
            _one(learner_id),
            _first((node, source)),
            _many(points),
            _one(profile),
            _one(None),
        ]
    )
    app.dependency_overrides[deps.get_model_router] = lambda: FakeReadingModelRouter()

    response = await client.post(
        f"/api/learners/{learner_id}/reading-workshop/generated-materials",
        json={
            "curriculum_node_id": str(node_id),
            "material_type": "passage",
            "length": "short",
            "goal": "mixed",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["material"]["title"] == "A New Friend At School"
    assert data["material"]["source"] == "unit_llm_generation"
    assert data["material"]["curriculum_node_id"] == str(node_id)
    assert data["material"]["generation_context"]["grammar_focus"] == ["be 动词"]
    created_material = [item for item in mock_session.added_objects if isinstance(item, ReadingMaterialHistory)][0]
    assert created_material.material_type == "passage"


@pytest.mark.asyncio
async def test_generate_reading_material_reuses_duplicate_model_output(
    client,
    mock_session,
):
    learner_id = uuid.uuid4()
    source_id = uuid.uuid4()
    node_id = uuid.uuid4()
    source = KnowledgeSource(
        id=source_id,
        owner_learner_id=None,
        title="Grade 7 English",
        filename="book.pdf",
        grade="grade-7",
        status="published",
        visibility="public",
        sha256="x" * 64,
        file_size=100,
    )
    node = CurriculumNode(
        id=node_id,
        source_id=source_id,
        node_type="unit",
        title="Unit 1",
        ordinal=1,
    )
    profile = LearnerProfile(learner_id=learner_id, current_level="a2")

    async def execute(statement):
        sql = str(statement)
        if "reading_material_histories" in sql:
            materials = [
                item
                for item in mock_session.added_objects
                if isinstance(item, ReadingMaterialHistory)
            ]
            return _one(materials[-1] if materials else None)
        if "knowledge_points" in sql:
            return _many([])
        if "learner_profiles" in sql:
            return _one(profile)
        if "curriculum_nodes" in sql:
            return _first((node, source))
        return _one(learner_id)

    mock_session.execute = AsyncMock(side_effect=execute)
    app.dependency_overrides[deps.get_model_router] = lambda: FakeReadingModelRouter()
    payload = {
        "curriculum_node_id": str(node_id),
        "material_type": "passage",
        "length": "short",
        "goal": "mixed",
    }

    first = await client.post(
        f"/api/learners/{learner_id}/reading-workshop/generated-materials",
        json=payload,
    )
    duplicate = await client.post(
        f"/api/learners/{learner_id}/reading-workshop/generated-materials",
        json=payload,
    )

    assert first.status_code == 201
    assert duplicate.status_code == 201
    assert duplicate.json()["material"]["id"] == first.json()["material"]["id"]
    materials = [
        item for item in mock_session.added_objects if isinstance(item, ReadingMaterialHistory)
    ]
    assert len(materials) == 1


@pytest.mark.asyncio
async def test_reading_material_insert_recovers_unique_hash_race(mock_session):
    learner_id = uuid.uuid4()
    candidate = _history(learner_id)
    existing = _history(learner_id)
    existing.text_hash = candidate.text_hash
    mock_session.flush = AsyncMock(
        side_effect=IntegrityError("insert", {}, Exception("duplicate key"))
    )
    mock_session.execute = AsyncMock(return_value=_one(existing))

    resolved = await reading_api._insert_reading_material_or_get_existing(
        mock_session,
        candidate,
    )

    assert resolved is existing


@pytest.mark.asyncio
async def test_generate_passage_rejects_dialogue_format(client, mock_session):
    learner_id = uuid.uuid4()
    source_id = uuid.uuid4()
    node_id = uuid.uuid4()
    source = KnowledgeSource(
        id=source_id,
        owner_learner_id=None,
        title="Grade 7 English",
        filename="book.pdf",
        publisher="PEP",
        edition="2026",
        grade="grade-7",
        volume="upper",
        status="published",
        visibility="public",
        sha256="x" * 64,
        file_size=100,
        unit_count=1,
        knowledge_count=3,
    )
    node = CurriculumNode(
        id=node_id,
        source_id=source_id,
        parent_id=None,
        node_type="unit",
        title="Unit 1",
        subtitle="Making new friends",
        ordinal=1,
    )
    profile = LearnerProfile(learner_id=learner_id, current_level="a2")
    mock_session.execute = AsyncMock(
        side_effect=[
            _one(learner_id),
            _first((node, source)),
            _many([]),
            _one(profile),
        ]
    )
    app.dependency_overrides[deps.get_model_router] = lambda: FakeDialogueAsPassageModelRouter()

    response = await client.post(
        f"/api/learners/{learner_id}/reading-workshop/generated-materials",
        json={
            "curriculum_node_id": str(node_id),
            "material_type": "passage",
            "length": "long",
            "goal": "mixed",
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Generated passage used dialogue format"
    created_materials = [item for item in mock_session.added_objects if isinstance(item, ReadingMaterialHistory)]
    assert created_materials == []


@pytest.mark.asyncio
async def test_complete_reading_material_records_reading_attempt(client, mock_session):
    learner_id = uuid.uuid4()
    material = _history(learner_id)
    mock_session.execute = AsyncMock(
        side_effect=[_one(learner_id), _one(material), _one(None)]
    )

    response = await client.post(
        f"/api/learners/{learner_id}/reading-workshop/materials/{material.id}/complete",
        json={
            "client_attempt_id": "reading-attempt-0001",
            "duration_seconds": 240,
            "comprehension_score": 86,
            "extensive_evidence": {
                "gist": "Effective readers change speed based on the sentence.",
                "central_sentence": "Effective readers slow down for hard sentences.",
            },
            "analyzed_sentence_ids": ["reading-sentence-1", "reading-sentence-2"],
            "selected_sentence_count": 2,
            "grammar_topic_count": 1,
            "unknown_vocabulary": ["uncertainty"],
            "grammar_blind_spots": ["relative clauses"],
            "correction_notes": ["I first misunderstood the writer's attitude."],
            "perceived_difficulty": "right",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["material_id"] == str(material.id)
    created_attempt = [item for item in mock_session.added_objects if isinstance(item, ExerciseAttempt)][0]
    assert created_attempt.target_type == "reading_passage"
    assert created_attempt.result == "completed"
    assert created_attempt.correct is False
    assert created_attempt.metadata_["client_attempt_id"] == "reading-attempt-0001"
    assert created_attempt.metadata_["reading_value"] > 0
    assert created_attempt.metadata_["selected_sentence_count"] == 2
    assert created_attempt.metadata_["extensive_evidence"]["gist"].startswith(
        "Effective readers"
    )
    assert created_attempt.metadata_["unknown_vocabulary"] == ["uncertainty"]
    assert created_attempt.metadata_["grammar_blind_spots"] == ["relative clauses"]
    assert created_attempt.metadata_["perceived_difficulty"] == "right"


@pytest.mark.asyncio
async def test_complete_reading_material_is_idempotent_for_client_attempt_id(
    client,
    mock_session,
):
    learner_id = uuid.uuid4()
    material = _history(learner_id)

    async def execute(statement):
        sql = str(statement)
        if "exercise_attempts" in sql:
            attempts = [
                item for item in mock_session.added_objects if isinstance(item, ExerciseAttempt)
            ]
            return _one(attempts[-1] if attempts else None)
        if "reading_material_histories" in sql:
            return _one(material)
        return _one(learner_id)

    mock_session.execute = AsyncMock(side_effect=execute)
    payload = {
        "client_attempt_id": "reading-attempt-retry-1",
        "extensive_evidence": {
            "gist": "Effective readers change their reading speed.",
            "central_sentence": "Effective readers slow down for hard sentences.",
        },
        "analyzed_sentence_ids": ["reading-sentence-1"],
    }

    first = await client.post(
        f"/api/learners/{learner_id}/reading-workshop/materials/{material.id}/complete",
        json=payload,
    )
    retry = await client.post(
        f"/api/learners/{learner_id}/reading-workshop/materials/{material.id}/complete",
        json=payload,
    )

    assert first.status_code == 200
    assert retry.status_code == 200
    assert retry.json() == first.json()
    attempts = [item for item in mock_session.added_objects if isinstance(item, ExerciseAttempt)]
    assert len(attempts) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("goal", "payload"),
    [
        ("extensive", {}),
        ("extensive", {"notes": "A non-structured note cannot complete the stage."}),
        (
            "extensive",
            {"extensive_evidence": {"gist": "A gist", "central_sentence": "   "}},
        ),
        ("extensive", {"extensive_evidence": {"gist": "A gist"}}),
        ("intensive", {}),
        ("intensive", {"selected_sentence_count": 1}),
        ("intensive", {"analyzed_sentence_ids": ["   "]}),
        (
            "mixed",
            {
                "extensive_evidence": {
                    "gist": "A gist",
                    "central_sentence": "A central sentence.",
                }
            },
        ),
        ("mixed", {"analyzed_sentence_ids": ["reading-sentence-1"]}),
    ],
)
async def test_complete_reading_material_rejects_empty_goal_evidence(
    client,
    mock_session,
    goal,
    payload,
):
    learner_id = uuid.uuid4()
    material = _history(learner_id)
    material.goal = goal
    mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(material)])

    response = await client.post(
        f"/api/learners/{learner_id}/reading-workshop/materials/{material.id}/complete",
        json={"client_attempt_id": "reading-attempt-invalid", **payload},
    )

    assert response.status_code == 422
    assert not any(isinstance(item, ExerciseAttempt) for item in mock_session.added_objects)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sentence_ids",
    [
        ["not-a-material-sentence"],
        ["reading-sentence-3"],
        ["reading-sentence-1", " reading-sentence-1 "],
    ],
)
async def test_complete_reading_material_rejects_invalid_analyzed_sentence_ids(
    client,
    mock_session,
    sentence_ids,
):
    learner_id = uuid.uuid4()
    material = _history(learner_id)
    material.goal = "intensive"
    mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(material)])

    response = await client.post(
        f"/api/learners/{learner_id}/reading-workshop/materials/{material.id}/complete",
        json={
            "client_attempt_id": "reading-attempt-invalid-sentence",
            "analyzed_sentence_ids": sentence_ids,
        },
    )

    assert response.status_code == 422
    assert not any(isinstance(item, ExerciseAttempt) for item in mock_session.added_objects)
