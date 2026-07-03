import uuid

from src.db import async_session_factory
from src.graph.state import LearningGraphState as LearningState
from src.memory.retriever import MemoryRetriever


async def schedule_review(state: LearningState) -> dict:
    """Generate review items from memory candidates for spaced repetition."""
    memory_candidates = state.get("memory_candidates", [])
    mastery_update = state.get("mastery_update") or {}
    evidence_refs = state.get("evidence_refs") or mastery_update.get("evidence_refs") or []
    review_items = []

    if mastery_update.get("next_review_at"):
        review_items.append(
            {
                "type": "review",
                "source": "mastery_update",
                "scheduled_at": mastery_update["next_review_at"],
                "priority": "high" if mastery_update.get("mastery_delta", 0) < 0 else "medium",
                "target_type": mastery_update.get("target_type"),
                "target_id": mastery_update.get("target_id"),
                "evidence_refs": evidence_refs,
            }
        )

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
    if learner_id is not None and state.get("side_effect_mode") != "dry_run":
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

    return {
        "review_items": review_items,
        "review_schedule_result": {
            "status": "scheduled" if review_items else "skipped",
            "review_items": review_items,
            "evidence_refs": evidence_refs,
        },
    }


def _state_uuid(value: object) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None
