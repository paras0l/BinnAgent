import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.explore.recommender import ExploreCapabilityRecommender
from src.explore.schemas import ExploreRecommendationContext
from src.main import app
from src.models.explore import ExploreFeaturePreference
from src.models.memory import LearningMemoryEvent
from src.models.runtime import AgentEpisode
from src.providers.base import ChatResponse


class FailingModelRouter:
    default_provider = "ollama"

    async def chat(self, request):
        raise RuntimeError("model disabled in test")


class FakeModelRouter:
    default_provider = "ollama"

    def __init__(self, payload: dict):
        self.payload = payload
        self.requests = []

    async def chat(self, request):
        self.requests.append(request)
        import json

        return ChatResponse(
            provider="fake",
            model="fake-utility",
            content=json.dumps(self.payload, ensure_ascii=False),
            structured=self.payload,
        )


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
    app.dependency_overrides[deps.get_model_router] = lambda: FailingModelRouter()
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


class TestExplorePreferences:
    @pytest.mark.asyncio
    async def test_list_preferences_empty(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _many([])])

        response = await client.get(f"/api/learners/{learner_id}/explore/preferences")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_preferences_unknown_learner_returns_404(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(return_value=_one(None))

        response = await client.get(f"/api/learners/{learner_id}/explore/preferences")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_preference_creates_favorite(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(None)])

        response = await client.put(
            f"/api/learners/{learner_id}/explore/preferences/cet-reading",
            json={"is_favorite": True, "priority": 240, "mark_used": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["learner_id"] == str(learner_id)
        assert data["feature_id"] == "cet-reading"
        assert data["is_favorite"] is True
        assert data["priority"] == 240
        assert data["last_used_at"] is not None
        created = mock_session.added_objects[0]
        assert isinstance(created, ExploreFeaturePreference)

    @pytest.mark.asyncio
    async def test_update_preference_modifies_existing(self, client, mock_session):
        learner_id = uuid.uuid4()
        preference = ExploreFeaturePreference(
            learner_id=learner_id,
            feature_id="essay-review",
            is_favorite=True,
            priority=100,
        )
        preference.id = uuid.uuid4()
        preference.created_at = datetime.now(timezone.utc)
        preference.updated_at = datetime.now(timezone.utc)
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(preference)])

        response = await client.put(
            f"/api/learners/{learner_id}/explore/preferences/essay-review",
            json={"is_favorite": False, "priority": 10},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_favorite"] is False
        assert data["priority"] == 10
        assert preference.is_favorite is False
        assert preference.priority == 10
        mock_session.add.assert_not_called()


class TestExploreCapabilities:
    @pytest.mark.asyncio
    async def test_list_explore_capabilities(self, client):
        response = await client.get("/api/explore/capabilities")

        assert response.status_code == 200
        capabilities = response.json()
        capability_ids = {item["capability_id"] for item in capabilities}
        assert {
            "grammar-explain",
            "writing-phrasebook",
            "vocab-review",
            "expression_lab",
        }.issubset(capability_ids)
        assert all(item["feature_id"] for item in capabilities)
        assert all(item["title"] for item in capabilities)
        assert all(item["category"] for item in capabilities)
        assert all(item["status"] for item in capabilities)
        vocabulary_manager = next(
            item for item in capabilities if item["capability_id"] == "vocabulary-manager"
        )
        assert vocabulary_manager["tool_target"] == "vocabulary-manager"
        expression_lab = next(
            item for item in capabilities if item["capability_id"] == "expression_lab"
        )
        assert expression_lab["feature_id"] == "expression-lab"
        assert expression_lab["status"] == "ready"

    @pytest.mark.asyncio
    async def test_old_explore_skills_endpoint_removed(self, client):
        list_response = await client.get("/api/explore/skills")
        start_response = await client.post(
            "/api/explore/skills/something/start",
            json={"learner_id": str(uuid.uuid4())},
        )

        assert list_response.status_code == 404
        assert start_response.status_code == 404

    @pytest.mark.asyncio
    async def test_start_explore_capability_creates_episode(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(return_value=_one(learner_id))

        response = await client.post(
            "/api/explore/capabilities/vocab-review/start",
            json={"learner_id": str(learner_id)},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["episode_id"]
        assert payload["status"] == "not_implemented"
        assert payload["task_spec"]["task_type"] == "practice_vocabulary"
        assert payload["task_spec"]["metadata"]["capability_id"] == "vocab-review"
        assert any(isinstance(item, AgentEpisode) for item in mock_session.added_objects)

    @pytest.mark.asyncio
    async def test_start_todo_capability_rejected(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(return_value=_one(learner_id))

        response = await client.post(
            "/api/explore/capabilities/listening-intensive/start",
            json={"learner_id": str(learner_id)},
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_recommend_capability_from_grammar_error(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _many([])])

        response = await client.post(
            f"/api/learners/{learner_id}/explore/recommendations",
            json={"grading_result": {"error_type": "grammar_rule_confusion"}},
        )

        assert response.status_code == 200
        recommendations = response.json()["recommendations"]
        assert recommendations
        assert any(item["capability_id"] == "grammar-explain" for item in recommendations)

    @pytest.mark.asyncio
    async def test_recommend_capability_from_writing_error(self, client, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _many([])])

        response = await client.post(
            f"/api/learners/{learner_id}/explore/recommendations",
            json={"grading_result": {"error_type": "low_level_connector_writing"}},
        )

        assert response.status_code == 200
        capability_ids = {item["capability_id"] for item in response.json()["recommendations"]}
        assert capability_ids & {"writing-phrasebook", "essay-review", "translation-practice"}

    @pytest.mark.asyncio
    async def test_recommendation_never_returns_unknown_capability(self, mock_session, monkeypatch):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(side_effect=[_many([])])
        recommender = ExploreCapabilityRecommender(
            mock_session,
            rerank_with_llm=True,
            model_router=FakeModelRouter({"recommendations": []}),
        )

        async def fake_llm(context, scored):
            return [
                {
                    "capability_id": "made-up-capability",
                    "reason": "bad id",
                    "priority_score": 1.0,
                }
            ]

        monkeypatch.setattr(recommender, "_call_llm_rerank", fake_llm)

        recommendations = await recommender.recommend(
            ExploreRecommendationContext(
                learner_id=learner_id,
                grading_result={"error_type": "grammar_rule_confusion"},
            )
        )

        assert recommendations
        assert all(item.capability_id != "made-up-capability" for item in recommendations)
        assert all(item.capability_id in {"grammar-explain", "daily-lesson"} or item.source in {"rule", "llm_rerank"} for item in recommendations)

    @pytest.mark.asyncio
    async def test_recommendation_filters_bare_name_from_vocabulary_tools(self, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(side_effect=[_many([])])
        recommender = ExploreCapabilityRecommender(mock_session, rerank_with_llm=False)

        recommendations = await recommender.recommend(
            ExploreRecommendationContext(
                learner_id=learner_id,
                learning_skill="vocabulary",
                grading_result={"error_type": "word_meaning spelling"},
                metadata={"target_label": "Alice", "target_type": "vocabulary_item"},
            )
        )

        capability_ids = {item.capability_id for item in recommendations}
        assert "word-roots-affixes" not in capability_ids
        assert "vocabulary-detail" not in capability_ids

    @pytest.mark.asyncio
    async def test_llm_rerank_can_drop_all_weak_candidates(self, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(side_effect=[_many([])])
        model_router = FakeModelRouter({"recommendations": []})
        recommender = ExploreCapabilityRecommender(
            mock_session,
            rerank_with_llm=True,
            model_router=model_router,
        )

        recommendations = await recommender.recommend(
            ExploreRecommendationContext(
                learner_id=learner_id,
                learning_skill="vocabulary",
                grading_result={"error_type": "word_meaning"},
                metadata={"target_label": "cake", "target_type": "vocabulary_item"},
            )
        )

        assert recommendations == []
        assert model_router.requests

    @pytest.mark.asyncio
    async def test_llm_rerank_uses_model_reason_and_score(self, mock_session):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(side_effect=[_many([])])
        model_router = FakeModelRouter(
            {
                "recommendations": [
                    {
                        "capability_id": "vocabulary-detail",
                        "priority_score": 0.93,
                        "reason": "significant 是真实高频词，适合补核心义项和例句。",
                    }
                ]
            }
        )
        recommender = ExploreCapabilityRecommender(
            mock_session,
            rerank_with_llm=True,
            model_router=model_router,
        )

        recommendations = await recommender.recommend(
            ExploreRecommendationContext(
                learner_id=learner_id,
                learning_skill="vocabulary",
                grading_result={"error_type": "word_meaning"},
                metadata={"target_label": "significant", "target_type": "vocabulary_item"},
            )
        )

        assert recommendations[0].capability_id == "vocabulary-detail"
        assert recommendations[0].priority_score == 0.93
        assert recommendations[0].source == "llm_rerank"
        assert "真实高频词" in recommendations[0].reason

    @pytest.mark.asyncio
    async def test_capability_clicked_event_writes_memory_and_updates_preference(
        self,
        client,
        mock_session,
    ):
        learner_id = uuid.uuid4()
        mock_session.execute = AsyncMock(side_effect=[_one(learner_id), _one(None)])

        response = await client.post(
            f"/api/learners/{learner_id}/explore/capabilities/grammar-explain/events",
            json={
                "event_type": "clicked",
                "recommendation_id": "caprec:test",
                "reason": "grammar mistake",
                "evidence_refs": [],
            },
        )

        assert response.status_code == 200
        assert any(isinstance(item, LearningMemoryEvent) for item in mock_session.added_objects)
        preference = next(
            item for item in mock_session.added_objects if isinstance(item, ExploreFeaturePreference)
        )
        assert preference.feature_id == "grammar-explain"
        assert preference.last_used_at is not None
