import pytest

from src.graph.main_graph import build_graph
from src.graph.nodes.wait_for_answer import wait_for_answer


@pytest.mark.asyncio
async def test_wait_for_answer_sets_interrupt_compatible_payload():
    result = await wait_for_answer(
        {
            "answer_required": True,
            "current_task_id": "task:1",
            "input_materials": [{"task_id": "task:1", "prompt": "Choose the greeting."}],
        }
    )

    assert result["answer_required"] is True
    assert result["current_task_id"] == "task:1"
    assert result["checkpoint_status"] == "waiting_user"
    assert result["resume_from"] == "grade_attempt"
    assert result["prompt_payload"]["prompt"] == "Choose the greeting."
    assert result["required_input_schema"]["required"] == ["answer"]


@pytest.mark.asyncio
async def test_no_answer_path_does_not_execute_side_effect_nodes():
    graph = build_graph()

    result = await graph.ainvoke(
        {
            "user_id": "not-a-uuid",
            "learner_id": "not-a-uuid",
            "thread_id": "daily-lesson:missing-answer",
            "messages": [{"role": "user", "content": "我想练习阅读"}],
        }
    )

    assert result["checkpoint_status"] == "waiting_user"
    assert result["resume_from"] == "grade_attempt"
    assert "grade_result" not in result
    assert "memory_write_result" not in result
    assert "mastery_update" not in result
