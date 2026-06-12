from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.health import router as health_router
from src.api.learners import router as learners_router
from src.api.sessions import router as sessions_router
from src.api.vocabulary import router as vocabulary_router
from src.api.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


app = FastAPI(
    title="BinnAgent",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(learners_router)
app.include_router(sessions_router)
app.include_router(vocabulary_router)
app.include_router(chat_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
