from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.evidence.types import EvidenceRef


class AttemptSignal(BaseModel):
    learner_id: str
    target_type: str
    target_id: str
    correct: bool
    score: float | None = None
    error_type: str | None = None
    hint_count: int = 0
    retry_count: int = 0
    response_time_ms: int | None = None
    source: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MasteryUpdateResult(BaseModel):
    learner_id: str
    target_type: str
    target_id: str
    previous_score: float | None = None
    new_score: float
    previous_confidence: float | None = None
    new_confidence: float
    mastery_delta: float
    weakness_tags: list[str] = Field(default_factory=list)
    forgetting_risk: float | None = None
    next_review_at: datetime | None = None
    status: str | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
