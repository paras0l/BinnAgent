from src.graph.state import LearningState


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

    return {"review_items": review_items}
