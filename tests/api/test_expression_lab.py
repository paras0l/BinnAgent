from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from src.api import deps
from src.api import expression_lab as expression_lab_api
from src.expression_lab import service as expression_lab_service
from src.expression_lab.action_handler import ActionExecutionResult
from src.expression_lab.service import ExpressionLabError
from src.main import app


class _ApiDb:
    def __init__(self) -> None:
        self.commit_count = 0
        self.rollback_count = 0

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1


@pytest.fixture
def expression_api_context() -> SimpleNamespace:
    learner = SimpleNamespace(id=uuid.uuid4(), nickname="Alice")
    db = _ApiDb()
    app.dependency_overrides[deps.get_current_learner] = lambda: learner
    app.dependency_overrides[deps.get_db_session] = lambda: db
    app.dependency_overrides[deps.get_model_router] = lambda: object()
    yield SimpleNamespace(learner=learner, db=db)
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("input_type", "text"),
    [
        ("zh_intent", "这个观点太绝对了"),
        ("en_draft", "I am agree with you."),
        (
            "good_sentence",
            "What matters most is not speed, but consistency.",
        ),
    ],
)
@pytest.mark.asyncio
async def test_create_returns_generating_and_uses_resolved_learner_not_path_id(
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
    expression_api_context: SimpleNamespace,
    input_type: str,
    text: str,
) -> None:
    path_learner_id = uuid.uuid4()
    session_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    class FakeService:
        def __init__(self, db: Any, model_router: Any = None) -> None:
            captured["db"] = db
            captured["model_router"] = model_router

        async def create_session(self, *, learner_id: uuid.UUID, request: Any) -> Any:
            captured["learner_id"] = learner_id
            captured["request"] = request
            return SimpleNamespace(id=session_id)

    async def background(target_session_id: uuid.UUID) -> None:
        captured["background_session_id"] = target_session_id

    monkeypatch.setattr(expression_lab_api, "ExpressionLabService", FakeService)
    monkeypatch.setattr(
        expression_lab_api,
        "generate_expression_lab_session_task",
        background,
    )

    response = await client.post(
        f"/api/learners/{path_learner_id}/expression-lab/sessions",
        json={
            "input_type": input_type,
            "text": text,
            "context": "group_chat",
            "style": "polite",
            "current_level": "B1",
            "needs_practice": True,
        },
    )

    assert response.status_code == 202
    assert response.json() == {
        "session_id": str(session_id),
        "status": "generating",
    }
    assert captured["learner_id"] == expression_api_context.learner.id
    assert captured["learner_id"] != path_learner_id
    assert captured["request"].input_type == input_type
    assert captured["request"].text == text
    assert captured["background_session_id"] == session_id
    assert expression_api_context.db.commit_count == 1


