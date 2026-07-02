from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LearningEventCreate(BaseModel):
    episode_id: str
    learner_id: str
    event_type: str
    source_module: str
    target_type: str | None = None
    target_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class LearningEventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    episode_id: str
    learner_id: str
    event_type: str
    source_module: str
    target_type: str | None = None
    target_id: str | None = None
    payload: dict[str, Any]
    occurred_at: datetime
