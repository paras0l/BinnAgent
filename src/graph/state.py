from typing import Any, TypedDict, Annotated

from langgraph.graph.message import add_messages


class LearningState(TypedDict, total=False):
    user_id: str
    thread_id: str
    session_id: str
    target_exam: str | None
    exam_date: str | None
    current_level: str | None
    daily_time_budget: int
    active_skill: str | None
    today_goal: str | None
    messages: Annotated[list, add_messages]
    input_materials: list[dict[str, Any]]
    learner_answer: dict[str, Any] | None
    agent_feedback: dict[str, Any] | None
    memory_candidates: list[dict[str, Any]]
    review_items: list[dict[str, Any]]
    next_tasks: list[dict[str, Any]]
    emotion_signal: dict[str, Any] | None
    model_policy: dict[str, Any] | None
