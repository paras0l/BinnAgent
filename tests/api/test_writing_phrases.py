import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.main import app
from src.models.writing_phrase import WritingPhrase, WritingPhraseAttempt, WritingPhraseExercise


@pytest.fixture
def mock_session():
    session = AsyncMock()
    added_objects = []
    session.add = MagicMock(side_effect=added_objects.append)
    session.delete = AsyncMock()
    session.flush = AsyncMock()

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


def _phrase(learner_id: uuid.UUID) -> WritingPhrase:
    phrase = WritingPhrase(
        learner_id=learner_id,
        text="What is more noteworthy is that...",
        normalized_text="what is more noteworthy is that...",
        chinese_meaning="更值得注意的一点是……",
        explanation="引出更重要的补充观点。",
        usage_scene="用于第二层论证中强调重点。",
        usage_position="body",
        tags=["强调重点", "分层递进"],
        examples=[
            {
                "sentence": "What is more noteworthy is that online learning requires self-discipline.",
                "translation": "更值得注意的是，在线学习需要自律。",
            }
        ],
        notes=["后面接完整句子。"],
        mistakes=["不要直接接名词短语。"],
        source_type="manual",
        difficulty=3,
        is_favorite=True,
        is_archived=False,
        review_enabled=True,
        metadata_={},
    )
    phrase.id = uuid.uuid4()
    phrase.created_at = datetime.now(timezone.utc)
    phrase.updated_at = datetime.now(timezone.utc)
    return phrase


class TestWritingPhrases:
    @pytest.mark.asyncio
    async def test_create_phrase(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(return_value=_one(learner_id))

        response = await client.post(
            f"/api/learners/{learner_id}/writing-phrases",
            json={
                "text": "To begin with, ...",
                "chinese_meaning": "首先，……",
                "usage_scene": "用于主体段第一个理由。",
                "usage_position": "body",
                "tags": ["开头引入", "分层递进"],
                "examples": [{"sentence": "To begin with, online learning is flexible."}],
                "notes": ["比 First 更自然。"],
                "review_enabled": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["text"] == "To begin with, ..."
        assert data["normalized_text"] == "to begin with, ..."
        assert data["tags"] == ["开头引入", "分层递进"]
        created = mock_session.added_objects[0]
        assert isinstance(created, WritingPhrase)

    @pytest.mark.asyncio
    async def test_list_phrases(self, client, mock_session):
        learner_id = uuid.uuid4()
        phrase = _phrase(learner_id)
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _many([phrase])])

        response = await client.get(
            f"/api/learners/{learner_id}/writing-phrases?tag=强调重点&q=noteworthy"
        )

        assert response.status_code == 200
        data = response.json()
        assert data[0]["id"] == str(phrase.id)
        assert data[0]["review_enabled"] is True

    @pytest.mark.asyncio
    async def test_update_and_delete_phrase(self, client, mock_session):
        learner_id = uuid.uuid4()
        phrase = _phrase(learner_id)
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(phrase)])

        response = await client.patch(
            f"/api/learners/{learner_id}/writing-phrases/{phrase.id}",
            json={"is_archived": True, "tags": ["我的收藏", "强调重点"]},
        )

        assert response.status_code == 200
        assert response.json()["is_archived"] is True
        assert phrase.tags == ["我的收藏", "强调重点"]

        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(phrase)])
        delete_response = await client.delete(
            f"/api/learners/{learner_id}/writing-phrases/{phrase.id}"
        )

        assert delete_response.status_code == 204
        mock_session.delete.assert_awaited_once_with(phrase)

    @pytest.mark.asyncio
    async def test_import_extracts_candidates_from_external_model_text(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(return_value=_one(learner_id))

        response = await client.post(
            f"/api/learners/{learner_id}/writing-phrases/import",
            json={
                "source": "external_model",
                "topic": "online learning",
                "raw_text": """
1. 英文句式：What is more noteworthy is that...
中文含义：更值得注意的一点是……
句式功能：强调重点 / 分层递进
适用场景：用于引出更重要的补充观点。
适用位置：主体段中后段
例句：What is more noteworthy is that online learning requires self-discipline.
使用注意事项：后面接完整句子。
常见错误：不要直接接名词短语。
""",
            },
        )

        assert response.status_code == 200
        candidate = response.json()["candidates"][0]
        assert candidate["text"] == "What is more noteworthy is that..."
        assert "强调重点" in candidate["tags"]
        assert candidate["examples"][0]["sentence"].startswith("What is more noteworthy")

    @pytest.mark.asyncio
    async def test_generate_exercises_and_record_attempt(self, client, mock_session):
        learner_id = uuid.uuid4()
        phrase = _phrase(learner_id)
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(phrase)])

        response = await client.post(
            f"/api/learners/{learner_id}/writing-phrases/{phrase.id}/exercises",
            json={"exercise_types": ["recognition", "blank", "replacement"]},
        )

        assert response.status_code == 200
        exercises = response.json()
        assert [item["exercise_type"] for item in exercises] == [
            "recognition",
            "blank",
            "replacement",
        ]
        assert all(isinstance(item["id"], str) for item in exercises)
        assert all(isinstance(item, WritingPhraseExercise) for item in mock_session.added_objects)

        exercise = mock_session.added_objects[1]
        mock_session.added_objects.clear()
        mock_session.execute = AsyncMock(
            side_effect=[_one(learner_id), _one(phrase), _one(exercise)]
        )
        attempt_response = await client.post(
            f"/api/learners/{learner_id}/writing-phrases/{phrase.id}/attempts",
            json={
                "exercise_id": str(exercise.id),
                "exercise_type": exercise.exercise_type,
                "answer": exercise.answer,
            },
        )

        assert attempt_response.status_code == 201
        attempt = mock_session.added_objects[0]
        assert isinstance(attempt, WritingPhraseAttempt)
        assert attempt.is_correct is True
        assert attempt_response.json()["score"] == 1.0
