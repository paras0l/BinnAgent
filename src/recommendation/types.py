from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.evidence.types import EvidenceRef
from src.runtime.task_spec import TaskSpec


class RecommendationInput(BaseModel):
    learner_id: str
    current_curriculum_node_id: str | None = None
    time_budget_minutes: int | None = None
    mode_hint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecommendationTask(BaseModel):
    task_spec: TaskSpec
    priority_score: float
    reason: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    estimated_minutes: int | None = None


class RecommendationPlan(BaseModel):
    plan_id: str
    learner_id: str
    mode: str
    reason: str
    confidence: float
    tasks: list[RecommendationTask] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    generated_at: datetime
