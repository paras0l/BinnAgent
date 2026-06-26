import uuid

from src.db import async_session_factory
from src.graph.state import LearningState
from src.memory.retriever import MemoryRetriever


async def schedule_review(state: LearningState) -> dict:
    """Generate review items from memory candidates for spaced repetition."""
    memory_candidates = state.get("memory_candidates", [])
    review_items = []

    for candidate in memory_candidates:
        if candidate.get("type") == "practice_record":
            review_items.append(
                {
                    "type": "review",
                    "source": candidate.get("summary", ""),
                    "scheduled_days_later": 1,
                    "priority": "medium",
                }
            )

    learner_id = _state_uuid(state.get("user_id"))
    if learner_id is not None:
        async with async_session_factory() as db:
            context = await MemoryRetriever(db).retrieve_context(
                learner_id=learner_id,
                reason="schedule_review",
                skill=state.get("active_skill"),
                limit=5,
            )
            review_items.extend(
                {
                    "type": item.type,
                    "source": item.summary,
                    "scheduled_days_later": 1 if item.skill in {"vocabulary", "knowledge"} else 2,
                    "priority": "high" if item.confidence >= 0.75 else "medium",
                    "memory_id": item.id,
                    "reason": item.reason,
                }
                for item in context.loaded_items
            )
            await db.commit()

    return {"review_items": review_items}


def _state_uuid(value: object) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None
