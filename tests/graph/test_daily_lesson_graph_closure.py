import pytest

from src.graph.main_graph import build_graph, build_resume_graph


def _state(answer: str = "Good morning!") -> dict:
    target_id = "11111111-1111-4111-8111-111111111111"
    return {
        "user_id": "not-a-uuid",
        "learner_id": "not-a-uuid",
        "thread_id": "daily-lesson:closure",
        "side_effect_mode": "dry_run",
        "selected_task": {
            "task_id": "task:greeting",
            "task_type": "practice_knowledge_point",
            "source": "test",
            "objective": "Practice greeting",
            "target": {"target_type": "knowledge_point", "target_id": target_id},
            "success_criteria": {"min_accuracy": 1.0},
            "verification_policy": {
                "required_checks": [
                    "task_prepared",
                    "learner_answer_received",
                    "exercise_attempt_created",
                    "exercise_graded",
                    "mastery_updated",
                    "memory_event_written",
                    "review_scheduled",
                    "next_action_recommended",
                ]
            },
            "metadata": {
                "question": {
                    "question_id": "question:greeting",
                    "question_type": "multiple_choice",
                    "stem": "Choose the greeting.",
                    "options": ["Good morning!", "Other"],
                    "answer": "Good morning!",
                    "knowledge_point_id": target_id,
                }
            },
        },
        "messages": [{"role": "user", "content": "Practice greeting"}],
        "learner_answer": {"answer": answer},
    }


@pytest.mark.asyncio
async def test_daily_lesson_graph_answer_closes_learning_loop():
    result = await build_graph().ainvoke(_state())

    assert result["exercise_attempt_id"]
    assert result["grade_result"]["correct"] is True
    assert result["mastery_update"]["mastery_delta"] > 0
    assert result["memory_write_result"]["status"] == "prepared"
    assert result["review_schedule_result"]["status"] == "scheduled"
    assert result["recommendation_result"]["status"] == "recommended"
    assert result["verification_report"]["status"] == "passed"
    assert {
        check["name"] for check in result["verification_report"]["checks"] if check["passed"]
    } >= {
        "task_prepared",
        "learner_answer_received",
        "exercise_attempt_created",
        "exercise_graded",
        "mastery_updated",
        "memory_event_written",
        "review_scheduled",
        "next_action_recommended",
    }


@pytest.mark.asyncio
async def test_resume_graph_from_grade_attempt_runs_new_chain():
    state = _state()
    state.update(
        {
            "answer_required": True,
            "current_task_id": "task:greeting",
            "input_materials": [
                {
                    "task_id": "task:greeting",
                    "question_id": "question:greeting",
                    "stem": "Choose the greeting.",
                    "options": ["Good morning!", "Other"],
                    "answer": "Good morning!",
                    "target_type": "knowledge_point",
                    "target_id": "11111111-1111-4111-8111-111111111111",
                }
            ],
        }
    )

    result = await build_resume_graph(start_node="grade_attempt").ainvoke(state)

    assert result["grade_result"]["status"] == "graded"
    assert result["mastery_update"]["status"] == "learning"
    assert result["recommendation_result"]["status"] == "recommended"
