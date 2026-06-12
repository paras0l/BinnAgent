import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.memory.profile_store import ProfileStore
from src.models.learner import LearnerProfile


@pytest.mark.asyncio
async def test_get_or_create_returns_profile_memory_lists() -> None:
    learner_id = uuid.uuid4()
    profile = LearnerProfile(
        learner_id=learner_id,
        target_exam="CET6",
        target_score=550,
        weak_skills=["grammar", "writing"],
        interest_topics=["technology"],
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = profile
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    data = await ProfileStore(db).get_or_create(learner_id)

    assert data["weak_skills"] == ["grammar", "writing"]
    assert data["interest_topics"] == ["technology"]


@pytest.mark.asyncio
async def test_update_weak_skills_stores_list_shape() -> None:
    learner_id = uuid.uuid4()
    profile = LearnerProfile(learner_id=learner_id)

    result = MagicMock()
    result.scalar_one_or_none.return_value = profile
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    await ProfileStore(db).update_weak_skills(learner_id, ["reading", "vocabulary"])

    assert profile.weak_skills == ["reading", "vocabulary"]
    db.commit.assert_awaited_once()
