import inspect
import time
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.runtime.episode import EpisodeRuntime
from src.runtime.hashing import stable_json_hash
from src.tools.types import ToolExecutionInput, ToolExecutionResult, ToolSpec

ToolHandler = Callable[[dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]


class ToolRegistry:
    def __init__(self, db: AsyncSession | None = None):
        self.db = db
        self._tools: dict[str, tuple[ToolSpec, ToolHandler]] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        self._tools[spec.name] = (spec, handler)

    def get(self, name: str) -> ToolSpec:
        return self._tools[name][0]

    def list_tools(self) -> list[ToolSpec]:
        return [tool[0] for tool in sorted(self._tools.values(), key=lambda item: item[0].name)]

    async def execute(self, input: ToolExecutionInput) -> ToolExecutionResult:
        if input.tool_name not in self._tools:
            return await self._failed(input, f"Unknown tool {input.tool_name}", None)
        spec, handler = self._tools[input.tool_name]
        start = time.perf_counter()
        input_hash = stable_json_hash(input.payload)
        try:
            raw_output = handler(input.payload)
            output = await raw_output if inspect.isawaitable(raw_output) else raw_output
            latency_ms = round((time.perf_counter() - start) * 1000)
            output_hash = stable_json_hash(output)
            result = ToolExecutionResult(
                tool_name=spec.name,
                status="success",
                output=output,
                error=None,
                latency_ms=latency_ms,
                input_hash=input_hash,
                output_hash=output_hash,
            )
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start) * 1000)
            result = ToolExecutionResult(
                tool_name=spec.name,
                status="failed",
                output=None,
                error=str(exc),
                latency_ms=latency_ms,
                input_hash=input_hash,
                output_hash=None,
            )
        await self._record(input, result)
        return result

    async def _failed(
        self,
        input: ToolExecutionInput,
        error: str,
        latency_ms: int | None,
    ) -> ToolExecutionResult:
        result = ToolExecutionResult(
            tool_name=input.tool_name,
            status="failed",
            output=None,
            error=error,
            latency_ms=latency_ms,
            input_hash=stable_json_hash(input.payload),
            output_hash=None,
        )
        await self._record(input, result)
        return result

    async def _record(self, input: ToolExecutionInput, result: ToolExecutionResult) -> None:
        if self.db is None or input.episode_id is None:
            return
        await EpisodeRuntime(self.db).record_tool_call(
            episode_id=input.episode_id,
            tool_name=result.tool_name,
            input_hash=result.input_hash,
            output_hash=result.output_hash,
            latency_ms=result.latency_ms,
            status=result.status,
            error=result.error,
            metadata=input.metadata,
        )


def build_default_tool_registry(db: AsyncSession | None = None) -> ToolRegistry:
    registry = ToolRegistry(db=db)
    for name, description in [
        ("rag.retrieve", "Retrieve textbook chunks for a learning task."),
        ("exercise.grade", "Grade a learner exercise answer."),
        ("memory.retrieve", "Retrieve learner memory context."),
        ("memory.write", "Write auditable learner memory evidence."),
        ("mastery.update", "Update learner mastery from an attempt signal."),
        ("review.schedule", "Schedule spaced review for a learning target."),
        ("recommendation.plan", "Build a daily learning recommendation plan."),
        ("verification.verify_episode", "Verify an AgentEpisode against required checks."),
    ]:
        registry.register(
            ToolSpec(
                name=name,
                description=description,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                risk_level="low",
            ),
            _default_handler(name),
        )
    return registry


def _default_handler(name: str) -> ToolHandler:
    def handler(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "tool_name": name,
            "status": "accepted",
            "payload": payload,
        }

    return handler
