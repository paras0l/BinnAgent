import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class GroupLearningSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "group_learning_sources"
    __table_args__ = (
        UniqueConstraint(
            "learner_id",
            "platform",
            "external_group_key",
            name="uq_group_learning_source_learner_external_key",
        ),
        Index("ix_group_learning_sources_learner_status", "learner_id", "status"),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(30), nullable=False, default="feishu")
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="group")
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    external_group_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    last_cursor: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_import_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sync_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    import_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="silent")
    allowed_senders: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    raw_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    auto_generate_recommendations: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    auto_write_candidates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_apply_high_confidence_tagged_signals: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)


class GroupLearningParticipant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "group_learning_participants"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "external_member_key",
            name="uq_group_learning_participant_source_member",
        ),
        Index("ix_group_learning_participants_source_role", "source_id", "role"),
        Index("ix_group_learning_participants_learner", "learner_id"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("group_learning_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_member_key: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    learner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="SET NULL"),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    analysis_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class GroupLearningMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "group_learning_messages"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "external_message_id",
            name="uq_group_learning_message_source_external",
        ),
        UniqueConstraint(
            "source_id",
            "content_hash",
            name="uq_group_learning_message_source_hash",
        ),
        Index("ix_group_learning_messages_source_occurred", "source_id", "occurred_at"),
        Index("ix_group_learning_messages_learner_status", "learner_id", "ingestion_status"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("group_learning_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_member_key: Mapped[str] = mapped_column(String(255), nullable=False)
    learner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    message_type: Mapped[str] = mapped_column(String(30), nullable=False, default="text")
    content_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    language_mix: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingestion_status: Mapped[str] = mapped_column(String(40), nullable=False, default="processed")
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class GroupLearningSignal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "group_learning_signals"
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "signal_type",
            "target_label",
            name="uq_group_learning_signal_message_type_target",
        ),
        Index("ix_group_learning_signals_learner_status", "learner_id", "status"),
        Index("ix_group_learning_signals_learner_type", "learner_id", "signal_type"),
    )

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("group_learning_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_label: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="candidate")
    applied_target_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    applied_target_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
