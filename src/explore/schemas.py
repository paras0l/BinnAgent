import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


ExploreCapabilityStatus = Literal["ready", "todo"]
ExploreCapabilityAction = Literal["chat", "session", "tool", "vocabulary-detail", "todo"]
ExploreRecommendationSource = Literal["rule", "llm_rerank", "fallback"]


class ExploreCapabilitySpec(BaseModel):
    capability_id: str
    feature_id: str
    title: str
    description: str
    category: str
    status: ExploreCapabilityStatus = "ready"

    action: ExploreCapabilityAction
    tool_target: str | None = None
    route_hint: str | None = None

    learning_skill: str
    supported_target_types: list[str]
    supported_error_types: list[str] = Field(default_factory=list)
    recommended_when: list[str]
    not_recommended_when: list[str] = Field(default_factory=list)
    expected_learning_outcome: str

    task_type: str | None = None
    target_type: str | None = None
    default_difficulty: str | None = None
    estimated_minutes: int | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    produces: list[str] = Field(default_factory=list)

    priority_weight: float = 1.0
    requires_user_input: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExploreRecommendationContext(BaseModel):
    learner_id: uuid.UUID
    episode_id: uuid.UUID | None = None
    task_spec: dict[str, Any] | None = None
    knowledge_point_id: str | None = None
    knowledge_point_title: str | None = None
    learning_skill: str | None = None
    subskill: str | None = None
    grading_result: dict[str, Any] | None = None
    mastery_update: dict[str, Any] | None = None
    memory_context: dict[str, Any] | None = None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExploreCapabilityRecommendation(BaseModel):
    recommendation_id: str
    capability_id: str
    feature_id: str
    title: str
    reason: str
    priority_score: float
    category: str
    action: str
    tool_target: str | None = None
    route_hint: str | None = None
    prompt_seed: str | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    source: ExploreRecommendationSource = "rule"


LearningCapabilityRecommendation = ExploreCapabilityRecommendation


class StartExploreCapabilityRequest(BaseModel):
    learner_id: uuid.UUID
    target_id: str | None = None
    difficulty: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExploreCapabilityStartResponse(BaseModel):
    episode_id: str
    task_spec: dict[str, Any] | None = None
    status: str
    answer_required: bool
    prompt: str | None = None
    initial_payload: dict[str, Any] = Field(default_factory=dict)


class ExploreRecommendationsRequest(BaseModel):
    episode_id: uuid.UUID | None = None
    task_spec: dict[str, Any] | None = None
    knowledge_point_id: str | None = None
    knowledge_point_title: str | None = None
    learning_skill: str | None = None
    subskill: str | None = None
    grading_result: dict[str, Any] | None = None
    mastery_update: dict[str, Any] | None = None
    memory_context: dict[str, Any] | None = None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExploreRecommendationsResponse(BaseModel):
    recommendations: list[ExploreCapabilityRecommendation]


class ExploreCapabilityEventRequest(BaseModel):
    event_type: Literal["shown", "clicked", "dismissed", "completed"]
    episode_id: uuid.UUID | None = None
    recommendation_id: str | None = None
    reason: str | None = None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
