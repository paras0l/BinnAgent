import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.base import UUIDPrimaryKeyMixin


class PromptExecutionRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "prompt_execution_records"
    __table_args__ = (
        Index("ix_prompt_execution_records_prompt", "prompt_id", "prompt_version"),
        Index("ix_prompt_execution_records_learner_created", "learner_id", "created_at"),
        Index("ix_prompt_execution_records_episode_id", "episode_id"),
        Index("ix_prompt_execution_records_source_module", "source_module"),
        Index("ix_prompt_execution_records_decision", "decision"),
        Index(
            "ix_prompt_execution_records_schema_validation_status",
            "schema_validation_status",
        ),
    )

    learner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="SET NULL"),
        nullable=True,
    )
    episode_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_episodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_module: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_id: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_schema: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    output_schema: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    model_policy_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    adaptive_policy_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    teaching_policy_decision_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teaching_policy_decisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    langfuse_trace_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    langfuse_observation_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    schema_validation_status: Mapped[str] = mapped_column(String(30), nullable=False)
    schema_error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    repair_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parse_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    target_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
