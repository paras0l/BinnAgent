import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.memory.layers import MemoryLayer


@dataclass(frozen=True)
class MemoryEventInput:
    learner_id: uuid.UUID
    event_type: str
    skill: str = "general"
    subskill: str | None = None
    source_type: str = "system"
    source_id: str | None = None
    thread_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    visibility: str = "private"
    created_by: str = "system"
    occurred_at: datetime | None = None


@dataclass(frozen=True)
class MemoryOperationInput:
    learner_id: uuid.UUID
    operation_type: str
    target_type: str
    target_id: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    reason: str | None = None
    created_by: str = "user"


@dataclass(frozen=True)
class RetrievedMemoryItem:
    id: str
    type: str
    skill: str
    summary: str
    confidence: float
    layer: str
    evidence_refs: list[str] = field(default_factory=list)
    reason: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryContext:
    loaded_items: list[RetrievedMemoryItem]
    excluded_items: list[str] = field(default_factory=list)
    retrieval_reason: str = "general"
    layer: str = MemoryLayer.CONTEXT.value

    def prompt_text(self) -> str:
        if not self.loaded_items:
            return ""
        lines = ["相关学习记忆（只在与当前回答相关时使用）："]
        for item in self.loaded_items:
            evidence = f" 证据：{', '.join(item.evidence_refs[:2])}" if item.evidence_refs else ""
            lines.append(
                f"- [{item.layer}/{item.skill}] {item.summary} "
                f"(confidence={item.confidence:.2f}).{evidence}".strip()
            )
        return "\n".join(lines)
