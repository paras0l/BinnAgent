import uuid

import httpx
import pytest

from src.simulation.fixtures import BUILTIN_PERSONAS, BUILTIN_SCENARIOS
from src.simulation.runner import ScenarioRunner


@pytest.mark.asyncio
async def test_vocabulary_practice_adaptation_records_attempt_and_spelling_mistake():
    learner_id = str(uuid.uuid4())
    item_ids = [str(uuid.uuid4()) for _ in range(5)]
    session_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path == "/api/learners":
            return httpx.Response(201, json={"id": learner_id})
        if request.method == "POST" and path == f"/api/learners/{learner_id}/vocabulary/add":
            index = len([call for call in calls if call == "add"])
            calls.append("add")
            return httpx.Response(
                200,
                json={
                    "id": item_ids[index],
                    "word": ["morning", "telephone", "number", "friend", "significant"][index],
                    "status": "learning",
                    "confidence": 0.0,
                },
            )
        if request.method == "POST" and path == f"/api/learners/{learner_id}/vocabulary/sessions":
            is_spelling = b'"spelling"' in request.content
            return httpx.Response(
                201,
                json={
                    "session_id": session_ids[1 if is_spelling else 0],
                    "mode": "spelling" if is_spelling else "new",
                    "total": 1,
                    "current_index": 0,
                },
            )
        if request.method == "GET" and path.endswith("/next"):
            is_spelling = session_ids[1] in path
            return httpx.Response(
                200,
                json={
                    "completed": False,
                    "vocabulary_item_id": item_ids[1 if is_spelling else 0],
                    "display_word": "telephone" if is_spelling else "morning",
                    "prompt_mode": "meaning",
                },
            )
        if request.method == "POST" and path.endswith("/attempts"):
            is_spelling = session_ids[1] in path
            return httpx.Response(
                200,
                json={
                    "attempt_id": str(uuid.uuid4()),
                    "result": "incorrect" if is_spelling else "correct",
                    "correct_answer": "telephone" if is_spelling else "morning",
                    "error_type": "missing" if is_spelling else None,
                },
            )
        if request.method == "POST" and path.endswith("/advance"):
            return httpx.Response(200, json={"status": "completed", "completed": 1, "correct": 1})
        if request.method == "GET" and path.endswith("/summary"):
            return httpx.Response(200, json={"status": "completed", "completed": 1, "correct": 1})
        if request.method == "GET" and path.startswith(f"/api/learners/{learner_id}/vocabulary/"):
            is_spelling = item_ids[1] in path
            return httpx.Response(
                200,
                json={
                    "id": item_ids[1 if is_spelling else 0],
                    "word": "telephone" if is_spelling else "morning",
                    "mastery": {"recognition": 0.2, "spelling": 0.0 if is_spelling else 0.1},
                    "mistakes": (
                        [{"mistake_type": "missing", "active": True}]
                        if is_spelling
                        else []
                    ),
                },
            )
        return httpx.Response(404, json={"detail": "not found"})

    calls: list[str] = []
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    async with client:
        report = await ScenarioRunner(client).run(
            scenario=BUILTIN_SCENARIOS["vocabulary_practice_adaptation"],
            persona=BUILTIN_PERSONAS["grade7_low_vocab"],
        )

    assert report.status == "passed"
    assert report.metrics["memory_write_count"] == 2
    assert report.steps[-1].output["attempt"]["error_type"] == "missing"