@pytest.mark.asyncio
async def test_get_generating_detail_has_stable_empty_workspace_contract(
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
    expression_api_context: SimpleNamespace,
) -> None:
    session_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    captured: dict[str, Any] = {}

    class FakeService:
        def __init__(self, _db: Any, _model_router: Any = None) -> None:
            pass

        async def get_session(self, *, learner_id: uuid.UUID, session_id: uuid.UUID) -> Any:
            captured["learner_id"] = learner_id
            return SimpleNamespace(id=session_id)

        async def session_detail(self, _session: Any) -> dict[str, Any]:
            return {
                "session_id": session_id,
                "status": "generating",
                "input_type": "zh_intent",
                "input_text": "怎么委婉表达不同意见？",
                "context": "group_chat",
                "style_goal": "polite",
                "source_type": "manual",
                "source_ref": None,
                "source": {"type": "manual", "source_id": None},
                "level": "B1",
                "include_practice": True,
                "ui_spec": None,
                "actions": [],
                "attempts": [],
                "evidence": [],
                "diagnostics": {},
                "created_at": now,
                "updated_at": now,
                "completed_at": None,
            }

    monkeypatch.setattr(expression_lab_api, "ExpressionLabService", FakeService)

    response = await client.get(
        f"/api/learners/{uuid.uuid4()}/expression-lab/sessions/{session_id}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "generating"
    assert payload["ui_spec"] is None
    assert payload["actions"] == []
    assert payload["attempts"] == []
    assert payload["evidence"] == []
    assert captured["learner_id"] == expression_api_context.learner.id


@pytest.mark.asyncio
async def test_foreign_or_missing_session_returns_scoped_404_body(
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
    expression_api_context: SimpleNamespace,
) -> None:
    captured: dict[str, Any] = {}

    class MissingService:
        def __init__(self, _db: Any, _model_router: Any = None) -> None:
            pass

        async def get_session(self, *, learner_id: uuid.UUID, session_id: uuid.UUID) -> Any:
            captured["learner_id"] = learner_id
            captured["session_id"] = session_id
            raise ExpressionLabError(
                "session_not_found",
                "Session not found",
                status_code=404,
            )

    monkeypatch.setattr(expression_lab_api, "ExpressionLabService", MissingService)
    session_id = uuid.uuid4()

    response = await client.get(
        f"/api/learners/{uuid.uuid4()}/expression-lab/sessions/{session_id}"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "session_not_found",
            "message": "Session not found",
        }
    }
    assert captured["learner_id"] == expression_api_context.learner.id


