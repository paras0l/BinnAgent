from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.chat import router as chat_router
from src.api.conversations import router as conversations_router
from src.api.dashboard import router as dashboard_router
from src.api.debug import router as debug_router
from src.api.daily_lessons import router as daily_lessons_router
from src.api.evidence import router as evidence_router
from src.api.essay_review import router as essay_review_router
from src.api.explore import capabilities_router as explore_capabilities_router
from src.api.explore import router as explore_router
from src.api.exercises import router as exercises_router
from src.api.exercise_attempts import router as exercise_attempts_router
from src.api.grammar import router as grammar_router
from src.api.health import router as health_router
from src.api.knowledge import router as knowledge_router
from src.api.learners import router as learners_router
from src.api.learning_progress import router as learning_progress_router
from src.api.memory import router as memory_router
from src.api.prompts import router as prompts_router
from src.api.reading import router as reading_router
from src.api.recommendations import router as recommendations_router
from src.api.runtime import router as runtime_router
from src.api.sessions import router as sessions_router
from src.api.tools import router as tools_router
from src.api.vocabulary import router as vocabulary_router
from src.api.vocabulary_learning import learning_router, router as vocabulary_learning_router
from src.api.writing_phrases import router as writing_phrases_router
from src.cache import close_redis
from src.observability import shutdown_observability
from src.providers.router import router as model_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    try:
        yield
    finally:
        await close_redis()
        await model_router.close()
        shutdown_observability()


app = FastAPI(
    title="BinnAgent",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(learners_router)
app.include_router(conversations_router)
app.include_router(dashboard_router)
app.include_router(debug_router)
app.include_router(daily_lessons_router)
app.include_router(evidence_router)
app.include_router(explore_router)
app.include_router(explore_capabilities_router)
app.include_router(essay_review_router)
app.include_router(exercises_router)
app.include_router(exercise_attempts_router)
app.include_router(grammar_router)
app.include_router(learning_progress_router)
app.include_router(memory_router)
app.include_router(prompts_router)
app.include_router(reading_router)
app.include_router(recommendations_router)
app.include_router(runtime_router)
app.include_router(knowledge_router)
app.include_router(sessions_router)
app.include_router(tools_router)
app.include_router(vocabulary_router)
app.include_router(vocabulary_learning_router)
app.include_router(learning_router)
app.include_router(writing_phrases_router)
app.include_router(chat_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
