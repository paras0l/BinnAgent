# BinnAgent MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working English learning companion agent MVP with LangGraph runtime, Ollama model provider, vocabulary memory, spaced repetition, reading/writing training, and weekly reports.

**Architecture:** FastAPI backend with LangGraph state machine for learning sessions. PostgreSQL for persistence, Ollama for local LLM. Multi-agent architecture with Learning Supervisor dispatching to skill agents (Vocabulary, Reading, Writing). Memory system tracks vocabulary, error patterns, and learning progress.

**Tech Stack:** Python 3.11+, FastAPI, LangGraph, SQLAlchemy 2.0, PostgreSQL + pgvector, Redis (optional), Ollama (local LLM), Pydantic v2, pytest

---

## File Structure

```
src/
├── __init__.py
├── main.py                      # FastAPI app entry
├── config.py                    # Settings / config
├── api/
│   ├── __init__.py
│   ├── deps.py                  # Dependencies (db, model client)
│   ├── health.py                # Health check endpoints
│   ├── learners.py              # User profile CRUD
│   ├── sessions.py              # Learning session endpoints
│   └── vocabulary.py            # Vocabulary endpoints
├── models/
│   ├── __init__.py
│   ├── base.py                  # SQLAlchemy base + mixins
│   ├── learner.py               # Learner + LearnerProfile models
│   ├── session.py               # LearningSession + LearningTask
│   ├── vocabulary.py            # VocabularyItem + ReviewSchedule
│   ├── error_pattern.py         # ErrorPattern model
│   └── runtime.py               # AgentThread, AgentRun, AgentEvent, ToolCall, ModelCallLog
├── providers/
│   ├── __init__.py
│   ├── base.py                  # ModelClient Protocol + ChatRequest/Response
│   ├── ollama.py                # Ollama provider implementation
│   └── router.py                # Model Router (selects provider/model)
├── memory/
│   ├── __init__.py
│   ├── vocabulary_store.py      # CRUD + SRS read/write
│   ├── error_store.py           # Error pattern CRUD
│   └── profile_store.py         # Learner profile CRUD
├── graph/
│   ├── __init__.py
│   ├── state.py                 # LearningState TypedDict
│   ├── main_graph.py            # Top-level daily lesson graph
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── load_profile.py
│   │   ├── detect_intent.py
│   │   ├── select_goal.py
│   │   ├── route_skill.py
│   │   ├── run_task.py
│   │   ├── generate_feedback.py
│   │   ├── update_memory.py
│   │   ├── schedule_review.py
│   │   └── summarize.py
│   └── agents/
│       ├── __init__.py
│       ├── supervisor.py
│       ├── vocabulary.py
│       ├── reading.py
│       └── writing.py
├── tools/
│   ├── __init__.py
│   ├── dictionary.py            # Dictionary Tool (local + provider protocol)
│   ├── srs.py                   # Spaced Repetition Scheduler
│   ├── question_bank.py         # CET Question Bank (mock data)
│   └── essay_scoring.py         # Essay Scoring Tool
└── db.py                        # Database engine + session factory

tests/
├── __init__.py
├── conftest.py                  # Fixtures (db, test client, mock ollama)
├── api/
│   ├── test_health.py
│   ├── test_learners.py
│   └── test_vocabulary.py
├── memory/
│   ├── test_vocabulary_store.py
│   ├── test_error_store.py
│   └── test_profile_store.py
├── providers/
│   └── test_ollama.py
├── tools/
│   ├── test_srs.py
│   ├── test_dictionary.py
│   └── test_question_bank.py
├── graph/
│   └── test_main_graph.py
└── integration/
    └── test_full_session.py
```

---

## Task 1: Project Skeleton & Configuration

**Files:**
- Create: `src/__init__.py`, `src/config.py`, `src/main.py`, `src/db.py`
- Create: `tests/__init__.py`, `tests/conftest.py`
- Create: `pyproject.toml`, `.env.example`

- [ ] **Step 1: Create pyproject.toml with dependencies**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "binn-agent"
version = "0.1.0"
description = "English Learning Companion Agent based on LangGraph"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "langgraph>=0.2.50",
    "httpx>=0.28.0",
    "redis>=5.2.0",
    "pgvector>=0.3.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "httpx>=0.28.0",
    "ruff>=0.8.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create src/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "BINN_", "env_file": ".env", "extra": "ignore"}

    # Database
    database_url: str = "postgresql+asyncpg://binn:binn@localhost:5432/binn_agent"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen3:latest"
    ollama_utility_model: str = "qwen3:latest"
    ollama_embedding_model: str = "nomic-embed-text:latest"

    # Fallback (disabled by default)
    fallback_enabled: bool = False

    # Redis (optional)
    redis_url: str = "redis://localhost:6379/0"

    # App
    debug: bool = False


settings = Settings()
```

- [ ] **Step 3: Create src/db.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
```

- [ ] **Step 4: Create src/main.py**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: check Ollama health
    yield
    # Shutdown: cleanup


