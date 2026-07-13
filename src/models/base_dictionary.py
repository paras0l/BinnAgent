import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class BaseDictionaryBuild(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One reproducible build of the shared, learner-independent dictionary."""

    __tablename__ = "base_dictionary_builds"

    version: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="staged")
    source_manifest: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    selection_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    statistics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class BaseDictionaryEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A shared lexical entry. Learner state must never be stored on this row."""

    __tablename__ = "base_dictionary_entries"
    __table_args__ = (
        UniqueConstraint("canonical_key", "entry_kind", name="uq_base_dictionary_key_kind"),
        Index("ix_base_dictionary_frequency_rank", "frequency_rank"),
        Index("ix_base_dictionary_kind_rank", "entry_kind", "frequency_rank"),
        Index("ix_base_dictionary_active_key", "active", "canonical_key"),
    )

    canonical_key: Mapped[str] = mapped_column(String(255), nullable=False)
    lemma: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    entry_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="word")
    frequency_zipf: Mapped[float] = mapped_column(Float, nullable=False)
    frequency_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    parts_of_speech: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    pronunciations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    forms: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    senses: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    relations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    examples: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_attribution: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    build_version: Mapped[str] = mapped_column(String(80), nullable=False)
    active: Mapped[bool] = mapped_column(nullable=False, default=True)


class BaseDictionaryTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Generated Chinese definitions kept separate from source-owned English senses."""

    __tablename__ = "base_dictionary_translations"
    __table_args__ = (
        UniqueConstraint(
            "entry_id", "sense_key", "locale", name="uq_base_dictionary_translation_sense"
        ),
        Index("ix_base_dictionary_translation_entry", "entry_id", "locale"),
    )

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("base_dictionary_entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    sense_key: Mapped[str] = mapped_column(String(120), nullable=False)
    locale: Mapped[str] = mapped_column(String(16), nullable=False, default="zh-CN")
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    generator: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    source_definition_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
