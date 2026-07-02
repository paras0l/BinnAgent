from typing import Any

from pydantic import BaseModel, Field


class TaskTarget(BaseModel):
    target_type: str
    target_id: str | None = None
    label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SuccessCriteria(BaseModel):
    min_accuracy: float | None = None
    max_hint_count: int | None = None
    requires_explanation: bool = False
    required_outputs: list[str] = Field(default_factory=list)


class VerificationPolicy(BaseModel):
    required_checks: list[str] = Field(default_factory=list)
    allow_llm_judge: bool = False
    require_evidence: bool = True


class TaskSpec(BaseModel):
    task_id: str
    task_type: str
    source: str
    objective: str
    target: TaskTarget
    difficulty: str | None = None
    required_inputs: list[str] = Field(default_factory=list)
    expected_output: dict[str, Any] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=list)
    success_criteria: SuccessCriteria
    verification_policy: VerificationPolicy
    metadata: dict[str, Any] = Field(default_factory=dict)
