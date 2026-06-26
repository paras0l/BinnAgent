import uuid

import httpx
import pytest

from src.simulation.fixtures import BUILTIN_PERSONAS, BUILTIN_SCENARIOS
from src.simulation.runner import ScenarioRunner


@pytest.mark.asyncio
async def test_vocabulary_agent_deposit_asserts_skill_trigger_and_saved_cards():
    learner_id = str(uuid.uuid4())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/learners":
            return httpx.Response(201, json={"id": learner_id})
        if request.method == "POST" and request.url.path == "/api/chat/send":
            return httpx.Response(
                200,
                json={
                    "reply": "Saved significant and sustainable.",
                    "response": "Saved significant and sustainable.",
                    "thread_id": str(uuid.uuid4()),
                    "message_id": str(uuid.uuid4()),
                    "skill_id": "vocabulary_deposit",
                    "skill_name": "AI vocabulary deposit",
                    "skill_events": [{"status": "completed", "saved_count": 3, "skipped_count": 0}],
                },
            )
        if request.method == "GET" and request.url.path == f"/api/learners/{learner_id}/vocabulary":
            return httpx.Response(
                200,
                json=[
                    {"id": str(uuid.uuid4()), "word": "significant"},
                    {"id": str(uuid.uuid4()), "word": "sustainable"},
                    {"id": str(uuid.uuid4()), "word": "evidence"},
                ],
            )
        return httpx.Response(404, json={"detail": "not found"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    async with client:
        report = await ScenarioRunner(client).run(
            scenario=BUILTIN_SCENARIOS["vocabulary_agent_deposit"],
            persona=BUILTIN_PERSONAS["vocabulary_deposit_user"],
        )

    assert report.status == "passed"
    assert report.metrics["agent_trigger_count"] == 1
    assert report.steps[1].output["vocabulary_agent"]["saved_count"] == 3
