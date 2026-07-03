from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.evidence.types import EvidenceRef


class VerificationCheck(BaseModel):
    name: str
    check_type: str
    passed: bool
    severity: str = "warning"
    expected: Any | None = None
    actual: Any | None = None
    source_node: str | None = None
    source_event_type: str | None = None
    source_tool_name: str | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    message: str


class VerificationReport(BaseModel):
    episode_id: str
    task_id: str | None = None
    status: str
    required_checks: list[str] = Field(default_factory=list)
    checks: list[VerificationCheck]
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0
    critical_failed_count: int = 0
    evidence_ref_count: int = 0
    failed_reason: str | None = None
    generated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