@pytest.mark.asyncio
async def test_action_failure_is_a_traceable_200_result_not_a_false_save(
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
    expression_api_context: SimpleNamespace,
) -> None:
    session_id = uuid.uuid4()
    action_id = uuid.uuid4()

    class FailedActionService:
        def __init__(self, _db: Any, _model_router: Any = None) -> None:
            pass

        async def execute_action(self, **kwargs: Any) -> ActionExecutionResult:
            assert kwargs["learner_id"] == expression_api_context.learner.id
            assert kwargs["request"].confirmed is True
            return ActionExecutionResult(
                action_id=action_id,
                status="failed",
                applied_target_type=None,
                applied_target_id=None,
                payload={"error_code": "action_apply_failed"},
            )

    monkeypatch.setattr(
        expression_lab_api,
        "ExpressionLabService",
        FailedActionService,
    )

    response = await client.post(
        f"/api/learners/{uuid.uuid4()}/expression-lab/sessions/{session_id}/actions/{action_id}",
        json={"confirmed": True, "edits": {}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "action_id": str(action_id),
        "status": "failed",
        "applied_target": None,
        "applied_target_type": None,
        "applied_target_id": None,
        "payload": {"error_code": "action_apply_failed"},
    }


@pytest.mark.asyncio
async def test_retry_returns_generating_and_passes_instruction_to_background(
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
    expression_api_context: SimpleNamespace,
) -> None:
    session_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    class RetryService:
        def __init__(self, _db: Any, _model_router: Any = None) -> None:
            pass

        async def retry_generation(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return SimpleNamespace(id=session_id)

    async def retry_task(
        target_session_id: uuid.UUID,
        mode: str,
        instruction: str | None,
    ) -> None:
        captured["background"] = (target_session_id, mode, instruction)

    monkeypatch.setattr(expression_lab_api, "ExpressionLabService", RetryService)
    monkeypatch.setattr(
        expression_lab_api,
        "generate_expression_lab_session_task",
        retry_task,
    )

    response = await client.post(
        f"/api/learners/{uuid.uuid4()}/expression-lab/sessions/{session_id}/regenerate",
        json={"instruction": "更委婉一些"},
    )

    assert response.status_code == 202
    assert response.json() == {
        "session_id": str(session_id),
        "status": "generating",
    }
    assert captured["learner_id"] == expression_api_context.learner.id
    assert captured["background"] == (session_id, "retry", "更委婉一些")
    assert expression_api_context.db.commit_count == 1


@pytest.mark.asyncio
async def test_retry_background_failure_rolls_back_without_crashing_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary_db = _ApiDb()
    failed_session = SimpleNamespace(status="generating", diagnostics_json={})

    class FailureDb(_ApiDb):
        async def execute(self, _statement: Any) -> Any:
            return SimpleNamespace(scalar_one_or_none=lambda: failed_session)

    failure_db = FailureDb()
    databases = iter([primary_db, failure_db])

    class DbContext:
        def __init__(self, db: _ApiDb) -> None:
            self.db = db

        async def __aenter__(self) -> _ApiDb:
            return self.db

        async def __aexit__(self, *_args: Any) -> None:
            return None

    class FailingService:
        def __init__(self, _db: Any, _model_router: Any = None) -> None:
            pass

        async def generate_and_store(self, **_kwargs: Any) -> None:
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        expression_lab_service,
        "async_session_factory",
        lambda: DbContext(next(databases)),
    )
    monkeypatch.setattr(
        expression_lab_service,
        "ExpressionLabService",
        FailingService,
    )

    await expression_lab_service.generate_expression_lab_session_task(
        uuid.uuid4(),
        "retry",
        "provider retry",
    )

    assert primary_db.commit_count == 0
    assert primary_db.rollback_count == 1
    assert failure_db.commit_count == 1
    assert failed_session.status == "error"
    assert failed_session.diagnostics_json == {
        "error_code": "background_generation_failed",
        "retryable": True,
    }


@pytest.mark.asyncio
async def test_complete_returns_source_signal_completion_body(
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
    expression_api_context: SimpleNamespace,
) -> None:
    session_id = uuid.uuid4()
    signal_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    class CompleteService:
        def __init__(self, _db: Any, _model_router: Any = None) -> None:
            pass

        async def complete_session(self, **kwargs: Any) -> Any:
            assert kwargs["learner_id"] == expression_api_context.learner.id
            return SimpleNamespace(id=session_id)

        async def session_detail(self, _session: Any) -> dict[str, Any]:
            return {
                "session_id": session_id,
                "status": "completed",
                "input_type": "zh_intent",
                "input_text": "怎么委婉表达？",
                "context": "group_chat",
                "style_goal": "polite",
                "source_type": "group_learning_signal",
                "source_ref": str(signal_id),
                "source": {
                    "type": "group_learning_signal",
                    "source_id": str(signal_id),
                },
                "level": "B1",
                "include_practice": True,
                "ui_spec": {"version": "expression_ui.v1", "blocks": []},
                "actions": [],
                "attempts": [],
                "evidence": [{"type": "source_evidence", "id": str(signal_id)}],
                "diagnostics": {},
                "created_at": now,
                "updated_at": now,
                "completed_at": now,
            }

    monkeypatch.setattr(expression_lab_api, "ExpressionLabService", CompleteService)

    response = await client.post(
        f"/api/learners/{uuid.uuid4()}/expression-lab/sessions/{session_id}/complete"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["source"] == {
        "type": "group_learning_signal",
        "source_id": str(signal_id),
    }
    assert payload["evidence"] == [
        {"type": "source_evidence", "id": str(signal_id)}
    ]


@pytest.mark.asyncio
async def test_delete_returns_204_after_service_scoped_delete(
    client: Any,
    monkeypatch: pytest.MonkeyPatch,
    expression_api_context: SimpleNamespace,
) -> None:
    session_id = uuid.uuid4()
    captured: dict[str, Any] = {}

    class DeleteService:
        def __init__(self, _db: Any, _model_router: Any = None) -> None:
            pass

        async def delete_session(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(expression_lab_api, "ExpressionLabService", DeleteService)

    response = await client.delete(
        f"/api/learners/{uuid.uuid4()}/expression-lab/sessions/{session_id}"
    )

    assert response.status_code == 204
    assert response.content == b""
    assert captured == {
        "learner_id": expression_api_context.learner.id,
        "session_id": session_id,
    }
