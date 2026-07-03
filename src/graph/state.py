from typing import Any, TypedDict, Annotated

from langgraph.graph.message import add_messages


class LearningGraphState(TypedDict, total=False):
    user_id: str
    learner_id: str
    graph_run_id: str | None
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
    recommendation_plan: dict[str, Any] | None
    selected_task: dict[str, Any] | None
    episode_id: str | None
    answer_required: bool
    current_task_id: str | None
    resume_from: str | None
    checkpoint_status: str | None
    feedback_ready: bool | None
    verification_report: dict[str, Any] | None
    exercise_attempt_id: str | None
    mastery_update: dict[str, Any] | None
    knowledge_point_ids: list[str]
    wrong_reason: str | None
    recommended_action: dict[str, Any] | None
    evidence_refs: list[dict[str, Any]]
    prompt_payload: dict[str, Any] | None
    required_input_schema: dict[str, Any] | None
    grade_result: dict[str, Any] | None
    review_schedule_result: dict[str, Any] | None
    memory_write_result: dict[str, Any] | None
    recommendation_result: dict[str, Any] | None
    side_effect_mode: str | None


class LearningState(LearningGraphState, total=False):
    checkpoint_id: str | None