app = FastAPI(
    title="BinnAgent",
    description="English Learning Companion Agent",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
```

- [ ] **Step 5: Create tests/conftest.py**

```python
import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

- [ ] **Step 6: Create tests/test_health.py**

```python
import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
```

- [ ] **Step 7: Run tests to verify skeleton works**

Run: `cd /Users/binge/Documents/BinnAgent && python -m pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 8: Create .env.example**

```env
BINN_DATABASE_URL=postgresql+asyncpg://binn:binn@localhost:5432/binn_agent
BINN_OLLAMA_BASE_URL=http://localhost:11434
BINN_OLLAMA_CHAT_MODEL=qwen3:latest
BINN_OLLAMA_UTILITY_MODEL=qwen3:latest
BINN_DEBUG=false
```

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml src/ tests/ .env.example
git commit -m "feat: add project skeleton with FastAPI, config, and db setup"
```

---

## Task 2: Database Models

**Files:**
- Create: `src/models/__init__.py`, `src/models/base.py`, `src/models/learner.py`, `src/models/session.py`, `src/models/vocabulary.py`, `src/models/error_pattern.py`, `src/models/runtime.py`
- Modify: `src/db.py` (add Base import)
- Create: `tests/models/__init__.py`, `tests/models/test_learner_model.py`

- [ ] **Step 1: Create src/models/base.py**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
```

- [ ] **Step 2: Create src/models/learner.py**

```python
import uuid

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Learner(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learners"

    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    profile: Mapped["LearnerProfile | None"] = relationship(back_populates="learner", uselist=False)


class LearnerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learner_profiles"

    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    target_exam: Mapped[str] = mapped_column(String(20), nullable=False)  # CET4 / CET6
    target_score: Mapped[int | None] = mapped_column(nullable=True)
    exam_date: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ISO date
    current_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    daily_time_budget_minutes: Mapped[int] = mapped_column(nullable=False, default=30)
    preferred_study_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    interest_topics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    weak_skills: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    learner: Mapped["Learner"] = relationship(back_populates="profile")
```

- [ ] **Step 3: Create src/models/session.py**

```python
import uuid

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LearningSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_sessions"

    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    thread_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    session_type: Mapped[str] = mapped_column(String(50), nullable=False, default="daily_lesson")
    active_skill: Mapped[str | None] = mapped_column(String(50), nullable=True)
    today_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    started_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class LearningTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_tasks"

    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    skill: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    estimated_minutes: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    input_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
```

- [ ] **Step 4: Create src/models/vocabulary.py**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class VocabularyItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vocabulary_items"

    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    word: Mapped[str] = mapped_column(String(100), nullable=False)
    phonetic: Mapped[str | None] = mapped_column(String(100), nullable=True)
    level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    meanings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    collocations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    examples: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")  # new, learning, mastered
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reviewed_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    next_review_at: Mapped[str | None] = mapped_column(String(30), nullable=True)

    __table_args__ = (
        # UniqueConstraint("learner_id", "word", name="uq_learner_word"),
    )


class ReviewSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_schedules"

    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    item_type: Mapped[str] = mapped_column(String(50), nullable=False)  # vocabulary, error_pattern
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scheduled_at: Mapped[str] = mapped_column(String(30), nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    result: Mapped[str | None] = mapped_column(String(20), nullable=True)  # correct, wrong, skipped
    response_time_ms: Mapped[int | None] = mapped_column(nullable=True)
    confidence_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_next_drill: Mapped[str | None] = mapped_column(String(100), nullable=True)
```

- [ ] **Step 5: Create src/models/error_pattern.py**

```python
import uuid

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ErrorPattern(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "error_patterns"

    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    skill: Mapped[str] = mapped_column(String(50), nullable=False)
    pattern: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="low")  # low, medium, high
    evidence_refs: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    recommended_drill: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_seen_at: Mapped[str | None] = mapped_column(String(30), nullable=True)

    __table_args__ = (
        # UniqueConstraint("learner_id", "skill", "pattern", name="uq_learner_skill_pattern"),
    )
```

- [ ] **Step 6: Create src/models/runtime.py**

```python
import uuid

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentThread(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_threads"

    learner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)


class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"

    thread_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    graph_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    model_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_events"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    node_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ToolCall(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tool_calls"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    node_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ModelCallLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "model_call_logs"

    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    node_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    task_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    local_only: Mapped[bool] = mapped_column(nullable=False, default=True)
    prompt_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fallback_from: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 7: Update src/models/__init__.py**

```python
from src.models.base import Base
from src.models.learner import Learner, LearnerProfile
from src.models.session import LearningSession, LearningTask
from src.models.vocabulary import VocabularyItem, ReviewSchedule
from src.models.error_pattern import ErrorPattern
from src.models.runtime import AgentThread, AgentRun, AgentEvent, ToolCall, ModelCallLog

__all__ = [
    "Base",
    "Learner",
    "LearnerProfile",
    "LearningSession",
    "LearningTask",
    "VocabularyItem",
    "ReviewSchedule",
    "ErrorPattern",
    "AgentThread",
    "AgentRun",
    "AgentEvent",
    "ToolCall",
    "ModelCallLog",
]
```

- [ ] **Step 8: Create Alembic init and migration**

Run: `cd /Users/binge/Documents/BinnAgent && alembic init alembic`

Modify `alembic/env.py` to import Base from src.models and set target_metadata.

- [ ] **Step 9: Generate and run migration**

Run: `alembic revision --autogenerate -m "initial tables" && alembic upgrade head`

- [ ] **Step 10: Commit**

```bash
git add src/models/ alembic/ alembic.ini
git commit -m "feat: add database models for all MVP tables"
```

---

## Task 3: Ollama Model Provider

**Files:**
- Create: `src/providers/__init__.py`, `src/providers/base.py`, `src/providers/ollama.py`, `src/providers/router.py`
- Create: `tests/providers/__init__.py`, `tests/providers/test_ollama.py`

- [ ] **Step 1: Create src/providers/base.py**

```python
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ChatRequest:
    messages: list[dict[str, str]]
    task_type: str = "general"
    temperature: float = 0.3
    max_tokens: int = 2000
    response_schema: dict[str, Any] | None = None
    preferred_provider: str = "ollama"
    preferred_model: str | None = None
    local_only: bool = True


@dataclass
class ChatResponse:
    provider: str
    model: str
    content: str
    structured: dict[str, Any] | None = None
    latency_ms: int = 0
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str = "stop"


class ModelClient(Protocol):
    async def chat(self, request: ChatRequest) -> ChatResponse: ...

    async def health_check(self) -> dict[str, Any]: ...
```

- [ ] **Step 2: Create src/providers/ollama.py**

```python
import time

import httpx

from src.config import settings
from src.providers.base import ChatRequest, ChatResponse


class OllamaClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=120.0)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        model = request.preferred_model or settings.ollama_chat_model

        messages = [{"role": m["role"], "content": m["content"]} for m in request.messages]

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        if request.response_schema:
            payload["format"] = "json"

        start = time.monotonic()
        resp = await self._client.post("/api/chat", json=payload)
        latency_ms = int((time.monotonic() - start) * 1000)
        resp.raise_for_status()
        data = resp.json()

        content = data.get("message", {}).get("content", "")

        return ChatResponse(
            provider="ollama",
            model=model,
            content=content,
            latency_ms=latency_ms,
            usage={
                "prompt_eval_count": data.get("prompt_eval_count"),
                "eval_count": data.get("eval_count"),
            },
            finish_reason="stop",
        )

    async def health_check(self) -> dict[str, Any]:
        try:
            resp = await self._client.get("/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return {
                "reachable": True,
                "chat_model": {
                    "name": settings.ollama_chat_model,
                    "available": settings.ollama_chat_model in models,
                },
                "embedding_model": {
                    "name": settings.ollama_embedding_model,
                    "available": settings.ollama_embedding_model in models,
                },
            }
        except Exception as e:
            return {"reachable": False, "error": str(e)}

    async def close(self):
        await self._client.aclose()
```

- [ ] **Step 3: Create src/providers/router.py**

```python
from src.providers.base import ChatRequest, ChatResponse, ModelClient
from src.providers.ollama import OllamaClient


class ModelRouter:
    def __init__(self):
        self._ollama = OllamaClient()
        self._clients: dict[str, ModelClient] = {"ollama": self._ollama}

    async def chat(self, request: ChatRequest) -> ChatResponse:
        provider = request.preferred_provider
        client = self._clients.get(provider)
        if not client:
            client = self._ollama
        return await client.chat(request)

    async def health_check(self) -> dict[str, dict]:
        return {"ollama": await self._ollama.health_check()}

    async def close(self):
        await self._ollama.close()


router = ModelRouter()
```

- [ ] **Step 4: Create tests/providers/test_ollama.py**

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.providers.base import ChatRequest, ChatResponse
from src.providers.ollama import OllamaClient


@pytest.fixture
def ollama_client():
    return OllamaClient(base_url="http://localhost:11434")


@pytest.mark.asyncio
async def test_chat_returns_response(ollama_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {"content": "Hello!"},
        "prompt_eval_count": 10,
        "eval_count": 5,
    }
    mock_response.raise_for_status = MagicMock()

    with patch.object(ollama_client._client, "post", new_callable=AsyncMock, return_value=mock_response):
        request = ChatRequest(messages=[{"role": "user", "content": "Hi"}])
        response = await ollama_client.chat(request)

        assert response.provider == "ollama"
        assert response.content == "Hello!"
        assert response.latency_ms >= 0
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/binge/Documents/BinnAgent && python -m pytest tests/providers/test_ollama.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/providers/ tests/providers/
git commit -m "feat: add Ollama model provider with health check and router"
```

---

## Task 4: API Endpoints (Health + Learners)

**Files:**
- Create: `src/api/__init__.py`, `src/api/deps.py`, `src/api/health.py`, `src/api/learners.py`
- Create: `tests/api/__init__.py`, `tests/api/test_health.py`, `tests/api/test_learners.py`
- Modify: `src/main.py` (register routers)

- [ ] **Step 1: Create src/api/deps.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import async_session_factory
from src.providers.router import ModelRouter, router


async def get_db_session():
    async with async_session_factory() as session:
        yield session


def get_model_router() -> ModelRouter:
    return router
```

- [ ] **Step 2: Create src/api/health.py**

```python
from fastapi import APIRouter, Depends

from src.providers.router import ModelRouter
from src.api.deps import get_model_router

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/model/health")
async def model_health(model_router: ModelRouter = Depends(get_model_router)):
    return await model_router.health_check()
```

- [ ] **Step 3: Create src/api/learners.py**

```python
import uuid
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.models.learner import Learner, LearnerProfile

router = APIRouter(prefix="/api/learners", tags=["learners"])


class CreateLearnerRequest(BaseModel):
    nickname: str
    email: str | None = None


class CreateProfileRequest(BaseModel):
    target_exam: str  # CET4 / CET6
    target_score: int | None = None
    exam_date: str | None = None
    daily_time_budget_minutes: int = 30


class LearnerResponse(BaseModel):
    id: uuid.UUID
    nickname: str
    email: str | None = None

    model_config = {"from_attributes": True}


class ProfileResponse(BaseModel):
    id: uuid.UUID
    learner_id: uuid.UUID
    target_exam: str
    target_score: int | None = None
    exam_date: str | None = None
    daily_time_budget_minutes: int = 30

    model_config = {"from_attributes": True}


@router.post("", response_model=LearnerResponse)
async def create_learner(req: CreateLearnerRequest, db: AsyncSession = Depends(get_db_session)):
    learner = Learner(nickname=req.nickname, email=req.email)
    db.add(learner)
    await db.commit()
    await db.refresh(learner)
    return learner


@router.get("/{learner_id}", response_model=LearnerResponse)
async def get_learner(learner_id: uuid.UUID, db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(Learner).where(Learner.id == learner_id))
    learner = result.scalar_one_or_none()
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    return learner


@router.post("/{learner_id}/profile", response_model=ProfileResponse)
async def create_profile(
    learner_id: uuid.UUID,
    req: CreateProfileRequest,
    db: AsyncSession = Depends(get_db_session),
):
    # Verify learner exists
    result = await db.execute(select(Learner).where(Learner.id == learner_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Learner not found")

    profile = LearnerProfile(
        learner_id=learner_id,
        target_exam=req.target_exam,
        target_score=req.target_score,
        exam_date=req.exam_date,
        daily_time_budget_minutes=req.daily_time_budget_minutes,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/{learner_id}/profile", response_model=ProfileResponse)
async def get_profile(learner_id: uuid.UUID, db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == learner_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile
```

- [ ] **Step 4: Update src/main.py to register routers**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import settings
from src.api.health import router as health_router
from src.api.learners import router as learners_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="BinnAgent",
    description="English Learning Companion Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(learners_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
```

- [ ] **Step 5: Create tests/api/test_learners.py**

```python
import pytest


@pytest.mark.asyncio
async def test_create_learner(client):
    response = await client.post("/api/learners", json={"nickname": "Test User"})
    assert response.status_code == 200
    data = response.json()
    assert data["nickname"] == "Test User"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_and_get_profile(client):
    # Create learner first
    resp = await client.post("/api/learners", json={"nickname": "Test"})
    learner_id = resp.json()["id"]

    # Create profile
    resp = await client.post(
        f"/api/learners/{learner_id}/profile",
        json={"target_exam": "CET6", "daily_time_budget_minutes": 45},
    )
    assert resp.status_code == 200
    profile = resp.json()
    assert profile["target_exam"] == "CET6"
    assert profile["daily_time_budget_minutes"] == 45

    # Get profile
    resp = await client.get(f"/api/learners/{learner_id}/profile")
    assert resp.status_code == 200
    assert resp.json()["target_exam"] == "CET6"
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/binge/Documents/BinnAgent && python -m pytest tests/api/ -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/api/ tests/api/
git commit -m "feat: add health and learner profile API endpoints"
```

---

## Task 5: Memory Stores (Profile + Vocabulary + Error)

**Files:**
- Create: `src/memory/__init__.py`, `src/memory/profile_store.py`, `src/memory/vocabulary_store.py`, `src/memory/error_store.py`
- Create: `tests/memory/__init__.py`, `tests/memory/test_profile_store.py`, `tests/memory/test_vocabulary_store.py`

- [ ] **Step 1: Create src/memory/profile_store.py**

```python
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.learner import Learner, LearnerProfile


class ProfileStore:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, learner_id: uuid.UUID) -> dict:
        result = await self.db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == learner_id))
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
        result = await self.db.execute(select(LearnerProfile).where(LearnerProfile.learner_id == learner_id))
        profile = result.scalar_one_or_none()
        if profile:
            profile.weak_skills = {"skills": skills}
            await self.db.commit()
```

- [ ] **Step 2: Create src/memory/vocabulary_store.py**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.vocabulary import VocabularyItem, ReviewSchedule


class VocabularyStore:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_word(
        self,
        learner_id: uuid.UUID,
        word: str,
        phonetic: str | None = None,
        level: str | None = None,
        meanings: list[str] | None = None,
        collocations: list[str] | None = None,
        examples: list[str] | None = None,
        source_ref: str | None = None,
    ) -> VocabularyItem:
        # Check if word already exists for this learner
        existing = await self.get_word(learner_id, word)
        if existing:
            return existing

        item = VocabularyItem(
            learner_id=learner_id,
            word=word.lower().strip(),
            phonetic=phonetic,
            level=level,
            meanings={"meanings": meanings} if meanings else None,
            collocations={"collocations": collocations} if collocations else None,
            examples={"examples": examples} if examples else None,
            source_ref=source_ref,
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def get_word(self, learner_id: uuid.UUID, word: str) -> VocabularyItem | None:
        result = await self.db.execute(
            select(VocabularyItem).where(
                and_(VocabularyItem.learner_id == learner_id, VocabularyItem.word == word.lower().strip())
            )
        )
        return result.scalar_one_or_none()

    async def get_due_reviews(self, learner_id: uuid.UUID, limit: int = 20) -> list[VocabularyItem]:
        now = datetime.now(timezone.utc).isoformat()
        result = await self.db.execute(
            select(VocabularyItem)
            .where(
                and_(
                    VocabularyItem.learner_id == learner_id,
                    VocabularyItem.next_review_at <= now,
                    VocabularyItem.status != "mastered",
                )
            )
            .order_by(VocabularyItem.next_review_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_confidence(
        self,
        item_id: uuid.UUID,
        correct: bool,
        response_time_ms: int | None = None,
    ) -> VocabularyItem:
        result = await self.db.execute(select(VocabularyItem).where(VocabularyItem.id == item_id))
        item = result.scalar_one()
        now = datetime.now(timezone.utc).isoformat()

        item.review_count += 1
        item.last_reviewed_at = now

        if correct:
            item.confidence = min(1.0, item.confidence + 0.1)
            if item.confidence >= 0.9:
                item.status = "mastered"
            else:
                item.status = "learning"
        else:
            item.confidence = max(0.0, item.confidence - 0.15)
            item.status = "learning"

        # Schedule next review using simplified SM-2
        days = self._calculate_interval(item.review_count, correct)
        from datetime import timedelta
        next_review = datetime.now(timezone.utc) + timedelta(days=days)
        item.next_review_at = next_review.isoformat()

        await self.db.commit()
        await self.db.refresh(item)
        return item

    def _calculate_interval(self, review_count: int, correct: bool) -> int:
        if not correct:
            return 1
        intervals = [1, 2, 4, 7, 15, 30]
        idx = min(review_count, len(intervals) - 1)
        return intervals[idx]
```

- [ ] **Step 3: Create src/memory/error_store.py**

```python
import uuid
from sqlalchemy import select, and_
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
        description: str,
        severity: str = "low",
        evidence_ref: str | None = None,
    ) -> ErrorPattern:
        # Check if pattern already exists
        existing = await self.db.execute(
            select(ErrorPattern).where(
                and_(
                    ErrorPattern.learner_id == learner_id,
                    ErrorPattern.skill == skill,
                    ErrorPattern.pattern == pattern,
                )
            )
        )
        error = existing.scalar_one_or_none()

        if error:
            error.frequency += 1
            if error.frequency >= 5:
                error.severity = "medium"
            if error.frequency >= 10:
                error.severity = "high"
            await self.db.commit()
            await self.db.refresh(error)
            return error

        error = ErrorPattern(
            learner_id=learner_id,
            skill=skill,
            pattern=pattern,
            description=description,
            severity=severity,
            evidence_refs={"refs": [evidence_ref]} if evidence_ref else None,
        )
        self.db.add(error)
        await self.db.commit()
        await self.db.refresh(error)
        return error

    async def get_top_errors(self, learner_id: uuid.UUID, skill: str | None = None, limit: int = 5) -> list[ErrorPattern]:
        query = select(ErrorPattern).where(ErrorPattern.learner_id == learner_id)
        if skill:
            query = query.where(ErrorPattern.skill == skill)
        query = query.order_by(ErrorPattern.frequency.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())
```

- [ ] **Step 4: Create tests/memory/test_vocabulary_store.py**

```python
import pytest
from src.memory.vocabulary_store import VocabularyStore


@pytest.mark.asyncio
async def test_add_word(test_db):
    store = VocabularyStore(test_db)
    item = await store.add_word(
        learner_id=test_learner_id,
        word="sustain",
        phonetic="/səˈsteɪn/",
        level="CET6",
        meanings=["维持", "支撑"],
    )
    assert item.word == "sustain"
    assert item.status == "new"


@pytest.mark.asyncio
async def test_add_duplicate_word(test_db):
    store = VocabularyStore(test_db)
    item1 = await store.add_word(learner_id=test_learner_id, word="hello")
    item2 = await store.add_word(learner_id=test_learner_id, word="hello")
    assert item1.id == item2.id
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/binge/Documents/BinnAgent && python -m pytest tests/memory/ -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/memory/ tests/memory/
git commit -m "feat: add memory stores for profile, vocabulary, and error patterns"
```

---

## Task 6: Tools (Dictionary + SRS + Question Bank)

**Files:**
- Create: `src/tools/__init__.py`, `src/tools/dictionary.py`, `src/tools/srs.py`, `src/tools/question_bank.py`, `src/tools/essay_scoring.py`
- Create: `tests/tools/__init__.py`, `tests/tools/test_srs.py`, `tests/tools/test_dictionary.py`

- [ ] **Step 1: Create src/tools/dictionary.py**

```python
from dataclasses import dataclass, field


@dataclass
class DictionaryLookupRequest:
    word: str
    learner_level: str = "CET4"
    context_sentence: str | None = None


@dataclass
class DictionaryLookupResponse:
    word: str
    phonetic: str = ""
    meanings: list[str] = field(default_factory=list)
    contextual_meaning: str = ""
    collocations: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    confusing_words: list[str] = field(default_factory=list)
    cet_relevance: str = "medium"
    provider: str = "local"


# Mock local dictionary data for MVP
LOCAL_DICT: dict[str, dict] = {
    "sustain": {
        "phonetic": "/səˈsteɪn/",
        "meanings": ["维持", "支撑", "遭受", "忍受"],
        "collocations": ["sustain growth", "sustain an injury", "sustainable development"],
        "examples": [
            "The policy is hard to sustain.",
            "They sustained heavy losses in the battle.",
        ],
        "confusing_words": ["maintain", "retain", "sustain"],
    },
    "abandon": {
        "phonetic": "/əˈbændən/",
        "meanings": ["放弃", "抛弃", "遗弃"],
        "collocations": ["abandon hope", "abandon a plan", "abandoned building"],
        "examples": [
            "They had to abandon the project due to lack of funding.",
            "Don't abandon your dreams just because of setbacks.",
        ],
        "confusing_words": ["desert", "discard", "resign"],
    },
}


class DictionaryTool:
    async def lookup(self, request: DictionaryLookupRequest) -> DictionaryLookupResponse:
        word = request.word.lower().strip()
        data = LOCAL_DICT.get(word, {})

        return DictionaryLookupResponse(
            word=word,
            phonetic=data.get("phonetic", ""),
            meanings=data.get("meanings", []),
            collocations=data.get("collocations", []),
            examples=data.get("examples", []),
            confusing_words=data.get("confusing_words", []),
            cet_relevance="high" if request.learner_level in ("CET4", "CET6") else "medium",
        )


dictionary = DictionaryTool()
```

- [ ] **Step 2: Create src/tools/srs.py**

```python
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class SRSCard:
    item_id: str
    item_type: str
    review_count: int
    confidence: float
    last_result: str | None = None


class SRSScheduler:
    def schedule_next(self, card: SRSCard, response_time_ms: int | None = None) -> dict:
        now = datetime.now(timezone.utc)
        review_count = card.review_count + 1

        if card.last_result == "correct":
            days = self._correct_interval(review_count)
            new_confidence = min(1.0, card.confidence + 0.1)
        else:
            days = 1
            new_confidence = max(0.0, card.confidence - 0.15)

        next_review = now + timedelta(days=days)
        return {
            "next_review_at": next_review.isoformat(),
            "interval_days": days,
            "new_confidence": new_confidence,
            "review_count": review_count,
            "recommended_drill": self._recommend_drill(new_confidence, card.item_type),
        }

    def _correct_interval(self, review_count: int) -> int:
        intervals = [1, 2, 4, 7, 15, 30]
        idx = min(review_count - 1, len(intervals) - 1)
        return intervals[max(0, idx)]

    def _recommend_drill(self, confidence: float, item_type: str) -> str:
        if confidence < 0.3:
            return "context_fill_blank"
        elif confidence < 0.6:
            return "sentence_translation"
        else:
            return "speed_recall"


srs_scheduler = SRSScheduler()
```

- [ ] **Step 3: Create src/tools/question_bank.py**

```python
from dataclasses import dataclass, field


@dataclass
class Question:
    question_id: str
    exam_type: str
    section: str
    question_type: str
    difficulty: str
    stem: str
    options: list[dict[str, str]]
    answer: str
    explanation: str
    tags: list[str] = field(default_factory=list)
    estimated_time_seconds: int = 120


# Mock CET6 reading questions for MVP
MOCK_QUESTIONS: list[Question] = [
    Question(
        question_id="cet6_read_001",
        exam_type="CET6",
        section="reading",
        question_type="reading_comprehension",
        difficulty="medium",
        stem="""The concept of sustainable development has gained significant traction in recent years.
However, implementing it in practice remains challenging. Many companies claim to be sustainable
while continuing harmful practices. The key issue is that true sustainability requires a fundamental
shift in how we produce and consume goods.""",
        options=[
            {"id": "A", "text": "Sustainable development is widely accepted and easy to implement."},
            {"id": "B", "text": "Most companies are genuinely committed to sustainability."},
            {"id": "C", "text": "True sustainability demands changes in production and consumption patterns."},
            {"id": "D", "text": "The concept of sustainable development is overrated."},
        ],
        answer="C",
        explanation="The passage states 'true sustainability requires a fundamental shift in how we produce and consume goods', which directly supports option C. Options A and B contradict the passage, and D is not supported.",
        tags=["transition_logic", "main_idea"],
        estimated_time_seconds=180,
    ),
    Question(
        question_id="cet6_read_002",
        exam_type="CET6",
        section="reading",
        question_type="reading_comprehension",
        difficulty="hard",
        stem="""Urban green spaces have been shown to reduce stress and improve mental health.
Yet, the distribution of these spaces is often unequal. Wealthier neighborhoods tend to have
more parks and trees, while lower-income areas suffer from a lack of greenery. This disparity
exacerbates existing health inequalities between different socioeconomic groups.""",
        options=[
            {"id": "A", "text": "Green spaces benefit everyone equally regardless of location."},
            {"id": "B", "text": "Wealthy people care more about environmental issues."},
            {"id": "C", "text": "Unequal distribution of green spaces widens health gaps."},
            {"id": "D", "text": "Urban planning should focus exclusively on green spaces."},
        ],
        answer="C",
        explanation="The passage explicitly states that the unequal distribution 'exacerbates existing health inequalities', which matches C. A is wrong because distribution is unequal. B and D are not mentioned.",
        tags=["detail", "inference"],
        estimated_time_seconds=180,
    ),
]


class QuestionBank:
    def __init__(self):
        self._questions = {q.question_id: q for q in MOCK_QUESTIONS}

    def get_question(self, exam_type: str = "CET6", section: str = "reading", difficulty: str | None = None) -> Question | None:
        for q in MOCK_QUESTIONS:
            if q.exam_type == exam_type and q.section == section:
                if difficulty is None or q.difficulty == difficulty:
                    return q
        return None

    def get_questions(self, exam_type: str = "CET6", section: str = "reading", limit: int = 5) -> list[Question]:
        return [q for q in MOCK_QUESTIONS if q.exam_type == exam_type and q.section == section][:limit]


question_bank = QuestionBank()
```

- [ ] **Step 4: Create src/tools/essay_scoring.py**

```python
from dataclasses import dataclass, field


@dataclass
class EssayScoringResult:
    score: int
    max_score: int
    strengths: list[str] = field(default_factory=list)
    key_issues: list[str] = field(default_factory=list)
    sentence_feedback: list[dict] = field(default_factory=list)
    error_patterns: list[str] = field(default_factory=list)


class EssayScoringTool:
    async def score(self, essay_text: str, prompt: str = "") -> EssayScoringResult:
        # MVP: simple heuristic scoring
        word_count = len(essay_text.split())
        score = min(15, max(5, word_count // 20))

        issues = []
        if word_count < 100:
            issues.append("文章过短，建议至少写120词")
        if not any(c in essay_text for c in ".!?"):
            issues.append("缺少句号或感叹号，注意句子完整性")

        return EssayScoringResult(
            score=score,
            max_score=15,
            key_issues=issues,
        )


essay_scorer = EssayScoringTool()
```

- [ ] **Step 5: Create tests/tools/test_srs.py**

```python
import pytest
from src.tools.srs import SRSScheduler, SRSCard


def test_srs_correct_answer():
    scheduler = SRSScheduler()
    card = SRSCard(item_id="1", item_type="vocabulary", review_count=0, confidence=0.5)
    result = scheduler.schedule_next(card, response_time_ms=3000)
    assert result["interval_days"] == 1
    assert result["new_confidence"] == 0.6


def test_srs_wrong_answer():
    scheduler = SRSScheduler()
    card = SRSCard(item_id="1", item_type="vocabulary", review_count=3, confidence=0.7)
    result = scheduler.schedule_next(card, response_time_ms=5000)
    assert result["interval_days"] == 1
    assert result["new_confidence"] == 0.55
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/binge/Documents/BinnAgent && python -m pytest tests/tools/ -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/tools/ tests/tools/
git commit -m "feat: add learning tools (dictionary, SRS, question bank, essay scoring)"
```

---

## Task 7: LangGraph Runtime (State + Main Graph)

**Files:**
- Create: `src/graph/__init__.py`, `src/graph/state.py`, `src/graph/main_graph.py`
- Create: `src/graph/nodes/__init__.py`, `src/graph/nodes/load_profile.py`, `src/graph/nodes/detect_intent.py`, `src/graph/nodes/select_goal.py`, `src/graph/nodes/route_skill.py`, `src/graph/nodes/run_task.py`, `src/graph/nodes/generate_feedback.py`, `src/graph/nodes/update_memory.py`, `src/graph/nodes/schedule_review.py`, `src/graph/nodes/summarize.py`
- Create: `tests/graph/__init__.py`, `tests/graph/test_main_graph.py`

- [ ] **Step 1: Create src/graph/state.py**

```python
from typing import Any, TypedDict, Annotated
from langgraph.graph.message import add_messages


class LearningState(TypedDict, total=False):
    user_id: str
    thread_id: str
    session_id: str
    target_exam: str | None
    exam_date: str | None
    current_level: str | None
    daily_time_budget: int
    active_skill: str | None
    today_goal: str | None
    messages: Annotated[list, add_messages]
    input_materials: list[dict[str, Any]]
    learner_answer: dict[str, Any] | None
    agent_feedback: dict[str, Any] | None
    memory_candidates: list[dict[str, Any]]
    review_items: list[dict[str, Any]]
    next_tasks: list[dict[str, Any]]
    emotion_signal: dict[str, Any] | None
    model_policy: dict[str, Any] | None
```

- [ ] **Step 2: Create src/graph/nodes/load_profile.py**

```python
from src.graph.state import LearningState


async def load_profile(state: LearningState) -> dict:
    """Load learner profile, review queue, and recent error patterns."""
    return {
        "target_exam": state.get("target_exam", "CET6"),
        "exam_date": state.get("exam_date"),
        "current_level": state.get("current_level", "intermediate"),
        "daily_time_budget": state.get("daily_time_budget", 30),
    }
```

- [ ] **Step 3: Create src/graph/nodes/detect_intent.py**

```python
from src.graph.state import LearningState
from src.providers.router import router as model_router
from src.providers.base import ChatRequest


async def detect_intent(state: LearningState) -> dict:
    """Detect user intent from the latest message."""
    messages = state.get("messages", [])
    if not messages:
        return {"active_skill": "reading"}

    last_message = messages[-1]
    user_input = last_message.get("content", "") if isinstance(last_message, dict) else str(last_message)

    # Simple keyword-based intent detection for MVP
    user_lower = user_input.lower()
    if any(kw in user_lower for kw in ["单词", "背词", "词汇", "vocabulary"]):
        skill = "vocabulary"
    elif any(kw in user_lower for kw in ["阅读", "reading", "文章"]):
        skill = "reading"
    elif any(kw in user_lower for kw in ["写作", "作文", "writing", "essay"]):
        skill = "writing"
    elif any(kw in user_lower for kw in ["复习", "review"]):
        skill = "vocabulary"
    else:
        skill = "reading"  # default

    return {"active_skill": skill}
```

- [ ] **Step 4: Create src/graph/nodes/select_goal.py**

```python
from src.graph.state import LearningState


async def select_learning_goal(state: LearningState) -> dict:
    """Select today's learning goal based on profile and recent performance."""
    skill = state.get("active_skill", "reading")
    time_budget = state.get("daily_time_budget", 30)

    goals = {
        "reading": {
            "today_goal": "练习六级阅读中的转折定位题",
            "estimated_minutes": min(20, time_budget),
            "success_criteria": "完成 1 篇短阅读并解释 2 道错题",
        },
        "writing": {
            "today_goal": "完成一篇作文练习并获得反馈",
            "estimated_minutes": min(25, time_budget),
            "success_criteria": "写完初稿并根据反馈修改",
        },
        "vocabulary": {
            "today_goal": "复习到期词汇并学习新词",
            "estimated_minutes": min(15, time_budget),
            "success_criteria": "完成复习并掌握 3 个新词",
        },
    }

    goal = goals.get(skill, goals["reading"])
    return goal
```

- [ ] **Step 5: Create src/graph/nodes/route_skill.py**

```python
from src.graph.state import LearningState


async def route_skill_agent(state: LearningState) -> dict:
    """Route to the appropriate skill agent based on active_skill."""
    skill = state.get("active_skill", "reading")
    return {"active_skill": skill}
```

- [ ] **Step 6: Create src/graph/nodes/run_task.py**

```python
from src.graph.state import LearningState
from src.tools.question_bank import question_bank


async def run_learning_task(state: LearningState) -> dict:
    """Run the learning task for the active skill."""
    skill = state.get("active_skill", "reading")
    target_exam = state.get("target_exam", "CET6")

    if skill == "reading":
        question = question_bank.get_question(exam_type=target_exam, section="reading")
        if question:
            return {
                "input_materials": [
                    {
                        "question_id": question.question_id,
                        "stem": question.stem,
                        "options": question.options,
                        "estimated_time": question.estimated_time_seconds,
                    }
                ]
            }

    return {"input_materials": [{"type": "general_task", "skill": skill}]}
```

- [ ] **Step 7: Create src/graph/nodes/generate_feedback.py**

```python
from src.graph.state import LearningState


async def generate_feedback(state: LearningState) -> dict:
    """Generate structured feedback based on learner answer."""
    answer = state.get("learner_answer", {})
    materials = state.get("input_materials", [])

    if not answer:
        return {"agent_feedback": {"summary": "请先完成练习", "key_issues": [], "drill": None}}

    # For reading: check answer
    selected = answer.get("selected_option", "")
    # Feedback would normally come from LLM, here using mock
    feedback = {
        "summary": "你需要关注转折信号词后的内容",
        "key_issues": [
            {
                "type": "reading_logic",
                "evidence": "你选择了错误的选项，请注意 however/but/yet 后的观点变化。",
                "fix": "看到转折词后优先标记作者观点变化。",
            }
        ],
        "drill": {
            "type": "transition_signal_practice",
            "minutes": 5,
        },
    }
    return {"agent_feedback": feedback}
```

- [ ] **Step 8: Create src/graph/nodes/update_memory.py**

```python
from src.graph.state import LearningState


async def update_memory(state: LearningState) -> dict:
    """Extract memory candidates from the session."""
    candidates = []
    answer = state.get("learner_answer", {})
    feedback = state.get("agent_feedback", {})

    if answer and not answer.get("is_correct"):
        # Record error pattern
        candidates.append({
            "type": "error_pattern",
            "skill": state.get("active_skill", "reading"),
            "pattern": "transition_logic",
            "description": "忽略转折信号词后的内容",
        })

    # Record vocabulary from materials
    materials = state.get("input_materials", [])
    for mat in materials:
        if "new_words" in mat:
            for word in mat["new_words"]:
                candidates.append({"type": "vocabulary", "word": word})

    return {"memory_candidates": candidates}
```

- [ ] **Step 9: Create src/graph/nodes/schedule_review.py**

```python
from src.graph.state import LearningState


async def schedule_review(state: LearningState) -> dict:
    """Schedule review items based on memory candidates."""
    candidates = state.get("memory_candidates", [])
    review_items = []

    for candidate in candidates:
        if candidate.get("type") == "vocabulary":
            review_items.append({
                "item_type": "vocabulary",
                "word": candidate.get("word"),
                "scheduled_at": "tomorrow",
            })
        elif candidate.get("type") == "error_pattern":
            review_items.append({
                "item_type": "error_pattern",
                "pattern": candidate.get("pattern"),
                "scheduled_at": "tomorrow",
            })

    return {"review_items": review_items}
```

- [ ] **Step 10: Create src/graph/nodes/summarize.py**

```python
from src.graph.state import LearningState


async def summarize_session(state: LearningState) -> dict:
    """Generate session summary."""
    goal = state.get("today_goal", "今日学习")
    feedback = state.get("agent_feedback", {})
    review_items = state.get("review_items", [])

    summary = {
        "completed": goal,
        "key_takeaway": feedback.get("summary", ""),
        "to_review": len(review_items),
        "next_focus": "继续练习薄弱环节",
    }
    return {"messages": [{"role": "assistant", "content": str(summary)}]}
```

- [ ] **Step 11: Create src/graph/main_graph.py**

```python
from langgraph.graph import StateGraph, END

from src.graph.state import LearningState
from src.graph.nodes.load_profile import load_profile
from src.graph.nodes.detect_intent import detect_intent
from src.graph.nodes.select_goal import select_learning_goal
from src.graph.nodes.route_skill import route_skill_agent
from src.graph.nodes.run_task import run_learning_task
from src.graph.nodes.generate_feedback import generate_feedback
from src.graph.nodes.update_memory import update_memory
from src.graph.nodes.schedule_review import schedule_review
from src.graph.nodes.summarize import summarize_session


def build_graph() -> StateGraph:
    graph = StateGraph(LearningState)

    # Add nodes
    graph.add_node("load_profile", load_profile)
    graph.add_node("detect_intent", detect_intent)
    graph.add_node("select_learning_goal", select_learning_goal)
    graph.add_node("route_skill_agent", route_skill_agent)
    graph.add_node("run_learning_task", run_learning_task)
    graph.add_node("generate_feedback", generate_feedback)
    graph.add_node("update_memory", update_memory)
    graph.add_node("schedule_review", schedule_review)
    graph.add_node("summarize_session", summarize_session)

    # Set edges
    graph.set_entry_point("load_profile")
    graph.add_edge("load_profile", "detect_intent")
    graph.add_edge("detect_intent", "select_learning_goal")
    graph.add_edge("select_learning_goal", "route_skill_agent")
    graph.add_edge("route_skill_agent", "run_learning_task")
    graph.add_edge("run_learning_task", "generate_feedback")
    graph.add_edge("generate_feedback", "update_memory")
    graph.add_edge("update_memory", "schedule_review")
    graph.add_edge("schedule_review", "summarize_session")
    graph.add_edge("summarize_session", END)

    return graph.compile()


daily_lesson_graph = build_graph()
```

- [ ] **Step 12: Create tests/graph/test_main_graph.py**

```python
import pytest
from src.graph.main_graph import daily_lesson_graph


@pytest.mark.asyncio
async def test_daily_lesson_runs():
    initial_state = {
        "user_id": "test-user",
        "thread_id": "test-thread",
        "session_id": "test-session",
        "target_exam": "CET6",
        "daily_time_budget": 30,
        "messages": [{"role": "user", "content": "我想练习阅读"}],
    }
    result = await daily_lesson_graph.ainvoke(initial_state)
    assert "active_skill" in result
    assert result["active_skill"] == "reading"
    assert "today_goal" in result
    assert "agent_feedback" in result
```

- [ ] **Step 13: Run tests**

Run: `cd /Users/binge/Documents/BinnAgent && python -m pytest tests/graph/ -v`
Expected: PASS

- [ ] **Step 14: Commit**

```bash
git add src/graph/ tests/graph/
git commit -m "feat: add LangGraph main graph with learning session nodes"
```

---

## Task 8: Session API Endpoint

**Files:**
- Create: `src/api/sessions.py`
- Create: `tests/api/test_sessions.py`
- Modify: `src/main.py` (register sessions router)

- [ ] **Step 1: Create src/api/sessions.py**

```python
import uuid
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.models.session import LearningSession
from src.graph.main_graph import daily_lesson_graph

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class StartSessionRequest(BaseModel):
    learner_id: str
    user_message: str = "开始今日课程"


class SessionResponse(BaseModel):
    id: uuid.UUID
    status: str
    active_skill: str | None = None
    today_goal: str | None = None

    model_config = {"from_attributes": True}


@router.post("/start", response_model=SessionResponse)
async def start_session(req: StartSessionRequest, db: AsyncSession = Depends(get_db_session)):
    learner_id = uuid.UUID(req.learner_id)

    # Create session record
    session = LearningSession(
        learner_id=learner_id,
        session_type="daily_lesson",
        status="active",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # Run the graph
    initial_state = {
        "user_id": str(learner_id),
        "thread_id": str(uuid.uuid4()),
        "session_id": str(session.id),
        "target_exam": "CET6",
        "daily_time_budget": 30,
        "messages": [{"role": "user", "content": req.user_message}],
    }

    result = await daily_lesson_graph.ainvoke(initial_state)

    # Update session with results
    session.active_skill = result.get("active_skill")
    session.today_goal = result.get("today_goal")
    session.status = "completed"
    await db.commit()
    await db.refresh(session)

    return SessionResponse(
        id=session.id,
        status=session.status,
        active_skill=session.active_skill,
        today_goal=session.today_goal,
    )
```

- [ ] **Step 2: Update src/main.py to register sessions router**

Add:
```python
from src.api.sessions import router as sessions_router
app.include_router(sessions_router)
```

- [ ] **Step 3: Create tests/api/test_sessions.py**

```python
import pytest


@pytest.mark.asyncio
async def test_start_session(client):
    # Create learner first
    resp = await client.post("/api/learners", json={"nickname": "Test"})
    learner_id = resp.json()["id"]

    # Start session
    resp = await client.post(
        "/api/sessions/start",
        json={"learner_id": learner_id, "user_message": "开始阅读练习"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert "active_skill" in data
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/binge/Documents/BinnAgent && python -m pytest tests/api/test_sessions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/sessions.py tests/api/test_sessions.py
git commit -m "feat: add session API endpoint with LangGraph integration"
```

---

## Task 9: Vocabulary API Endpoint

**Files:**
- Create: `src/api/vocabulary.py`
- Create: `tests/api/test_vocabulary.py`
- Modify: `src/main.py` (register vocabulary router)

- [ ] **Step 1: Create src/api/vocabulary.py**

```python
import uuid
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.memory.vocabulary_store import VocabularyStore

router = APIRouter(prefix="/api/learners/{learner_id}/vocabulary", tags=["vocabulary"])


class AddWordRequest(BaseModel):
    word: str
    phonetic: str | None = None
    level: str | None = None
    meanings: list[str] | None = None


class ReviewWordRequest(BaseModel):
    word_id: str
    correct: bool
    response_time_ms: int | None = None


class WordResponse(BaseModel):
    id: uuid.UUID
    word: str
    phonetic: str | None = None
    status: str
    confidence: float
    next_review_at: str | None = None


@router.post("/add", response_model=WordResponse)
async def add_word(
    learner_id: uuid.UUID,
    req: AddWordRequest,
    db: AsyncSession = Depends(get_db_session),
):
    store = VocabularyStore(db)
    item = await store.add_word(
        learner_id=learner_id,
        word=req.word,
        phonetic=req.phonetic,
        level=req.level,
        meanings=req.meanings,
    )
    return WordResponse(
        id=item.id,
        word=item.word,
        phonetic=item.phonetic,
        status=item.status,
        confidence=item.confidence,
        next_review_at=item.next_review_at,
    )


@router.get("/due", response_model=list[WordResponse])
async def get_due_reviews(
    learner_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
):
    store = VocabularyStore(db)
    items = await store.get_due_reviews(learner_id)
    return [
        WordResponse(
            id=item.id,
            word=item.word,
            phonetic=item.phonetic,
            status=item.status,
            confidence=item.confidence,
            next_review_at=item.next_review_at,
        )
        for item in items
    ]


@router.post("/review", response_model=WordResponse)
async def review_word(
    learner_id: uuid.UUID,
    req: ReviewWordRequest,
    db: AsyncSession = Depends(get_db_session),
):
    store = VocabularyStore(db)
    item = await store.update_confidence(
        item_id=uuid.UUID(req.word_id),
        correct=req.correct,
        response_time_ms=req.response_time_ms,
    )
    return WordResponse(
        id=item.id,
        word=item.word,
        phonetic=item.phonetic,
        status=item.status,
        confidence=item.confidence,
        next_review_at=item.next_review_at,
    )
```

- [ ] **Step 2: Update src/main.py**

Add:
```python
from src.api.vocabulary import router as vocabulary_router
app.include_router(vocabulary_router)
```

- [ ] **Step 3: Create tests/api/test_vocabulary.py**

```python
import pytest


@pytest.mark.asyncio
async def test_add_and_review_word(client):
    # Create learner
    resp = await client.post("/api/learners", json={"nickname": "Test"})
    learner_id = resp.json()["id"]

    # Add word
    resp = await client.post(
        f"/api/learners/{learner_id}/vocabulary/add",
        json={"word": "sustain", "phonetic": "/səˈsteɪn/", "meanings": ["维持"]},
    )
    assert resp.status_code == 200
    word_id = resp.json()["id"]

    # Review word (correct)
    resp = await client.post(
        f"/api/learners/{learner_id}/vocabulary/review",
        json={"word_id": word_id, "correct": True, "response_time_ms": 3000},
    )
    assert resp.status_code == 200
    assert resp.json()["confidence"] > 0
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/binge/Documents/BinnAgent && python -m pytest tests/api/test_vocabulary.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/vocabulary.py tests/api/test_vocabulary.py
git commit -m "feat: add vocabulary API with add, due review, and review endpoints"
```

---

## Task 10: Integration Test (Full Session Flow)

**Files:**
- Create: `tests/integration/__init__.py`, `tests/integration/test_full_session.py`

- [ ] **Step 1: Create tests/integration/test_full_session.py**

```python
import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_full_learning_session():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create learner
        resp = await client.post("/api/learners", json={"nickname": "Integration Test User"})
        assert resp.status_code == 200
        learner_id = resp.json()["id"]

        # 2. Set profile
        resp = await client.post(
            f"/api/learners/{learner_id}/profile",
            json={"target_exam": "CET6", "daily_time_budget_minutes": 30},
        )
        assert resp.status_code == 200

        # 3. Start learning session
        resp = await client.post(
            "/api/sessions/start",
            json={"learner_id": learner_id, "user_message": "我想练习六级阅读"},
        )
        assert resp.status_code == 200
        session = resp.json()
        assert session["status"] == "completed"
        assert session["active_skill"] == "reading"

        # 4. Add vocabulary
        resp = await client.post(
            f"/api/learners/{learner_id}/vocabulary/add",
            json={"word": "sustain", "meanings": ["维持"]},
        )
        assert resp.status_code == 200

        # 5. Check due reviews
        resp = await client.get(f"/api/learners/{learner_id}/vocabulary/due")
        assert resp.status_code == 200

        # 6. Health check
        resp = await client.get("/health")
        assert resp.status_code == 200
```

- [ ] **Step 2: Run integration test**

Run: `cd /Users/binge/Documents/BinnAgent && python -m pytest tests/integration/ -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/
git commit -m "test: add integration test for full learning session flow"
```

---

## Task 11: Final Verification & Documentation

- [ ] **Step 1: Run all tests**

Run: `cd /Users/binge/Documents/BinnAgent && python -m pytest tests/ -v --tb=short`

- [ ] **Step 2: Update README.md with setup instructions**

Add sections for:
- Prerequisites (Python 3.11+, PostgreSQL, Ollama)
- Installation steps
- Running the server
- API documentation (endpoints)

- [ ] **Step 3: Final commit**

```bash
git add README.md
git commit -m "docs: update README with setup and usage instructions"
```

---

## Parallel Execution Opportunities

Tasks can be parallelized as follows:

**Wave 1 (Independent):**
- Task 1: Project skeleton
- Task 2: Database models (depends only on Task 1's db.py)
- Task 3: Ollama provider (independent of DB)

**Wave 2 (After Wave 1):**
- Task 4: API endpoints (depends on Task 1, 2)
- Task 5: Memory stores (depends on Task 2)
- Task 6: Tools (independent)

**Wave 3 (After Wave 2):**
- Task 7: LangGraph runtime (depends on Task 3, 6)
- Task 8: Session API (depends on Task 4, 7)
- Task 9: Vocabulary API (depends on Task 4, 5)

**Wave 4 (After Wave 3):**
- Task 10: Integration test (depends on all)
- Task 11: Final verification
