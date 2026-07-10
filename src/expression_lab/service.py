from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import async_session_factory
from src.exercises.attempt_service import (
    ExerciseAttemptCreate,
    ExerciseAttemptService,
    ExerciseTarget,
)
from src.expression_lab.action_handler import (
    ActionExecutionResult,
    ExpressionLabActionHandler,
    editable_fields_for_action,
)
from src.expression_lab.schemas import (
    ActionRequest,
    AttemptRequest,
    AttemptResponse,
    CreateSessionRequest,
    EventRequest,
)
from src.expression_lab.ui_spec_generator import ExpressionUiSpecGenerator, GenerationOutcome
from src.memory.schemas import MemoryEventInput
from src.memory.writer import MemoryWriter
from src.models.expression_lab import (
    ExpressionLabAction,
    ExpressionLabAttempt,
    ExpressionLabEvent,
    ExpressionLabSession,
)
from src.models.group_learning import (
    GroupLearningMessage,
    GroupLearningSignal,
    GroupLearningSource,
)
from src.models.runtime import AgentEpisode
from src.providers.router import ModelRouter, router as global_model_router
from src.runtime.episode import EpisodeRuntime
from src.runtime.task_spec import (
    SuccessCriteria,
    TaskSpec,
    TaskTarget,
    VerificationPolicy,
)


SOURCE_SIGNAL_TYPES = frozenset(
    {
        "expression_gap",
        "grammar_error",
        "good_sentence",
        "desired_vocabulary",
        "desired_grammar",
    }
)
ACTIVE_SESSION_STATUSES = frozenset({"generating", "ready", "partial", "error"})


