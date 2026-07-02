from typing import Any

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    evidence_type: str
    evidence_id: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reason: str | None = None
    used_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceBundle(BaseModel):
    refs: list[EvidenceRef] = Field(default_factory=list)
    summary: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class EvidenceResolution(BaseModel):
    ref: EvidenceRef
    found: bool
    title: str | None = None
    content: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
