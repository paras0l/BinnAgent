import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class AgentThread(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_threads"

    learner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )

    def __repr__(self) -> str:
        return f"<AgentThread {self.id} learner={self.learner_id}>"


class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"

    thread_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    graph_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    model_usage: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AgentRun {self.graph_name} thread={self.thread_id}>"


class AgentEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_events"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    node_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    def __repr__(self) -> str:
        return f"<AgentEvent {self.event_type} run={self.run_id}>"


class ToolCall(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tool_calls"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    node_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ToolCall {self.tool_name} run={self.run_id}>"


class ModelCallLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "model_call_logs"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    node_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    task_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    local_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    prompt_chars: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_chars: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    retry_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    fallback_from: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fallback_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ModelCallLog {self.provider}/{self.model} run={self.run_id}>"
