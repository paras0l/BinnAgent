import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ExploreFeaturePreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "explore_feature_preferences"
    __table_args__ = (
        UniqueConstraint(
            "learner_id",
            "feature_id",
            name="uq_explore_feature_preferences_learner_feature",
        ),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_id: Mapped[str] = mapped_column(String(100), nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<ExploreFeaturePreference {self.feature_id} learner={self.learner_id}>"
