import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.learner import LearnerProfile


class ProfileStore:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, learner_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            select(LearnerProfile).where(LearnerProfile.learner_id == learner_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return {}
        return {
            "target_exam": profile.target_exam,
            "target_score": profile.target_score,
            "exam_date": profile.exam_date,
            "current_level": profile.current_level,
            "daily_time_budget_minutes": profile.daily_time_budget_minutes,
            "weak_skills": profile.weak_skills or [],
            "interest_topics": profile.interest_topics or [],
        }

    async def update_weak_skills(self, learner_id: uuid.UUID, skills: list[str]) -> None:
        result = await self.db.execute(
            select(LearnerProfile).where(LearnerProfile.learner_id == learner_id)
        )
        profile = result.scalar_one_or_none()
        if profile:
            profile.weak_skills = skills
            await self.db.commit()