class ExpressionLabError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class ExpressionLabService:
    def __init__(self, db: AsyncSession, model_router: ModelRouter | None = None) -> None:
        self.db = db
        self.model_router = model_router or global_model_router

    async def create_session(
        self,
        *,
        learner_id: uuid.UUID,
        request: CreateSessionRequest,
    ) -> ExpressionLabSession:
        session_id = uuid.uuid4()
        source_type = "manual"
        source_ref: str | None = None
        source_snapshot: dict[str, Any] = {}
        if request.source_signal_id is not None:
            source_type = "group_learning_signal"
            source_ref = str(request.source_signal_id)
            source_snapshot = await self._source_signal_snapshot(
                learner_id, request.source_signal_id
            )

        task_spec = TaskSpec(
            task_id=f"expression-lab:{session_id}",
            task_type="expression_lab",
            source=source_type,
            objective="比较、理解、练习并按用户确认保存英语表达",
            target=TaskTarget(
                target_type="expression_lab_session",
                target_id=str(session_id),
                label=request.text[:120],
                metadata={"input_type": request.input_type},
            ),
            difficulty=request.current_level,
            required_inputs=["input_text", "input_type"],
            expected_output={"schema": "expression_ui.v1", "practice": request.needs_practice},
            allowed_tools=["writing_phrase", "vocabulary", "grammar", "exercise_attempt"],
            success_criteria=SuccessCriteria(
                requires_explanation=True,
                required_outputs=["expression_variants", "learning_actions"],
            ),
            verification_policy=VerificationPolicy(
                required_checks=["schema", "renderer_policy", "action_confirmation"],
                allow_llm_judge=False,
                require_evidence=True,
            ),
            metadata={"context": request.context, "style_goal": request.style},
        )
        episode = await EpisodeRuntime(self.db).create_episode(
            learner_id=learner_id,
            source="expression_lab",
            entrypoint="expression_lab.create_session",
            task_spec=task_spec,
            context_snapshot={
                "input_type": request.input_type,
                "context": request.context,
                "style_goal": request.style,
                "source": source_snapshot,
            },
            status="running",
        )
        session = ExpressionLabSession(
            id=session_id,
            learner_id=learner_id,
            episode_id=episode.id,
            source_type=source_type,
            source_ref=source_ref,
            source_snapshot=source_snapshot,
            input_type=request.input_type,
            input_text=request.text,
            context=request.context,
            style_goal=request.style,
            current_level=request.current_level,
            needs_practice=request.needs_practice,
            status="generating",
            ui_spec_json={},
            grading_spec_json={},
            diagnostics_json={},
            generation_attempts=0,
        )
        self.db.add(session)
        await self.db.flush()
        await self._record_event(session, "session_created", {"source_type": source_type})
        return session

    async def list_sessions(
        self, *, learner_id: uuid.UUID, limit: int = 20
    ) -> tuple[list[ExpressionLabSession], int]:
        result = await self.db.execute(
            select(ExpressionLabSession)
            .where(ExpressionLabSession.learner_id == learner_id)
            .order_by(ExpressionLabSession.updated_at.desc())
            .limit(max(1, min(limit, 50)))
        )
        pending_result = await self.db.execute(
            select(func.count(ExpressionLabSession.id)).where(
                ExpressionLabSession.learner_id == learner_id,
                ExpressionLabSession.status.in_(["generating", "ready", "partial"]),
            )
        )
        return list(result.scalars().all()), int(pending_result.scalar_one() or 0)

    async def get_session(
        self,
        *,
        learner_id: uuid.UUID,
        session_id: uuid.UUID,
        for_update: bool = False,
    ) -> ExpressionLabSession:
        statement = select(ExpressionLabSession).where(
            ExpressionLabSession.id == session_id,
            ExpressionLabSession.learner_id == learner_id,
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.db.execute(statement)
        session = result.scalar_one_or_none()
        if session is None:
            raise ExpressionLabError("session_not_found", "Session not found", status_code=404)
        return session

    async def generate_and_store(
        self,
        *,
        session_id: uuid.UUID,
        mode: str = "full",
        instruction: str | None = None,
    ) -> ExpressionLabSession:
        result = await self.db.execute(
            select(ExpressionLabSession)
            .where(ExpressionLabSession.id == session_id)
            .with_for_update()
        )
        session = result.scalar_one_or_none()
        if session is None:
            raise ExpressionLabError("session_not_found", "Session not found", status_code=404)
        session.generation_attempts = (session.generation_attempts or 0) + 1
        outcome = await ExpressionUiSpecGenerator(self.db, self.model_router).generate(
            session,
            mode=mode,  # type: ignore[arg-type]
            instruction=instruction,
        )
        await self._apply_generation_outcome(session, outcome, replace_actions=True)
        return session

    async def retry_generation(
        self,
        *,
        learner_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> ExpressionLabSession:
        session = await self.get_session(
            learner_id=learner_id, session_id=session_id, for_update=True
        )
        if session.status == "completed":
            raise ExpressionLabError(
                "session_completed", "Completed sessions cannot be regenerated", status_code=409
            )
        session.status = "generating"
        session.diagnostics_json = {"retry_requested": True}
        await self._record_event(session, "generation_retried", {})
        return session

    async def regenerate_block(
        self,
        *,
        learner_id: uuid.UUID,
        session_id: uuid.UUID,
        block_id: str,
        instruction: str | None = None,
    ) -> ExpressionLabSession:
        session = await self.get_session(
            learner_id=learner_id, session_id=session_id, for_update=True
        )
        if session.status not in {"ready", "partial"}:
            raise ExpressionLabError(
                "session_not_ready", "Session is not ready for block regeneration", status_code=409
            )
        current_blocks = list((session.ui_spec_json or {}).get("blocks") or [])
        old_index = next(
            (index for index, block in enumerate(current_blocks) if block.get("id") == block_id),
            None,
        )
        if old_index is None:
            raise ExpressionLabError("block_not_found", "Block not found", status_code=404)
        outcome = await ExpressionUiSpecGenerator(self.db, self.model_router).generate(
            session,
            mode="regenerate_block",
            block_id=block_id,
            instruction=instruction,
        )
        candidate_blocks = outcome.ui_spec.get("blocks") or []
        replacement = next(
            (block for block in candidate_blocks if block.get("id") == block_id),
            candidate_blocks[0] if candidate_blocks else None,
        )
        if replacement is None:
            raise ExpressionLabError(
                "block_regeneration_failed", "Block could not be regenerated", status_code=422
            )
        replacement = {**replacement, "id": block_id}
        current_blocks[old_index] = replacement
        merged_ui = {**(session.ui_spec_json or {}), "blocks": current_blocks}
        generated_actions = []
        for action in outcome.ui_spec.get("learning_actions") or []:
            action_copy = dict(action)
            if action_copy.get("block_id") in {block_id, replacement.get("id")}:
                action_copy["block_id"] = block_id
                generated_actions.append(action_copy)
        previous_actions = [
            action
            for action in (session.ui_spec_json or {}).get("learning_actions") or []
            if action.get("block_id") != block_id
        ]
        merged_ui["learning_actions"] = [*previous_actions, *generated_actions]
        merged_grading = dict(session.grading_spec_json or {})
        new_grading = next(iter(outcome.grading_spec.values()), {})
        merged_grading[block_id] = new_grading
        session.ui_spec_json = merged_ui
        session.grading_spec_json = merged_grading
        session.status = outcome.status
        session.diagnostics_json = {
            **(session.diagnostics_json or {}),
            "last_block_regeneration": outcome.diagnostics,
        }
        await self._materialize_actions(session, generated_actions, block_id=block_id)
        await self._record_event(
            session, "block_regenerated", {"block_id": block_id, "instruction": instruction}
        )
        return session

    async def submit_attempt(
        self,
        *,
        learner_id: uuid.UUID,
        session_id: uuid.UUID,
        request: AttemptRequest,
    ) -> AttemptResponse:
        session = await self.get_session(
            learner_id=learner_id, session_id=session_id, for_update=True
        )
        if session.status not in {"ready", "partial"}:
            raise ExpressionLabError(
                "session_not_ready", "Session is not ready for practice", status_code=409
            )
        question = self._question(session, request.block_id, request.question_id)
        grading = (
            (session.grading_spec_json or {}).get(request.block_id, {}).get(request.question_id)
        )
        if not isinstance(grading, dict):
            raise ExpressionLabError(
                "grading_key_not_found", "Practice grading key not found", status_code=404
            )
        submitted = _answer_text(request.answer)
        grade = _grade_answer(submitted, grading)
        count_result = await self.db.execute(
            select(func.count(ExpressionLabAttempt.id)).where(
                ExpressionLabAttempt.session_id == session.id,
                ExpressionLabAttempt.block_id == request.block_id,
                ExpressionLabAttempt.question_id == request.question_id,
            )
        )
        attempt_number = int(count_result.scalar_one() or 0) + 1
        next_recommendations = _next_recommendations(
            grade["is_correct"], request.block_id, request.question_id, attempt_number
        )
        skill = str(grading.get("skill") or question.get("skill") or "writing")
        target_type = {
            "grammar": "grammar_topic",
            "vocabulary": "vocabulary",
        }.get(skill, "writing_phrase")
        exercise_attempt = await ExerciseAttemptService(self.db).save_attempt(
            learner_id,
            ExerciseAttemptCreate(
                exercise_id=f"expression-lab:{session.id}:{request.block_id}:{request.question_id}",
                target=ExerciseTarget(
                    type=target_type,  # type: ignore[arg-type]
                    id=f"{session.id}:{request.question_id}",
                    label=str(question.get("prompt") or "Expression Lab practice")[:255],
                ),
                answer=submitted,
                result="correct" if grade["is_correct"] else "incorrect",
                response_time_ms=request.response_time_ms,
                metadata={
                    "score": grade["score"],
                    "expression_lab_session_id": str(session.id),
                    "block_id": request.block_id,
                    "question_id": request.question_id,
                    "attempt_number": attempt_number,
                },
                source_context={
                    "source": "expression_lab",
                    "session_id": str(session.id),
                    "input_type": session.input_type,
                    "source_signal_id": session.source_ref,
                },
                should_update_mastery=True,
                should_create_error_pattern=not grade["is_correct"],
                should_create_memory_evidence=True,
            ),
        )
        feedback = {
            "message": grade["feedback"],
            "hint": grading.get("hint") if not grade["is_correct"] else None,
            "explanation": grading.get("explanation"),
            "can_retry": not grade["is_correct"] and attempt_number < 3,
            "expected_answer": grading.get("answer"),
        }
        answer_json = request.answer if isinstance(request.answer, dict) else {"value": request.answer}
        attempt = ExpressionLabAttempt(
            session_id=session.id,
            exercise_attempt_id=exercise_attempt.id,
            block_id=request.block_id,
            question_id=request.question_id,
            answer_json=answer_json,
            score=grade["score"],
            is_correct=grade["is_correct"],
            feedback_json=feedback,
            next_recommendations=next_recommendations,
            attempt_number=attempt_number,
            response_time_ms=request.response_time_ms,
        )
        self.db.add(attempt)
        await self.db.flush()
        event_payload = {
            "attempt_id": str(attempt.id),
            "exercise_attempt_id": str(exercise_attempt.id),
            "block_id": request.block_id,
            "question_id": request.question_id,
            "attempt_number": attempt_number,
            "score": grade["score"],
            "is_correct": grade["is_correct"],
            "skill": skill,
        }
        await self._record_event(session, "practice_submitted", event_payload)
        await MemoryWriter(self.db).record_event(
            MemoryEventInput(
                learner_id=learner_id,
                event_type="expression_lab_practice_submitted",
                skill=skill,
                source_type="expression_lab_session",
                source_id=str(session.id),
                payload={**event_payload, "input_type": session.input_type},
                confidence=0.95,
                created_by="user",
            )
        )
        return AttemptResponse(
            attempt_id=attempt.id,
            score=grade["score"],
            is_correct=grade["is_correct"],
            feedback=feedback,
            next_recommendations=next_recommendations,
        )

    async def execute_action(
        self,
        *,
        learner_id: uuid.UUID,
        session_id: uuid.UUID,
        action_id: uuid.UUID,
        request: ActionRequest,
    ) -> ActionExecutionResult:
        session = await self.get_session(learner_id=learner_id, session_id=session_id)
        handler = ExpressionLabActionHandler(
            self.db,
            create_practice=self._create_practice_action,
            mark_completed=self._mark_completed_action,
        )
        return await handler.execute(session=session, action_id=action_id, request=request)

    async def complete_session(
        self,
        *,
        learner_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> ExpressionLabSession:
        session = await self.get_session(
            learner_id=learner_id, session_id=session_id, for_update=True
        )
        await self._complete(session)
        # Server-side ``updated_at`` values are expired by the flushes performed while
        # completing the linked episode. Refresh inside the async context so response
        # serialization never triggers an implicit (and invalid) lazy load.
        await self.db.refresh(session)
        return session

    async def record_client_event(
        self,
        *,
        learner_id: uuid.UUID,
        session_id: uuid.UUID,
        request: EventRequest,
    ) -> None:
        session = await self.get_session(learner_id=learner_id, session_id=session_id)
        payload = _bounded_event_payload(request.payload)
        await self._record_event(session, request.event_type, payload)

    async def delete_session(
        self,
        *,
        learner_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> None:
        session = await self.get_session(
            learner_id=learner_id, session_id=session_id, for_update=True
        )
        episode_id = session.episode_id
        await self.db.delete(session)
        await self.db.flush()
        if episode_id is not None:
            await self.db.execute(delete(AgentEpisode).where(AgentEpisode.id == episode_id))

    async def session_detail(self, session: ExpressionLabSession) -> dict[str, Any]:
        actions_result = await self.db.execute(
            select(ExpressionLabAction)
            .where(ExpressionLabAction.session_id == session.id)
            .order_by(ExpressionLabAction.created_at.asc())
        )
        attempts_result = await self.db.execute(
            select(ExpressionLabAttempt)
            .where(ExpressionLabAttempt.session_id == session.id)
            .order_by(ExpressionLabAttempt.created_at.asc())
        )
        source = _source_view(session)
        evidence = _evidence_view(session.source_snapshot or {})
        return {
            "session_id": session.id,
            "status": session.status,
            "input_type": session.input_type,
            "input_text": session.input_text,
            "context": session.context,
            "style_goal": session.style_goal,
            "source_type": session.source_type,
            "source_ref": session.source_ref,
            "source": source,
            "level": session.current_level,
            "current_level": session.current_level,
            "include_practice": session.needs_practice,
            "needs_practice": session.needs_practice,
            "ui_spec": session.ui_spec_json or None,
            "actions": [_action_view(row) for row in actions_result.scalars().all()],
            "attempts": [_attempt_view(row) for row in attempts_result.scalars().all()],
            "evidence": evidence,
            "diagnostics": session.diagnostics_json or {},
            "error_message": (
                "本次生成未完成，可以保留输入后重试。"
                if session.status == "error"
                else None
            ),
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "completed_at": session.completed_at,
        }

    async def _apply_generation_outcome(
        self,
        session: ExpressionLabSession,
        outcome: GenerationOutcome,
        *,
        replace_actions: bool,
    ) -> None:
        session.status = outcome.status
        session.ui_spec_json = _ensure_system_actions(outcome.ui_spec)
        session.grading_spec_json = outcome.grading_spec
        session.diagnostics_json = outcome.diagnostics
        session.model_id = outcome.model_id
        session.prompt_id = outcome.prompt_id
        session.prompt_version = outcome.prompt_version
        session.prompt_hash = outcome.prompt_hash
        actions = list(session.ui_spec_json.get("learning_actions") or [])
        await self._materialize_actions(
            session, actions, supersede_missing=replace_actions
        )
        await self._record_event(
            session,
            "ui_generated",
            {
                "status": outcome.status,
                "block_count": len(outcome.ui_spec.get("blocks") or []),
                "action_count": len(actions),
                "fallback_stage": outcome.diagnostics.get("fallback_stage"),
            },
        )

    async def _materialize_actions(
        self,
        session: ExpressionLabSession,
        actions: list[dict[str, Any]],
        *,
        block_id: str | None = None,
        supersede_missing: bool = False,
    ) -> None:
        existing_result = await self.db.execute(
            select(ExpressionLabAction).where(ExpressionLabAction.session_id == session.id)
        )
        existing = {row.spec_action_id: row for row in existing_result.scalars().all()}
        incoming_ids: set[str] = set()
        save_types = {"save_writing_phrase", "save_vocabulary", "save_grammar_point"}
        for proposed in actions:
            spec_action_id = str(proposed.get("id") or "")[:120]
            if not spec_action_id:
                continue
            incoming_ids.add(spec_action_id)
            action_type = str(proposed.get("type") or "")
            server_editable = set(editable_fields_for_action(action_type))
            declared_editable = {
                str(field) for field in proposed.get("editable_fields") or []
            }
            system_editable = sorted(server_editable.intersection(declared_editable))
            row = existing.get(spec_action_id)
            if row is None:
                row = ExpressionLabAction(
                    session_id=session.id,
                    block_id=block_id or proposed.get("block_id"),
                    spec_action_id=spec_action_id,
                    action_type=action_type,
                    label=str(proposed.get("label") or "继续")[:160],
                    payload_json=dict(proposed.get("payload") or {}),
                    editable_fields=system_editable,
                    requires_confirmation=(
                        action_type in save_types or bool(proposed.get("requires_confirmation"))
                    ),
                    status="pending",
                    confirmed_by_user=False,
                )
                self.db.add(row)
                existing[spec_action_id] = row
            elif row.status in {"pending", "failed", "superseded"}:
                row.block_id = block_id or proposed.get("block_id")
                row.action_type = action_type
                row.label = str(proposed.get("label") or row.label)[:160]
                row.payload_json = dict(proposed.get("payload") or {})
                row.editable_fields = system_editable
                row.requires_confirmation = action_type in save_types or bool(
                    proposed.get("requires_confirmation")
                )
                row.status = "pending"
                row.failure_code = None
                row.failure_summary = None
        if supersede_missing:
            for spec_action_id, row in existing.items():
                if row.status == "pending" and spec_action_id not in incoming_ids:
                    row.status = "superseded"
        elif block_id is not None:
            for spec_action_id, row in existing.items():
                if (
                    row.status == "pending"
                    and row.block_id == block_id
                    and spec_action_id not in incoming_ids
                ):
                    row.status = "superseded"
        await self.db.flush()

    async def _create_practice_action(
        self,
        session: ExpressionLabSession,
        action: ExpressionLabAction,
        payload: dict[str, Any],
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        outcome = await ExpressionUiSpecGenerator(self.db, self.model_router).generate(
            session,
            mode="practice_only",
            instruction=f"生成 {payload.get('count', 1)} 道练习；focus={payload.get('focus', '')}",
        )
        practice = next(
            (
                block
                for block in outcome.ui_spec.get("blocks") or []
                if block.get("type") == "micro_practice"
            ),
            None,
        )
        if practice is None:
            raise ExpressionLabError(
                "practice_generation_failed", "Practice could not be generated", status_code=422
            )
        new_block_id = f"practice-{uuid.uuid4().hex[:12]}"
        old_block_id = str(practice.get("id"))
        practice = {**practice, "id": new_block_id}
        ui = dict(session.ui_spec_json or {})
        ui["blocks"] = [*(ui.get("blocks") or []), practice]
        new_actions = []
        for proposed in outcome.ui_spec.get("learning_actions") or []:
            if proposed.get("block_id") == old_block_id:
                new_actions.append({**proposed, "block_id": new_block_id})
        ui["learning_actions"] = [*(ui.get("learning_actions") or []), *new_actions]
        session.ui_spec_json = ui
        grading = dict(session.grading_spec_json or {})
        grading[new_block_id] = outcome.grading_spec.get(old_block_id, {})
        session.grading_spec_json = grading
        await self._materialize_actions(session, new_actions, block_id=new_block_id)
        await self._record_event(
            session,
            "practice_created",
            {"block_id": new_block_id, "source_action_id": str(action.id)},
        )
        return "expression_lab_block", new_block_id, {"block": practice}

    async def _mark_completed_action(
        self,
        session: ExpressionLabSession,
        _action: ExpressionLabAction,
        _payload: dict[str, Any],
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        await self._complete(session)
        return "expression_lab_session", str(session.id), {"completed": True}

    async def _complete(self, session: ExpressionLabSession) -> None:
        if session.status == "completed":
            return
        if session.status not in {"ready", "partial", "error"}:
            raise ExpressionLabError(
                "session_not_completable", "Session cannot be completed yet", status_code=409
            )
        now = datetime.now(timezone.utc)
        session.status = "completed"
        session.completed_at = now
        if session.source_type == "group_learning_signal" and session.source_ref:
            try:
                signal_id = uuid.UUID(session.source_ref)
            except ValueError:
                signal_id = None
            if signal_id is not None:
                signal_result = await self.db.execute(
                    select(GroupLearningSignal)
                    .where(
                        GroupLearningSignal.id == signal_id,
                        GroupLearningSignal.learner_id == session.learner_id,
                    )
                    .with_for_update()
                )
                signal = signal_result.scalar_one_or_none()
                if signal is not None:
                    signal.status = "accepted"
                    signal.applied_target_type = "expression_lab_session"
                    signal.applied_target_id = session.id
                    signal.metadata_ = {
                        **(signal.metadata_ or {}),
                        "expression_lab_session_id": str(session.id),
                        "expression_lab_completed_at": now.isoformat(),
                        "completion_mode": "learning_completed_without_automatic_asset_save",
                    }
        await self._record_event(session, "session_completed", {})
        await MemoryWriter(self.db).record_event(
            MemoryEventInput(
                learner_id=session.learner_id,
                event_type="expression_lab_session_completed",
                skill="writing",
                source_type="expression_lab_session",
                source_id=str(session.id),
                payload={
                    "input_type": session.input_type,
                    "source_type": session.source_type,
                    "source_signal_id": session.source_ref,
                },
                confidence=1.0,
                created_by="user",
            )
        )
        if session.episode_id is not None:
            await EpisodeRuntime(self.db).complete_episode(
                session.episode_id,
                verification_report={
                    "passed": True,
                    "session_status": "completed",
                    "completed_by_user": True,
                },
            )

    async def _record_event(
        self,
        session: ExpressionLabSession,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        now = datetime.now(timezone.utc)
        self.db.add(
            ExpressionLabEvent(
                session_id=session.id,
                event_type=event_type,
                payload_json=payload,
                occurred_at=now,
            )
        )
        if session.episode_id is not None:
            await EpisodeRuntime(self.db).append_event(
                episode_id=session.episode_id,
                learner_id=session.learner_id,
                event_type=f"expression_lab_{event_type}",
                source_module="expression_lab",
                target_type="expression_lab_session",
                target_id=str(session.id),
                payload=payload,
            )
        await self.db.flush()

    async def _source_signal_snapshot(
        self, learner_id: uuid.UUID, signal_id: uuid.UUID
    ) -> dict[str, Any]:
        result = await self.db.execute(
            select(GroupLearningSignal, GroupLearningMessage, GroupLearningSource)
            .join(GroupLearningMessage, GroupLearningMessage.id == GroupLearningSignal.message_id)
            .join(GroupLearningSource, GroupLearningSource.id == GroupLearningMessage.source_id)
            .where(
                GroupLearningSignal.id == signal_id,
                GroupLearningSignal.learner_id == learner_id,
                GroupLearningMessage.learner_id == learner_id,
                GroupLearningSource.learner_id == learner_id,
            )
        )
        row = result.one_or_none()
        if row is None:
            raise ExpressionLabError(
                "source_signal_not_found", "Source signal not found", status_code=404
            )
        signal, message, source = row
        if signal.signal_type not in SOURCE_SIGNAL_TYPES:
            raise ExpressionLabError(
                "unsupported_source_signal", "Signal cannot open Expression Lab", status_code=422
            )
        return {
            "signal_id": str(signal.id),
            "signal_type": signal.signal_type,
            "target_type": signal.target_type,
            "target_label": signal.target_label,
            "confidence": signal.confidence,
            "evidence_text": signal.evidence_text,
            "normalized_note": signal.normalized_note,
            "recommendation_reason": signal.recommendation_reason,
            "signal_status_at_open": signal.status,
            "message_id": str(message.id),
            "occurred_at": message.occurred_at.isoformat(),
            "source_id": str(source.id),
            "source_label": source.display_name,
            "platform": source.platform,
        }

    def _question(
        self, session: ExpressionLabSession, block_id: str, question_id: str
    ) -> dict[str, Any]:
        for block in (session.ui_spec_json or {}).get("blocks") or []:
            if block.get("id") != block_id or block.get("type") != "micro_practice":
                continue
            for question in block.get("data", {}).get("questions", []):
                if question.get("id") == question_id:
                    return question
        raise ExpressionLabError("question_not_found", "Practice question not found", status_code=404)


async def generate_expression_lab_session_task(
    session_id: uuid.UUID,
    mode: str = "full",
    instruction: str | None = None,
) -> None:
    """FastAPI background entrypoint with an independent transaction."""

    async with async_session_factory() as db:
        try:
            await ExpressionLabService(db, global_model_router).generate_and_store(
                session_id=session_id,
                mode=mode,
                instruction=instruction,
            )
            await db.commit()
        except Exception:
            await db.rollback()
            async with async_session_factory() as failure_db:
                result = await failure_db.execute(
                    select(ExpressionLabSession).where(ExpressionLabSession.id == session_id)
                )
                session = result.scalar_one_or_none()
                if session is not None and session.status == "generating":
                    session.status = "error"
                    session.diagnostics_json = {
                        "error_code": "background_generation_failed",
                        "retryable": True,
                    }
                    await failure_db.commit()


def session_summary(session: ExpressionLabSession) -> dict[str, Any]:
    return {
        "session_id": session.id,
        "status": session.status,
        "input_type": session.input_type,
        "input_text": session.input_text,
        "context": session.context,
        "style_goal": session.style_goal,
        "source_type": session.source_type,
        "source_ref": session.source_ref,
        "source": _source_view(session),
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "completed_at": session.completed_at,
    }


def _answer_text(answer: str | dict[str, Any]) -> str:
    if isinstance(answer, str):
        return answer.strip()
    for key in ("answer", "value", "text"):
        value = answer.get(key)
        if isinstance(value, str):
            return value.strip()
    items = answer.get("items")
    if isinstance(items, list):
        return " ".join(str(item).strip() for item in items if str(item).strip())
    return ""


def _normalize_answer(value: str) -> str:
    return " ".join(value.strip().strip(".!?。！？").casefold().split())


def _grade_answer(submitted: str, grading: dict[str, Any]) -> dict[str, Any]:
    answer = str(grading.get("answer") or "")
    acceptable = [answer, *(grading.get("accepted_answers") or [])]
    normalized = _normalize_answer(submitted)
    exact = normalized in {_normalize_answer(str(item)) for item in acceptable if str(item)}
    target = _normalize_answer(str(grading.get("target_expression") or ""))
    target_used = bool(target and target in normalized)
    score = 100.0 if exact else 60.0 if target_used else 0.0
    feedback = (
        "回答正确，你已经能在这个场景中使用目标表达。"
        if exact
        else "意思接近，目标表达已经用上了；再调整完整句子会更自然。"
        if target_used
        else "这次还没有用到目标表达。先看提示，再换一种更自然的说法。"
    )
    return {"score": score, "is_correct": exact, "feedback": feedback}


def _next_recommendations(
    correct: bool, block_id: str, question_id: str, attempt_number: int
) -> list[dict[str, Any]]:
    if correct:
        return [
            {
                "type": "transfer_practice",
                "reason": "当前题已答对，换一个场景能验证是否真正会迁移。",
                "block_id": block_id,
            },
            {"type": "save_expression", "reason": "可收藏最适合自己的表达用于复习。"},
        ]
    return [
        {
            "type": "retry",
            "reason": "根据提示再试一次。",
            "question_id": question_id,
            "available": attempt_number < 3,
        },
        {"type": "review_explanation", "reason": "回看语气、结构或错误 diff 后再作答。"},
    ]


def _bounded_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in list(payload.items())[:20]:
        safe_key = re.sub(r"[^a-zA-Z0-9_.:-]", "", str(key))[:80]
        if not safe_key:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            clean[safe_key] = value[:500] if isinstance(value, str) else value
    return clean


def _source_view(session: ExpressionLabSession) -> dict[str, Any]:
    snapshot = session.source_snapshot or {}
    return {
        "type": session.source_type,
        "source_id": session.source_ref,
        "label": snapshot.get("source_label") or (
            "群聊学习线索" if session.source_type == "group_learning_signal" else "手动输入"
        ),
        "text": snapshot.get("evidence_text") or session.input_text,
        "occurred_at": snapshot.get("occurred_at"),
        "confidence": snapshot.get("confidence"),
        "metadata": {
            "signal_type": snapshot.get("signal_type"),
            "recommendation_reason": snapshot.get("recommendation_reason"),
        },
    }


def _evidence_view(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = []
    if snapshot.get("evidence_text"):
        evidence.append(
            {
                "type": "source_evidence",
                "label": snapshot["evidence_text"],
                "id": snapshot.get("message_id"),
            }
        )
    if snapshot.get("recommendation_reason"):
        evidence.append(
            {
                "type": "recommendation_reason",
                "label": snapshot["recommendation_reason"],
                "id": snapshot.get("signal_id"),
            }
        )
    return evidence


def _action_view(action: ExpressionLabAction) -> dict[str, Any]:
    public_status = {
        "pending": "candidate",
        "applying": "saving",
        "applied": "saved",
        "dismissed": "dismissed",
        "failed": "failed",
        "superseded": "superseded",
    }.get(action.status, action.status)
    return {
        "id": str(action.id),
        "spec_action_id": action.spec_action_id,
        "type": action.action_type,
        "action_type": action.action_type,
        "label": action.label,
        "block_id": action.block_id,
        "payload": action.payload_json or {},
        "editable_fields": action.editable_fields or [],
        "requires_confirmation": action.requires_confirmation,
        "confirmed_by_user": action.confirmed_by_user,
        "status": public_status,
        "applied_target_type": action.applied_target_type,
        "applied_target_id": action.applied_target_id,
        "failure_code": action.failure_code,
    }


def _attempt_view(attempt: ExpressionLabAttempt) -> dict[str, Any]:
    return {
        "id": str(attempt.id),
        "block_id": attempt.block_id,
        "question_id": attempt.question_id,
        "answer_json": attempt.answer_json,
        "score": attempt.score,
        "is_correct": attempt.is_correct,
        "feedback_json": attempt.feedback_json,
        "next_recommendations": attempt.next_recommendations,
        "attempt_number": attempt.attempt_number,
        "created_at": attempt.created_at,
    }


def _ensure_system_actions(ui_spec: dict[str, Any]) -> dict[str, Any]:
    ui = {**ui_spec}
    actions = [dict(action) for action in ui.get("learning_actions") or []]
    action_types = {action.get("type") for action in actions}
    if "create_practice" in action_types:
        actions = [
            {
                **action,
                "requires_confirmation": True,
                "editable_fields": ["count", "focus"],
            }
            if action.get("type") == "create_practice"
            else action
            for action in actions
        ]
    else:
        actions.append(
            {
                "id": "system-create-practice",
                "type": "create_practice",
                "label": "生成 1–3 道练习",
                "block_id": None,
                "payload": {"count": 2, "focus": "当前表达的真实场景迁移"},
                "requires_confirmation": True,
                "editable_fields": ["count", "focus"],
            }
        )
    if "dismiss_suggestion" not in action_types:
        actions.append(
            {
                "id": "system-dismiss-suggestion",
                "type": "dismiss_suggestion",
                "label": "不适合我",
                "block_id": None,
                "payload": {"reason": ""},
                "requires_confirmation": False,
                "editable_fields": [],
            }
        )
    if "mark_completed" not in action_types:
        actions.append(
            {
                "id": "system-mark-completed",
                "type": "mark_completed",
                "label": "完成本次学习",
                "block_id": None,
                "payload": {"note": ""},
                "requires_confirmation": False,
                "editable_fields": [],
            }
        )
    ui["learning_actions"] = actions
    return ui
