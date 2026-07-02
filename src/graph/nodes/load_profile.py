from src.graph.state import LearningGraphState as LearningState


async def load_profile(state: LearningState) -> dict:
    """Load learner profile from state or return defaults."""
    return {
        "target_exam": state.get("target_exam", "CET6"),
        "exam_date": state.get("exam_date"),
        "current_level": state.get("current_level"),
        "daily_time_budget": state.get("daily_time_budget", 30),
    }
