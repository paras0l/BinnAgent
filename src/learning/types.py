from typing import Any

from pydantic import BaseModel, Field

from src.recommendation.types import RecommendationPlan
from src.runtime.task_spec import TaskSpec


class LearningPlanRequest(BaseModel):
    learner_id: str
    current_curriculum_node_id: str | None = None
    time_budget_minutes: int | None = None
    mode_hint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearningPlanResult(BaseModel):
    recommendation_plan: RecommendationPlan
    selected_task: TaskSpec | None = None
    episode_id: str | None = None
    status: str
    reason: str


class StartedTask(BaseModel):
    episode_id: str
    task_spec: TaskSpec | None = None
    status: str
    answer_required: bool
    prompt: str | None = None
    initial_payload: dict[str, Any] = Field(default_factory=dict)
    recommendation_reason: str | None = None
