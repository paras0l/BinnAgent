import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.error_pattern import ErrorPattern


class ErrorStore:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_error(
        self,
        learner_id: uuid.UUID,
        skill: str,
        pattern: str,
        description: str | None = None,
        severity: str | None = None,
        evidence_ref: str | None = None,
    ) -> ErrorPattern:
        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(ErrorPattern).where(
                ErrorPattern.learner_id == learner_id,
                ErrorPattern.pattern == pattern,
                ErrorPattern.skill == skill,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.frequency += 1
            existing.last_seen_at = now

            if evidence_ref:
                refs = list(existing.evidence_refs) if existing.evidence_refs else []
                refs.append(evidence_ref)
                existing.evidence_refs = refs

            if existing.frequency >= 10:
                existing.severity = "high"
            elif existing.frequency >= 5:
                existing.severity = "medium"

            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        error = ErrorPattern(
            learner_id=learner_id,
            skill=skill,
            pattern=pattern,
            description=description,
            frequency=1,
            severity=severity,
            evidence_refs=[evidence_ref] if evidence_ref else [],
            last_seen_at=now,
        )
        self.db.add(error)
        await self.db.commit()
        await self.db.refresh(error)
        return error

    async def get_top_errors(
        self,
        learner_id: uuid.UUID,
        skill: str | None = None,
        limit: int = 5,
    ) -> list[ErrorPattern]:
        query = select(ErrorPattern).where(ErrorPattern.learner_id == learner_id)
        if skill:
            query = query.where(ErrorPattern.skill == skill)
        query = query.order_by(ErrorPattern.frequency.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())
