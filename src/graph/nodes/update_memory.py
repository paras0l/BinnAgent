import uuid
from datetime import datetime, timezone

from src.db import async_session_factory
from src.graph.state import LearningState
from src.memory.curator import MemoryCurator
from src.memory.schemas import MemoryEventInput
from src.memory.writer import MemoryWriter


async def update_memory(state: LearningState) -> dict:
    """Extract memory candidates from the learner's answer and feedback."""
    learner_answer = state.get("learner_answer")
    agent_feedback = state.get("agent_feedback")

    memory_candidates = []

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
                },
            }
        )
        learner_id = _state_uuid(state.get("user_id"))
        if learner_id is not None:
            async with async_session_factory() as db:
                writer = MemoryWriter(db)
                await writer.record_event(
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
                        },
                        confidence=0.75,
                        created_by="system",
                    )
                )
                await MemoryCurator(db).curate_learner(learner_id)
                await db.commit()

    return {"memory_candidates": memory_candidates}


def _state_uuid(value: object) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None
