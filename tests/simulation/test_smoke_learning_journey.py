import uuid

import httpx
import pytest

from src.simulation.fixtures import BUILTIN_PERSONAS, BUILTIN_SCENARIOS
from src.simulation.runner import ScenarioRunner


@pytest.mark.asyncio
async def test_smoke_learning_journey_generates_passing_report():
    learner_id = str(uuid.uuid4())

    async def graph_invoker(state):
        return {
            **state,
            "input_materials": [{"type": "vocabulary", "word": "morning"}],
            "agent_feedback": {"message": "Practice scheduled."},
            "memory_candidates": [{"skill": "vocabulary", "evidence": "sim"}],
            "review_items": [{"type": "word", "word": "morning"}],
            "summary": "Daily lesson completed.",
        }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/learners":
            return httpx.Response(201, json={"id": learner_id, "nickname": "sim"})
        if request.method == "POST" and request.url.path == "/api/chat/send":
            return httpx.Response(
                200,
                json={
                    "reply": "Let's practice vocabulary.",
                    "response": "Let's practice vocabulary.",
                    "thread_id": str(uuid.uuid4()),
                    "message_id": str(uuid.uuid4()),
                    "skill_events": [],
                },
            )
        if request.method == "GET" and request.url.path == f"/api/learners/{learner_id}/memory/summary":
            return httpx.Response(200, json={"learner": {"id": learner_id}, "vocabulary": {"total": 0}})
        return httpx.Response(404, json={"detail": "not found"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    async with client:
        report = await ScenarioRunner(client, graph_invoker=graph_invoker).run(
            scenario=BUILTIN_SCENARIOS["smoke_learning_journey"],
            persona=BUILTIN_PERSONAS["grade7_low_vocab"],
        )

    assert report.status == "passed"
    assert report.metrics["api_success_rate"] == 1.0
    assert report.to_dict()["steps"][-1]["evidence"] == ["daily_graph:completed"]
