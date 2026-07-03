import pytest

from src.graph.main_graph import build_checkpointer, build_graph


@pytest.mark.asyncio
async def test_daily_lesson_graph_compiles_with_memory_checkpointer():
    checkpointer = build_checkpointer(kind="memory")
    graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "daily-lesson:test-checkpoint"}}

    result = await graph.ainvoke(
        {
            "user_id": "test-user",
            "learner_id": "test-user",
            "thread_id": "daily-lesson:test-checkpoint",
            "messages": [{"role": "user", "content": "我想练习阅读"}],
        },
        config=config,
    )

    assert result["checkpoint_status"] == "waiting_user"
    assert result["resume_from"] == "grade_attempt"
    assert result["prompt_payload"]["prompt"]


def test_build_checkpointer_none_fallback():
    assert build_checkpointer(kind="none") is None
    assert build_checkpointer() is None
