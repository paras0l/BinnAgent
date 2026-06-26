import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.curator import MemoryCurator
from src.memory.retriever import MemoryRetriever
from src.memory.schemas import MemoryContext, MemoryEventInput
from src.memory.writer import MemoryWriter
from src.models.memory import LearningMemoryEvent


class MemoryManager:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.writer = MemoryWriter(db)
        self.retriever = MemoryRetriever(db)
        self.curator = MemoryCurator(db)

    async def record_and_curate(
        self, event: MemoryEventInput, *, commit: bool = False
    ) -> LearningMemoryEvent:
        row = await self.writer.record_event(event)
        await self.curator.curate_learner(event.learner_id)
        if commit:
            await self.db.commit()
        return row

    async def retrieve(
        self,
        *,
        learner_id: uuid.UUID,
        reason: str,
        skill: str | None = None,
        thread_id: uuid.UUID | None = None,
        limit: int = 8,
    ) -> MemoryContext:
        return await self.retriever.retrieve_context(
            learner_id=learner_id,
            reason=reason,
            skill=skill,
            thread_id=thread_id,
            limit=limit,
        )

    async def curate(self, learner_id: uuid.UUID, *, commit: bool = False) -> dict[str, Any]:
        return await self.curator.curate_learner(learner_id, commit=commit)
