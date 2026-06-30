import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.main import app
from src.models.reading import ReadingMaterialHistory


@pytest.fixture
def mock_session():
    session = AsyncMock()
    added_objects = []
    session.add = MagicMock(side_effect=added_objects.append)
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


def _history(learner_id: uuid.UUID) -> ReadingMaterialHistory:
    material = ReadingMaterialHistory(
        learner_id=learner_id,
        title="How Effective Readers Work",
        text="Many students read for the main idea. Effective readers slow down for hard sentences.",
        text_hash="hash",
        level="general",
        goal="mixed",
        word_count=14,
        sentence_count=2,
        source="reading_workshop",
    )
    material.id = uuid.uuid4()
    material.created_at = datetime.now(timezone.utc)
    material.updated_at = datetime.now(timezone.utc)
    return material


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
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["learner_id"] == str(learner_id)
    assert data["title"] == "Reading Strategies"
    assert data["level"] == "cet4"
    assert data["goal"] == "mixed"
    assert data["word_count"] == 14
    assert data["sentence_count"] == 2
    created = mock_session.added_objects[0]
    assert isinstance(created, ReadingMaterialHistory)


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
async def test_list_reading_material_history_unknown_learner_returns_404(client, mock_session):
    learner_id = uuid.uuid4()
    mock_session.execute = AsyncMock(return_value=_one(None))

    response = await client.get(f"/api/learners/{learner_id}/reading-workshop/materials")

    assert response.status_code == 404
