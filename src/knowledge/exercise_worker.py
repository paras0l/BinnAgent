from __future__ import annotations

import asyncio
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config import settings
from src.db import async_session_factory
from src.knowledge.exercise_pool import (
    claim_next_exercise_run,
    mark_exercise_run_failed,
    maybe_enqueue_followup_refill,
    process_exercise_generation_run,
)
from src.models.knowledge import ExerciseGenerationRun
from src.providers.router import ModelRouter, router

SessionFactory = async_sessionmaker[AsyncSession]


async def run_exercise_worker_once(
    *,
    session_factory: SessionFactory = async_session_factory,
    model_router: ModelRouter = router,
) -> bool:
    async with session_factory() as claim_db:
        run = await claim_next_exercise_run(claim_db)
        if run is None:
            await claim_db.rollback()
            return False
        run_id = run.id
        await claim_db.commit()

    try:
        async with session_factory() as work_db:
            result = await work_db.execute(
                select(ExerciseGenerationRun).where(ExerciseGenerationRun.id == run_id)
            )
            active_run = result.scalar_one()
            await process_exercise_generation_run(
                work_db,
                run=active_run,
                model_router=model_router,
            )
            await maybe_enqueue_followup_refill(work_db, run=active_run)
            await work_db.commit()
        return True
    except Exception as exc:
        async with session_factory() as failure_db:
            result = await failure_db.execute(
                select(ExerciseGenerationRun).where(ExerciseGenerationRun.id == run_id)
            )
            failed_run = result.scalar_one_or_none()
            if failed_run is not None:
                await mark_exercise_run_failed(failure_db, run=failed_run, error=exc)
                await failure_db.commit()
        return True


async def run_exercise_worker_forever(
    *,
    session_factory: SessionFactory = async_session_factory,
    model_router: ModelRouter = router,
    should_stop: Callable[[], bool] | None = None,
) -> None:
    should_stop = should_stop or (lambda: False)
    while not should_stop():
        processed = await run_exercise_worker_once(
            session_factory=session_factory,
            model_router=model_router,
        )
        if not processed:
            await asyncio.sleep(settings.exercise_worker_poll_seconds)
