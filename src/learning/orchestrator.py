import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from langchain_core.messages import BaseMessage
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.knowledge import (
    _append_runtime_event,
    _record_runtime_tool_call,
    _update_exercise_mastery_and_review,
)
from src.evidence.resolver import evidence_from_attempt, evidence_from_memory_event
from src.evidence.types import EvidenceRef
from src.exercises import ExerciseAttemptService
from src.graph.checkpoint_store import GraphCheckpointStore
from src.graph.main_graph import daily_lesson_graph
from src.knowledge.exercise_grader import answer_to_text, grade_exercise_answer
from src.memory.schemas import MemoryEventInput
from src.memory.writer import MemoryWriter
from src.models.knowledge import ExerciseQuestion, KnowledgeLearningEvent
from src.models.runtime import AgentEpisode, LearningEvent, ToolCallRecord
from src.recommendation.engine import RecommendationEngine
from src.recommendation.types import RecommendationInput
from src.runtime.episode import EpisodeRuntime
from src.runtime.schemas import EpisodeTraceView, episode_to_view, event_to_view, tool_call_to_view
from src.runtime.task_spec import TaskSpec
from src.verification.report import verify_knowledge_exercise_episode

from src.learning.types import LearningPlanRequest, LearningPlanResult, StartedTask


class LearningOrchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_learning_plan(self, request: LearningPlanRequest) -> LearningPlanResult:
        recommendation_plan = await RecommendationEngine(self.db).build_daily_plan(
            RecommendationInput(
                learner_id=request.learner_id,
                current_curriculum_node_id=request.current_curriculum_node_id,
                time_budget_minutes=request.time_budget_minutes,
                mode_hint=request.mode_hint,
                metadata=request.metadata,
            )
        )
        selected = recommendation_plan.tasks[0].task_spec if recommendation_plan.tasks else None
        return LearningPlanResult(
            recommendation_plan=recommendation_plan,
            selected_task=selected,
            episode_id=None,
            status="planned" if selected is not None else "empty",
            reason=recommendation_plan.reason,
        )

    async def start_task(
        self,
        *,
        learner_id: str | uuid.UUID,
        task_spec: TaskSpec,
        recommendation_reason: str | None = None,
    ) -> StartedTask:
        runtime = EpisodeRuntime(self.db)
        episode = await runtime.create_episode(
            learner_id=learner_id,
            source=task_spec.source,
            entrypoint="daily_lesson.start",
            task_spec=task_spec,
            status="running",
            context_snapshot={"recommendation_reason": recommendation_reason},
        )
        await runtime.append_event(
            episode_id=episode.id,
            learner_id=learner_id,
            event_type="episode_started",
            source_module="daily_lesson",
            target_type=task_spec.target.target_type,
            target_id=task_spec.target.target_id,
            payload={"task_id": task_spec.task_id, "reason": recommendation_reason},
        )

        if task_spec.task_type not in {
            "practice_knowledge_point",
            "learn_knowledge_point",
            "repair_weakness",
            "review_due_item",
        }:
            episode.status = "waiting_user"
            await self.db.flush()
            return StartedTask(
                episode_id=str(episode.id),
                task_spec=task_spec,
                status="not_implemented",
                answer_required=False,
                initial_payload={"reason": f"Unsupported task_type {task_spec.task_type}"},
                recommendation_reason=recommendation_reason,
            )

        question = await self._select_question(task_spec)
        if question is None:
            episode.status = "waiting_user"
            await self.db.flush()
            return StartedTask(
                episode_id=str(episode.id),
                task_spec=task_spec,
                status="not_implemented",
                answer_required=False,
                prompt="当前任务还没有可用题目。",
                initial_payload={"task_type": task_spec.task_type},
                recommendation_reason=recommendation_reason,
            )
        selected_task = task_spec.model_dump(mode="json")
        selected_task.setdefault("metadata", {})
        selected_task["metadata"]["question"] = _question_payload(question)
        thread_id = f"daily-lesson:{episode.id}"
        graph_run_id = str(uuid.uuid4())
        initial_state = {
            "user_id": str(learner_id),
            "learner_id": str(learner_id),
            "episode_id": str(episode.id),
            "graph_run_id": graph_run_id,
            "thread_id": thread_id,
            "selected_task": selected_task,
            "recommendation_plan": {"reason": recommendation_reason},
            "messages": [{"role": "user", "content": task_spec.objective}],
            "learner_answer": None,
            "answer_required": False,
        }
        graph_state = await daily_lesson_graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}},
        )
        input_materials = _json_safe(graph_state.get("input_materials", []))
        prompt_payload = {
            "prompt": _prompt_from_materials(input_materials) or question.stem,
            "input_materials": input_materials,
        }
        required_input_schema = {
            "type": "object",
            "required": ["answer"],
            "properties": {
                "answer": {
                    "type": ["string", "object"],
                    "description": "Learner answer for the prepared daily lesson task.",
                }
            },
        }
        checkpoint = None
        if graph_state.get("answer_required"):
            snapshot_state = _json_safe(graph_state)
            checkpoint_key = f"{episode.id}:{graph_state.get('current_task_id') or task_spec.task_id}"
            checkpoint = await GraphCheckpointStore(self.db).create_waiting_checkpoint(
                learner_id=learner_id,
                episode_id=episode.id,
                thread_id=thread_id,
                checkpoint_key=checkpoint_key,
                resume_from=graph_state.get("resume_from") or "generate_feedback",
                state_snapshot=snapshot_state,
                required_input_schema=required_input_schema,
                prompt_payload=prompt_payload,
            )
            snapshot_state["checkpoint_id"] = str(checkpoint.id)
            snapshot_state["checkpoint_status"] = checkpoint.status
            checkpoint.state_snapshot = snapshot_state

        snapshot = dict(episode.context_snapshot or {})
        snapshot.update(
            {
                "question_id": str(question.id),
                "answer_required": bool(graph_state.get("answer_required")),
                "thread_id": thread_id,
                "graph_run_id": graph_run_id,
                "current_task_id": graph_state.get("current_task_id") or task_spec.task_id,
                "resume_from": graph_state.get("resume_from") or "generate_feedback",
                "input_materials": input_materials,
            }
        )
        if checkpoint is not None:
            snapshot["checkpoint_id"] = str(checkpoint.id)
            snapshot["checkpoint_status"] = checkpoint.status
        episode.context_snapshot = snapshot
        episode.status = "waiting_user" if checkpoint is not None else "completed"
        await runtime.append_event(
            episode_id=episode.id,
            learner_id=learner_id,
            event_type="task_prepared",
            source_module="daily_lesson",
            target_type=task_spec.target.target_type,
            target_id=task_spec.target.target_id,
            payload={
                "current_task_id": snapshot["current_task_id"],
                "answer_required": bool(graph_state.get("answer_required")),
                "resume_from": snapshot["resume_from"],
                "checkpoint_id": str(checkpoint.id) if checkpoint is not None else None,
                "input_materials": input_materials,
            },
        )
        if checkpoint is not None:
            await runtime.append_event(
                episode_id=episode.id,
                learner_id=learner_id,
                event_type="graph_interrupted",
                source_module="daily_lesson",
                target_type=task_spec.target.target_type,
                target_id=task_spec.target.target_id,
                payload={
                    "current_task_id": snapshot["current_task_id"],
                    "answer_required": True,
                    "resume_from": snapshot["resume_from"],
                    "checkpoint_id": str(checkpoint.id),
                    "input_materials": input_materials,
                },
            )
        await self.db.flush()
        return StartedTask(
            episode_id=str(episode.id),
            task_spec=task_spec,
            status=episode.status,
            answer_required=bool(graph_state.get("answer_required")),
            checkpoint_id=str(checkpoint.id) if checkpoint is not None else None,
            checkpoint_status=checkpoint.status if checkpoint is not None else None,
            resume_from=snapshot["resume_from"],
            prompt=prompt_payload["prompt"],
            initial_payload={
                "question_id": str(question.id),
                "question_type": question.question_type,
                "options": question.options or [],
                "difficulty": question.difficulty,
                "input_materials": input_materials,
                "prompt_payload": prompt_payload,
            },
            recommendation_reason=recommendation_reason,
        )

    async def resume_task(self, episode_id: str | uuid.UUID) -> dict[str, Any]:
        episode = await self._get_episode(episode_id)
        return {
            "episode_id": str(episode.id),
            "status": episode.status,
            "context_snapshot": episode.context_snapshot or {},
        }

    async def get_daily_lesson_status(
        self,
        *,
        learner_id: str | uuid.UUID,
        episode_id: str | uuid.UUID,
    ) -> dict[str, Any]:
        episode = await self._get_episode(episode_id)
        if str(episode.learner_id) != str(learner_id):
            raise HTTPException(status_code=404, detail="Daily lesson episode not found")

        checkpoints = await GraphCheckpointStore(self.db).list_checkpoints_for_episode(episode.id)
        checkpoint = checkpoints[0] if checkpoints else None
        event_count_result = await self.db.execute(
            select(func.count()).select_from(LearningEvent).where(LearningEvent.episode_id == episode.id)
        )
        tool_count_result = await self.db.execute(
            select(func.count())
            .select_from(ToolCallRecord)
            .where(ToolCallRecord.episode_id == episode.id)
        )
        verification_report = (
            episode.verification_report if isinstance(episode.verification_report, dict) else {}
        )
        return {
            "episode_id": str(episode.id),
            "episode_status": episode.status,
            "checkpoint": _checkpoint_status_payload(checkpoint),
            "trace_summary": {
                "event_count": int(event_count_result.scalar_one() or 0),
                "tool_call_count": int(tool_count_result.scalar_one() or 0),
                "verification_status": verification_report.get("status"),
            },
        }

    async def complete_task(
        self,
        episode_id: str | uuid.UUID,
        *,
        verification_report: dict[str, Any] | None = None,
    ) -> AgentEpisode:
        return await EpisodeRuntime(self.db).complete_episode(
            episode_id,
            verification_report=verification_report,
        )

    async def submit_answer(
        self,
        *,
        learner_id: str | uuid.UUID,
        episode_id: str | uuid.UUID,
        answer: str | dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        episode = await self._get_episode(episode_id)
        if str(episode.learner_id) != str(learner_id):
            raise HTTPException(status_code=404, detail="Daily lesson episode not found")
        checkpoint_store = GraphCheckpointStore(self.db)
        checkpoint = await checkpoint_store.get_active_checkpoint(episode.id, learner_id)
        if checkpoint is None:
            raise HTTPException(status_code=409, detail="Episode is not waiting for an answer")
        question_id = (episode.context_snapshot or {}).get("question_id")
        if not question_id:
            raise HTTPException(status_code=409, detail="Episode is not waiting for an answer")
        question = await self._get_question(question_id)
        submitted_answer = answer_to_text(answer)
        if not submitted_answer:
            raise HTTPException(status_code=422, detail="Answer cannot be empty")

        runtime = EpisodeRuntime(self.db)
        runtime_events = []
        tool_calls = []
        task_spec = TaskSpec(**episode.task_spec)
        checkpoint_state = dict(checkpoint.state_snapshot or {})
        learner_answer = answer if isinstance(answer, dict) else {"answer": answer}
        checkpoint_state.update(
            {
                "learner_answer": learner_answer,
                "checkpoint_status": "resumed",
                "resume_from": checkpoint.resume_from or "generate_feedback",
                "checkpoint_id": str(checkpoint.id),
            }
        )
        checkpoint.state_snapshot = _json_safe(checkpoint_state)
        await checkpoint_store.mark_resumed(checkpoint.id)
        await _append_daily_event(
            runtime,
            runtime_events,
            episode=episode,
            learner_id=uuid.UUID(str(learner_id)),
            event_type="graph_resumed",
            target_type=task_spec.target.target_type,
            target_id=task_spec.target.target_id,
            payload={
                "current_task_id": checkpoint_state.get("current_task_id"),
                "answer_required": True,
                "resume_from": checkpoint.resume_from or "generate_feedback",
                "checkpoint_id": str(checkpoint.id),
            },
        )
        await _append_daily_event(
            runtime,
            runtime_events,
            episode=episode,
            learner_id=uuid.UUID(str(learner_id)),
            event_type="learner_answer_received",
            target_type=task_spec.target.target_type,
            target_id=task_spec.target.target_id,
            payload={
                "checkpoint_id": str(checkpoint.id),
                "answer": submitted_answer,
            },
        )
        grading = grade_exercise_answer(
            question,
            answer,
            attempt_index=int((metadata or {}).get("attempt_index", 0)),
        )
        await _record_runtime_tool_call(
            runtime,
            episode,
            tool_calls,
            tool_name="exercise.grade",
            input_payload={"question_id": str(question.id), "answer": answer},
            output_payload=grading,
        )
        correct = bool(grading["correct"])
        stored_answer = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
        attempt = await ExerciseAttemptService(self.db).save_knowledge_question_attempt(
            learner_id=uuid.UUID(str(learner_id)),
            question=question,
            answer=stored_answer.strip(),
            correct=correct,
            session_id=None,
            response_time_ms=(metadata or {}).get("response_time_ms"),
            metadata={
                "score": grading["score"],
                "passed": grading["passed"],
                "error_type": grading["error_type"],
                "episode_id": str(episode.id),
            },
            source_context={"source_id": str(question.source_id), "episode_id": str(episode.id)},
        )
        evidence_refs = [
            evidence_from_attempt(attempt, reason="daily lesson answer", used_by="daily_lesson").model_dump(
                mode="json"
            )
        ]
        if question.knowledge_point_id:
            evidence_refs.append(
                EvidenceRef(
                    evidence_type="knowledge_point",
                    evidence_id=str(question.knowledge_point_id),
                    reason="daily lesson target",
                    used_by="daily_lesson",
                ).model_dump(mode="json")
            )
        target_type = task_spec.target.target_type
        target_id = task_spec.target.target_id
        await _append_runtime_event(
            runtime,
            runtime_events,
            episode=episode,
            learner_id=uuid.UUID(str(learner_id)),
            event_type="exercise_answered",
            target_type=target_type,
            target_id=target_id,
            payload={
                "question_id": str(question.id),
                "attempt_id": str(attempt.id),
                "answer": submitted_answer,
                "evidence_refs": evidence_refs,
            },
        )
        await _append_runtime_event(
            runtime,
            runtime_events,
            episode=episode,
            learner_id=uuid.UUID(str(learner_id)),
            event_type="exercise_graded",
            target_type=target_type,
            target_id=target_id,
            payload={
                "question_id": str(question.id),
                "attempt_id": str(attempt.id),
                "correct": correct,
                "score": grading["score"],
                "error_type": grading["error_type"],
                "evidence_refs": evidence_refs,
            },
        )
        mastery_update, review_schedule = await _update_exercise_mastery_and_review(
            self.db,
            learner_id=uuid.UUID(str(learner_id)),
            question=question,
            correct=correct,
            grading=grading,
            body=_BodyShim(metadata or {}),
            attempt_id=attempt.id,
            evidence_refs=evidence_refs,
        )
        if mastery_update is not None:
            await _record_runtime_tool_call(
                runtime,
                episode,
                tool_calls,
                tool_name="mastery.update",
                input_payload={"attempt_id": str(attempt.id), "score": grading["score"]},
                output_payload=mastery_update,
            )
            await _append_runtime_event(
                runtime,
                runtime_events,
                episode=episode,
                learner_id=uuid.UUID(str(learner_id)),
                event_type="mastery_updated",
                target_type="knowledge_point",
                target_id=str(question.knowledge_point_id),
                payload=mastery_update,
            )
        if review_schedule is not None:
            await _append_runtime_event(
                runtime,
                runtime_events,
                episode=episode,
                learner_id=uuid.UUID(str(learner_id)),
                event_type="review_scheduled",
                target_type="knowledge_point",
                target_id=str(question.knowledge_point_id),
                payload={
                    "review_schedule_id": str(review_schedule.id),
                    "scheduled_at": review_schedule.scheduled_at.isoformat(),
                    "evidence_refs": evidence_refs,
                },
            )
        memory_updates = []
        if question.knowledge_point_id:
            now = datetime.now(timezone.utc)
            self.db.add(
                KnowledgeLearningEvent(
                    learner_id=uuid.UUID(str(learner_id)),
                    session_id=None,
                    event_type="exercise_answered",
                    knowledge_point_id=question.knowledge_point_id,
                    payload={
                        "question_id": str(question.id),
                        "attempt_id": str(attempt.id),
                        "episode_id": str(episode.id),
                        "correct": correct,
                        "score": grading["score"],
                    },
                    occurred_at=now,
                )
            )
            memory_event = await MemoryWriter(self.db).record_event(
                MemoryEventInput(
                    learner_id=uuid.UUID(str(learner_id)),
                    event_type="daily_lesson_answered",
                    skill="knowledge",
                    subskill=question.question_type,
                    source_type="exercise_attempt",
                    source_id=str(attempt.id),
                    payload={
                        "question_id": str(question.id),
                        "attempt_id": str(attempt.id),
                        "episode_id": str(episode.id),
                        "correct": correct,
                        "score": grading["score"],
                        "evidence_refs": evidence_refs,
                    },
                    confidence=0.95,
                    occurred_at=now,
                )
            )
            memory_updates.append({"memory_event_id": str(memory_event.id)})
            await _record_runtime_tool_call(
                runtime,
                episode,
                tool_calls,
                tool_name="memory.write",
                input_payload={"attempt_id": str(attempt.id)},
                output_payload={"memory_event_id": str(memory_event.id)},
            )
            await _append_runtime_event(
                runtime,
                runtime_events,
                episode=episode,
                learner_id=uuid.UUID(str(learner_id)),
                event_type="memory_written",
                target_type="knowledge_point",
                target_id=str(question.knowledge_point_id),
                payload={
                    "memory_event_id": str(memory_event.id),
                    "evidence_refs": [
                        *evidence_refs,
                        evidence_from_memory_event(memory_event).model_dump(mode="json"),
                    ],
                },
            )

        await _append_daily_event(
            runtime,
            runtime_events,
            episode=episode,
            learner_id=uuid.UUID(str(learner_id)),
            event_type="episode_completed",
            target_type=target_type,
            target_id=target_id,
            payload={"task_id": task_spec.task_id},
        )
        trace = EpisodeTraceView(
            episode=episode_to_view(episode),
            events=[event_to_view(event) for event in runtime_events],
            tool_calls=[tool_call_to_view(tool_call) for tool_call in tool_calls],
        )
        verification_report = await verify_knowledge_exercise_episode(
            self.db,
            str(episode.id),
            trace=trace,
        )
        await _record_runtime_tool_call(
            runtime,
            episode,
            tool_calls,
            tool_name="verification.verify_episode",
            input_payload={"episode_id": str(episode.id)},
            output_payload=verification_report,
        )
        await runtime.complete_episode(
            episode.id,
            episode=episode,
            verification_report=verification_report,
        )
        await checkpoint_store.mark_completed(checkpoint.id)
        completion_snapshot = dict(episode.context_snapshot or {})
        completion_snapshot["checkpoint_status"] = "completed"
        completion_snapshot["checkpoint_id"] = str(checkpoint.id)
        episode.context_snapshot = completion_snapshot
        await self.db.flush()
        return {
            "feedback": grading["feedback"],
            "grading_result": grading,
            "mastery_update": mastery_update,
            "memory_updates": memory_updates,
            "verification_status": verification_report.get("status"),
            "next_recommendation": None,
            "episode_id": str(episode.id),
            "status": episode.status,
            "checkpoint_status": "completed",
        }

    async def _select_question(self, task_spec: TaskSpec) -> ExerciseQuestion | None:
        target_id = _safe_uuid(task_spec.target.target_id)
        if target_id is None:
            return None
        query = select(ExerciseQuestion).where(ExerciseQuestion.status == "published")
        if task_spec.target.target_type == "knowledge_point":
            query = query.where(ExerciseQuestion.knowledge_point_id == target_id)
        else:
            query = query.where(ExerciseQuestion.curriculum_node_id == target_id)
        result = await self.db.execute(query.order_by(ExerciseQuestion.created_at.asc()).limit(1))
        return result.scalar_one_or_none()

    async def _get_question(self, question_id: str) -> ExerciseQuestion:
        result = await self.db.execute(
            select(ExerciseQuestion).where(
                ExerciseQuestion.id == uuid.UUID(str(question_id)),
                ExerciseQuestion.status == "published",
            )
        )
        question = result.scalar_one_or_none()
        if question is None:
            raise HTTPException(status_code=404, detail="Exercise question not found")
        return question

    async def _get_episode(self, episode_id: str | uuid.UUID) -> AgentEpisode:
        result = await self.db.execute(
            select(AgentEpisode).where(AgentEpisode.id == uuid.UUID(str(episode_id)))
        )
        episode = result.scalar_one_or_none()
        if episode is None:
            raise HTTPException(status_code=404, detail="Daily lesson episode not found")
        return episode


class _BodyShim:
    def __init__(self, metadata: dict[str, Any]):
        self.response_time_ms = metadata.get("response_time_ms")
        self.hint_used = int(metadata.get("hint_used", 0))
        self.attempt_index = int(metadata.get("attempt_index", 0))


def _safe_uuid(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


async def _append_daily_event(
    runtime: EpisodeRuntime,
    events: list,
    *,
    episode,
    learner_id: uuid.UUID,
    event_type: str,
    target_type: str | None,
    target_id: str | None,
    payload: dict[str, Any],
) -> None:
    events.append(
        await runtime.append_event(
            episode_id=episode.id,
            learner_id=learner_id,
            event_type=event_type,
            source_module="daily_lesson",
            target_type=target_type,
            target_id=target_id,
            payload=payload,
        )
    )


def _question_payload(question: ExerciseQuestion) -> dict[str, Any]:
    return {
        "question_id": str(question.id),
        "question_type": question.question_type,
        "stem": question.stem,
        "options": question.options or [],
        "difficulty": question.difficulty,
    }


def _prompt_from_materials(materials: Any) -> str | None:
    if not isinstance(materials, list) or not materials:
        return None
    first = materials[0] if isinstance(materials[0], dict) else {}
    value = first.get("prompt") or first.get("stem") or first.get("content")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _checkpoint_status_payload(checkpoint) -> dict[str, Any] | None:
    if checkpoint is None:
        return None
    prompt_payload = checkpoint.prompt_payload or {}
    return {
        "checkpoint_id": str(checkpoint.id),
        "status": checkpoint.status,
        "resume_from": checkpoint.resume_from,
        "answer_required": checkpoint.status == "waiting_user",
        "prompt_payload": prompt_payload,
        "created_at": checkpoint.created_at,
        "consumed_at": checkpoint.consumed_at,
    }


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, BaseMessage):
        return {"type": value.type, "content": value.content}
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_safe(item) for item in value]
    return str(value)
