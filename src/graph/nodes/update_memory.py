from src.graph.state import LearningState


async def update_memory(state: LearningState) -> dict:
    """Extract memory candidates from the learner's answer and feedback."""
    learner_answer = state.get("learner_answer")
    agent_feedback = state.get("agent_feedback")

    memory_candidates = []

    if learner_answer or agent_feedback:
        memory_candidates.append(
            {
                "type": "practice_record",
                "timestamp": "2026-01-01T00:00:00",
                "summary": "完成了一次练习",
                "metadata": {
                    "active_skill": state.get("active_skill"),
                    "feedback_summary": (
                        agent_feedback.get("summary", "") if agent_feedback else ""
                    ),
                },
            }
        )

    return {"memory_candidates": memory_candidates}
