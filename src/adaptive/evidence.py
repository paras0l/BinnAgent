from typing import Literal

from pydantic import BaseModel, Field

EvidenceMode = Literal["recognition", "recall", "spelling", "listening", "context_use", "production"]


class AssessmentEvidenceInput(BaseModel):
    knowledge_point_id: str
    item_id: str
    evidence_mode: EvidenceMode = "recall"
    outcome_score: float = Field(ge=0.0, le=1.0)
    independent: bool = True
    hint_count: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    response_time_ms: int | None = Field(default=None, ge=0)
    error_tags: list[str] = Field(default_factory=list)
    semantic_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    item_difficulty_prior: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_ref: str
    interaction_type: Literal["assessment", "browsing", "explanation", "answer_reveal"] = (
        "assessment"
    )


class EvidenceDecision(BaseModel):
    accepted: bool
    reason: str
    updates_learning_state: bool


def evaluate_evidence(
    evidence: AssessmentEvidenceInput,
    *,
    confidence_threshold: float = 0.65,
) -> EvidenceDecision:
    if evidence.interaction_type != "assessment":
        return EvidenceDecision(
            accepted=False,
            reason=f"interaction_type_{evidence.interaction_type}_is_not_assessment",
            updates_learning_state=False,
        )
    if evidence.semantic_confidence < confidence_threshold:
        return EvidenceDecision(
            accepted=True,
            reason="semantic_confidence_below_update_threshold",
            updates_learning_state=False,
        )
    return EvidenceDecision(accepted=True, reason="assessment_evidence_accepted", updates_learning_state=True)
