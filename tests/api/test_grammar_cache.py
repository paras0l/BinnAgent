import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.main import app


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value: str):
        self.values[key] = value

    async def delete(self, key: str):
        self.values.pop(key, None)


@pytest.fixture
def mock_session():
    session = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


@pytest.fixture
def fake_redis(monkeypatch):
    redis = FakeRedis()

    async def _get_redis():
        return redis

    monkeypatch.setattr("src.api.grammar.get_redis", _get_redis)
    return redis


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


class TestGrammarHtmlCache:
    @pytest.mark.asyncio
    async def test_cache_miss(self, client, mock_session, fake_redis):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(return_value=_one(learner_id))

        response = await client.get(
            f"/api/learners/{learner_id}/grammar/topics/present-for-future/html-cache",
            params={"prompt_hash": "abcdef123456", "prompt_version": "v1"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is False
        assert data["html"] is None

    @pytest.mark.asyncio
    async def test_store_and_hit_cache(self, client, mock_session, fake_redis):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(return_value=_one(learner_id))

        store_response = await client.put(
            f"/api/learners/{learner_id}/grammar/topics/present-for-future/html-cache",
            json={
                "prompt_hash": "abcdef123456",
                "prompt_version": "v1",
                "html": "<main>主将从现</main>",
                "source": "deepseek",
            },
        )

        assert store_response.status_code == 200
        assert store_response.json()["cached"] is True

        hit_response = await client.get(
            f"/api/learners/{learner_id}/grammar/topics/present-for-future/html-cache",
            params={"prompt_hash": "abcdef123456", "prompt_version": "v1"},
        )

        assert hit_response.status_code == 200
        data = hit_response.json()
        assert data["cached"] is True
        assert data["html"] == "<main>主将从现</main>"
        assert data["source"] == "deepseek"

    @pytest.mark.asyncio
    async def test_store_overwrites_cache(self, client, mock_session, fake_redis):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(return_value=_one(learner_id))
        url = f"/api/learners/{learner_id}/grammar/topics/present-for-future/html-cache"

        await client.put(
            url,
            json={
                "prompt_hash": "abcdef123456",
                "prompt_version": "v1",
                "html": "<main>old</main>",
            },
        )
        await client.put(
            url,
            json={
                "prompt_hash": "abcdef123456",
                "prompt_version": "v1",
                "html": "<main>new</main>",
            },
        )

        key = "grammar:html:v1:present-for-future:abcdef123456"
        assert json.loads(fake_redis.values[key])["html"] == "<main>new</main>"

    @pytest.mark.asyncio
    async def test_delete_cache(self, client, mock_session, fake_redis):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(return_value=_one(learner_id))
        key = "grammar:html:v1:present-for-future:abcdef123456"
        fake_redis.values[key] = json.dumps({"html": "<main>cached</main>"})

        response = await client.delete(
            f"/api/learners/{learner_id}/grammar/topics/present-for-future/html-cache",
            params={"prompt_hash": "abcdef123456", "prompt_version": "v1"},
        )

        assert response.status_code == 204
        assert key not in fake_redis.values

    @pytest.mark.asyncio
    async def test_unknown_learner_returns_404(self, client, mock_session, fake_redis):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(return_value=_one(None))

        response = await client.get(
            f"/api/learners/{learner_id}/grammar/topics/present-for-future/html-cache",
            params={"prompt_hash": "abcdef123456", "prompt_version": "v1"},
        )

        assert response.status_code == 404
