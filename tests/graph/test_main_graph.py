import pytest

from src.graph.main_graph import daily_lesson_graph, route_after_task


class TestDailyLessonGraph:
    @pytest.mark.asyncio
    async def test_daily_lesson_runs(self):
        initial_state = {
            "user_id": "test-user",
            "thread_id": "test-thread",
            "session_id": "test-session",
            "target_exam": "CET6",
            "daily_time_budget": 30,
            "messages": [{"role": "user", "content": "我想练习阅读"}],
        }
        result = await daily_lesson_graph.ainvoke(initial_state)

        assert "active_skill" in result
        assert result["active_skill"] == "reading"
        assert "today_goal" in result

    @pytest.mark.asyncio
    async def test_daily_lesson_with_vocabulary_intent(self):
        initial_state = {
            "user_id": "test-user",
            "thread_id": "test-thread",
            "session_id": "test-session",
            "messages": [{"role": "user", "content": "我想背单词"}],
        }
        result = await daily_lesson_graph.ainvoke(initial_state)

        assert result["active_skill"] == "vocabulary"
        assert "today_goal" in result

    @pytest.mark.asyncio
    async def test_daily_lesson_produces_summary_message(self):
        initial_state = {
            "user_id": "test-user",
            "thread_id": "test-thread",
            "session_id": "test-session",
            "messages": [{"role": "user", "content": "练习写作"}],
        }
        result = await daily_lesson_graph.ainvoke(initial_state)

        assert "messages" in result
        assert len(result["messages"]) > 0

    @pytest.mark.asyncio
    async def test_daily_lesson_reading_gets_materials(self):
        initial_state = {
            "user_id": "test-user",
            "thread_id": "test-thread",
            "session_id": "test-session",
            "target_exam": "CET6",
            "messages": [{"role": "user", "content": "我想练习阅读"}],
        }
        result = await daily_lesson_graph.ainvoke(initial_state)

        assert "input_materials" in result
        assert len(result["input_materials"]) > 0
        assert result["input_materials"][0]["type"] == "reading_question"

    @pytest.mark.asyncio
    async def test_daily_lesson_default_intent_is_reading(self):
        initial_state = {
            "user_id": "test-user",
            "thread_id": "test-thread",
            "session_id": "test-session",
            "messages": [{"role": "user", "content": "你好，我想学习英语"}],
        }
        result = await daily_lesson_graph.ainvoke(initial_state)

        assert result["active_skill"] == "reading"


def test_graph_route_after_task_interrupts_without_answer():
    state = {"answer_required": True, "learner_answer": None}

    assert route_after_task(state) == "interrupt"


def test_graph_route_after_task_continues_with_answer():
    state = {"answer_required": True, "learner_answer": {"answer": "A"}}

    assert route_after_task(state) == "continue"
