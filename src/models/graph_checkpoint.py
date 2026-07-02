import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class LearningGraphCheckpoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_graph_checkpoints"
    __table_args__ = (
        Index(
            "uq_learning_graph_checkpoints_active_waiting_episode",
            "episode_id",
            unique=True,
            postgresql_where=text("status = 'waiting_user'"),
        ),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    episode_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_episodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    checkpoint_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    resume_from: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    state_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    required_input_schema: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    prompt_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<LearningGraphCheckpoint {self.status} episode={self.episode_id}>"
