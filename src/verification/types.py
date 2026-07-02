from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.evidence.types import EvidenceRef


class VerificationCheck(BaseModel):
    name: str
    check_type: str
    passed: bool
    expected: Any | None = None
    actual: Any | None = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    message: str | None = None


class VerificationReport(BaseModel):
    episode_id: str
    task_id: str | None = None
    status: str
    checks: list[VerificationCheck]
    failed_reason: str | None = None
    generated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
