import uuid
from datetime import datetime, timezone

from src.db import async_session_factory
from src.graph.state import LearningGraphState as LearningState
from src.memory.curator import MemoryCurator
from src.memory.schemas import MemoryEventInput
from src.memory.writer import MemoryWriter


async def update_memory(state: LearningState) -> dict:
    """Extract memory candidates from the learner's answer and feedback."""
    learner_answer = state.get("learner_answer")
    agent_feedback = state.get("agent_feedback")
    exercise_attempt_id = state.get("exercise_attempt_id")
    mastery_update = state.get("mastery_update")
    evidence_refs = state.get("evidence_refs") or []

    memory_candidates = []
    memory_write_result = {
        "status": "skipped",
        "memory_event_ids": [],
        "evidence_refs": evidence_refs,
    }

    if learner_answer or agent_feedback:
        summary = "完成了一次练习"
        memory_candidates.append(
            {
                "type": "practice_record",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": summary,
                "metadata": {
                    "active_skill": state.get("active_skill"),
                    "feedback_summary": (
                        agent_feedback.get("summary", "") if agent_feedback else ""
                    ),
                    "exercise_attempt_id": exercise_attempt_id,
                    "mastery_update": mastery_update,
                    "evidence_refs": evidence_refs,
                },
            }
        )
        learner_id = _state_uuid(state.get("user_id"))
        if state.get("side_effect_mode") == "dry_run":
            memory_write_result = {
                "status": "prepared",
                "memory_event_ids": [],
                "evidence_refs": evidence_refs,
            }
            return {
                "memory_candidates": memory_candidates,
                "memory_write_result": memory_write_result,
            }
        if learner_id is not None:
            async with async_session_factory() as db:
                writer = MemoryWriter(db)
                memory_event = await writer.record_event(
                    MemoryEventInput(
                        learner_id=learner_id,
                        event_type="knowledge_exercise_answered",
                        skill=state.get("active_skill") or "general",
                        source_type="langgraph_run",
                        source_id=state.get("thread_id"),
                        payload={
                            "summary": summary,
                            "learner_answer": learner_answer or {},
                            "feedback": agent_feedback or {},
                            "exercise_attempt_id": exercise_attempt_id,
                            "mastery_update": mastery_update or {},
                            "evidence_refs": evidence_refs,
                        },
                        confidence=0.75,
                        created_by="system",
                    )
                )
                await MemoryCurator(db).curate_learner(learner_id)
                await db.commit()
                memory_write_result = {
                    "status": "written",
                    "memory_event_ids": [str(memory_event.id)],
                    "evidence_refs": evidence_refs,
                }
        else:
            memory_write_result = {
                "status": "prepared",
                "memory_event_ids": [],
                "evidence_refs": evidence_refs,
            }

    return {"memory_candidates": memory_candidates, "memory_write_result": memory_write_result}


def _state_uuid(value: object) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None
