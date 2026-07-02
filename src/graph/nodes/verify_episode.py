from datetime import datetime, timezone

from src.graph.state import LearningGraphState as LearningState


async def verify_episode(state: LearningState) -> dict:
    """Produce a lightweight graph-level verification report."""
    checks = [
        {
            "name": "answer_received",
            "passed": bool(state.get("learner_answer")),
        },
        {
            "name": "feedback_ready",
            "passed": bool(state.get("agent_feedback")),
        },
        {
            "name": "review_items_prepared",
            "passed": "review_items" in state,
        },
    ]
    status = "passed" if all(check["passed"] for check in checks) else "failed"
    return {
        "feedback_ready": bool(state.get("agent_feedback")),
        "verification_report": {
            "episode_id": state.get("episode_id"),
            "status": status,
            "checks": checks,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "daily_lesson_graph",
        },
    }
