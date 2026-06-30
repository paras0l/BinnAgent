import uuid

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ReadingMaterialHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reading_material_histories"
    __table_args__ = (
        UniqueConstraint(
            "learner_id",
            "text_hash",
            name="uq_reading_material_histories_learner_text_hash",
        ),
        Index("ix_reading_material_histories_learner_updated", "learner_id", "updated_at"),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(30), nullable=False, default="general")
    goal: Mapped[str] = mapped_column(String(30), nullable=False, default="mixed")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sentence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="reading_workshop")
