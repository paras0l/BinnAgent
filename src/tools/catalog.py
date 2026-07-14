import asyncio
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from jsonschema import ValidationError, validate
from sqlalchemy.ext.asyncio import AsyncSession

from src.runtime.episode import EpisodeRuntime
from src.runtime.hashing import stable_json_hash
from src.tools.types import (
    ToolCatalogView,
    ToolExecutionContext,
    ToolExecutionInput,
    ToolExecutionResult,
    ToolResolutionItem,
    ToolResolutionView,
    ToolSpec,
)

ToolHandler = Callable[
    [dict[str, Any], ToolExecutionContext],
    dict[str, Any] | Awaitable[dict[str, Any]],
]


@dataclass(frozen=True)
class ToolBinding:
    spec: ToolSpec
    handler: ToolHandler


class ToolCatalogManager:
    """Application-level catalog with atomic refresh and execution policy enforcement."""

    def __init__(self) -> None:
        self._bindings: dict[str, ToolBinding] = {}
        self._generation = 0
        self._revision = "uninitialized"
        self._created_at = _now()
        self._refreshed_at = self._created_at
        self._refresh_count = 0
        self._failed_refresh_count = 0
        self._last_refresh_error: str | None = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        if not self._bindings:
            await self.refresh()

    async def refresh(self) -> ToolCatalogView:
        async with self._lock:
            try:
                candidates = _discover_internal_tools()
                _validate_candidates(candidates)
                previous_enabled = {
                    name: binding.spec.enabled for name, binding in self._bindings.items()
                }
                now = _now()
                normalized: dict[str, ToolBinding] = {}
                for candidate in candidates:
                    spec = candidate.spec.model_copy(
                        update={
                            "enabled": previous_enabled.get(candidate.spec.name, True),
                            "registered_at": candidate.spec.registered_at or now,
                            "last_health_check_at": now,
                        }
                    )
                    spec = spec.model_copy(update={"spec_hash": _spec_hash(spec)})
                    normalized[spec.name] = ToolBinding(spec=spec, handler=candidate.handler)
                self._bindings = normalized
                self._generation += 1
                self._revision = stable_json_hash(
                    {name: binding.spec.spec_hash for name, binding in sorted(normalized.items())}
                )[:16]
                self._refreshed_at = now
                self._refresh_count += 1
                self._last_refresh_error = None
            except Exception as exc:
                self._failed_refresh_count += 1
                self._last_refresh_error = str(exc)
                raise
        return self.view()

    def view(self) -> ToolCatalogView:
        tools = [binding.spec for _, binding in sorted(self._bindings.items())]
        counts = {status: 0 for status in ("healthy", "degraded", "unavailable", "disabled")}
        for tool in tools:
            status = "disabled" if not tool.enabled else tool.health_status
            counts[status] += 1
        return ToolCatalogView(
            revision=self._revision,
            generation=self._generation,
            created_at=self._created_at,
            refreshed_at=self._refreshed_at,
            tool_count=len(tools),
            enabled_count=sum(1 for tool in tools if tool.enabled),
            healthy_count=counts["healthy"],
            degraded_count=counts["degraded"],
            unavailable_count=counts["unavailable"],
            disabled_count=counts["disabled"],
            refresh_count=self._refresh_count,
            failed_refresh_count=self._failed_refresh_count,
            last_refresh_error=self._last_refresh_error,
            tools=tools,
        )

    def list_tools(self) -> list[ToolSpec]:
        return self.view().tools

    def set_enabled(self, name: str, enabled: bool) -> ToolSpec:
        binding = self._bindings.get(name)
        if binding is None:
            raise KeyError(name)
        health_status = binding.spec.health_status
        if not enabled:
            health_status = "disabled"
        elif health_status == "disabled":
            health_status = "healthy"
        spec = binding.spec.model_copy(update={"enabled": enabled, "health_status": health_status})
        self._bindings = {**self._bindings, name: ToolBinding(spec=spec, handler=binding.handler)}
        return spec

    def resolve(self, allowed_tools: list[str]) -> ToolResolutionView:
        allowed = set(allowed_tools)
        items: list[ToolResolutionItem] = []
        for tool in self.list_tools():
            if tool.name not in allowed:
                decision, reason = False, "not_in_task_allowlist"
            elif not tool.enabled:
                decision, reason = False, "disabled"
            elif tool.health_status not in {"healthy", "degraded"}:
                decision, reason = False, f"health_{tool.health_status}"
            else:
                decision, reason = True, "allowed"
            items.append(
                ToolResolutionItem(
                    name=tool.name,
                    version=tool.version,
                    allowed=decision,
                    reason=reason,
                )
            )
        return ToolResolutionView(catalog_revision=self._revision, items=items)

    async def execute(
        self,
        input: ToolExecutionInput,
        *,
        db: AsyncSession | None = None,
        learner_id=None,
    ) -> ToolExecutionResult:
        await self.initialize()
        binding = self._bindings.get(input.tool_name)
        if binding is None:
            return await self._failure(input, "not_found", f"Unknown tool {input.tool_name}", db)
        spec = binding.spec
        if input.catalog_revision and input.catalog_revision != self._revision:
            return await self._failure(input, "catalog_revision_mismatch", "Catalog revision changed", db, spec)
        if input.allowed_tools is not None and input.tool_name not in input.allowed_tools:
            return await self._failure(input, "not_allowed", "Tool is not in task allowlist", db, spec)
        if not spec.enabled:
            return await self._failure(input, "disabled", "Tool is disabled", db, spec)
        if spec.health_status not in {"healthy", "degraded"}:
            return await self._failure(input, "provider_unavailable", "Tool provider is unavailable", db, spec)
        try:
            validate(instance=input.payload, schema=spec.input_schema)
        except ValidationError as exc:
            return await self._failure(input, "invalid_input", exc.message, db, spec)

        started = asyncio.get_running_loop().time()
        try:
            raw = binding.handler(
                input.payload,
                ToolExecutionContext(db=db, learner_id=learner_id),
            )
            output = await asyncio.wait_for(
                raw if inspect.isawaitable(raw) else _completed(raw),
                timeout=spec.timeout_ms / 1000,
            )
            validate(instance=output, schema=spec.output_schema)
            result = ToolExecutionResult(
                tool_name=spec.name,
                tool_version=spec.version,
                catalog_revision=self._revision,
                status="success",
                output=output,
                latency_ms=round((asyncio.get_running_loop().time() - started) * 1000),
                input_hash=stable_json_hash(input.payload),
                output_hash=stable_json_hash(output),
            )
        except TimeoutError:
            result = _failed_result(input, spec, self._revision, "timeout", "Tool execution timed out")
        except ValidationError as exc:
            result = _failed_result(input, spec, self._revision, "invalid_output", exc.message)
        except Exception as exc:
            result = _failed_result(input, spec, self._revision, "execution_failed", str(exc))
        if result.latency_ms is None:
            result.latency_ms = round((asyncio.get_running_loop().time() - started) * 1000)
        await _record(db, input, result, spec)
        return result

    async def _failure(
        self,
        input: ToolExecutionInput,
        code: str,
        error: str,
        db: AsyncSession | None,
        spec: ToolSpec | None = None,
    ) -> ToolExecutionResult:
        result = _failed_result(input, spec, self._revision, code, error)
        await _record(db, input, result, spec)
        return result


async def _completed(value: dict[str, Any]) -> dict[str, Any]:
    return value


def _failed_result(
    input: ToolExecutionInput,
    spec: ToolSpec | None,
    revision: str,
    code: str,
    error: str,
) -> ToolExecutionResult:
    return ToolExecutionResult(
        tool_name=input.tool_name,
        tool_version=spec.version if spec else None,
        catalog_revision=revision,
        status="failed",
        error=error,
        error_code=code,
        input_hash=stable_json_hash(input.payload),
    )


async def _record(
    db: AsyncSession | None,
    input: ToolExecutionInput,
    result: ToolExecutionResult,
    spec: ToolSpec | None,
) -> None:
    if db is None or input.episode_id is None:
        return
    metadata = {
        **input.metadata,
        "tool_version": result.tool_version,
        "catalog_revision": result.catalog_revision,
        "spec_hash": spec.spec_hash if spec else None,
        "provider_ref": spec.provider_ref if spec else None,
        "error_code": result.error_code,
        "attempt_count": result.attempt_count,
    }
    await EpisodeRuntime(db).record_tool_call(
        episode_id=input.episode_id,
        tool_name=result.tool_name,
        input_hash=result.input_hash,
        output_hash=result.output_hash,
        latency_ms=result.latency_ms,
        status=result.status,
        error=result.error,
        metadata=metadata,
    )


def _discover_internal_tools() -> list[ToolBinding]:
    tools = [
        ("rag.retrieve", "Retrieve textbook chunks for a learning task."),
        ("exercise.grade", "Grade a learner exercise answer."),
        ("memory.retrieve", "Retrieve learner memory context."),
        ("memory.write", "Write auditable learner memory evidence."),
        ("mastery.update", "Update learner mastery from an attempt signal."),
        ("review.schedule", "Schedule spaced review for a learning target."),
        ("recommendation.plan", "Build a daily learning recommendation plan."),
        ("verification.verify_episode", "Verify an AgentEpisode against required checks."),
    ]
    bindings = [
        ToolBinding(
            spec=ToolSpec(
                name=name,
                description=description,
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                risk_level="low",
                source="internal",
                provider_ref="binnagent.core",
                idempotency="safe" if name.endswith("retrieve") else "keyed",
            ),
            handler=_default_handler(name),
        )
        for name, description in tools
    ]
    bindings.extend(_learning_tool_bindings())
    return bindings


def _default_handler(name: str) -> ToolHandler:
    def handler(payload: dict[str, Any], _: ToolExecutionContext) -> dict[str, Any]:
        return {"tool_name": name, "status": "accepted", "payload": payload}

    return handler


def _learning_tool_bindings() -> list[ToolBinding]:
    from src.tools.learning_tools import (
        AnalyzeLearnerResponseInput,
        FindCanDoForItemInput,
        FindCanDoForQueryInput,
        GetLearnerKnowledgeStateInput,
        RecordLearningEvidenceInput,
        analyze_learner_response,
        find_can_do_for_item,
        find_can_do_for_query,
        get_learner_knowledge_state,
        record_learning_evidence,
        tool_input_schema,
    )

    async def item_handler(payload, context):
        return await find_can_do_for_item(
            _require_db(context), FindCanDoForItemInput.model_validate(payload)
        )

    async def query_handler(payload, context):
        return await find_can_do_for_query(
            _require_db(context), FindCanDoForQueryInput.model_validate(payload)
        )

    def analyze_handler(payload, _context):
        return analyze_learner_response(AnalyzeLearnerResponseInput.model_validate(payload))

    async def state_handler(payload, context):
        return await get_learner_knowledge_state(
            _require_db(context),
            _require_learner(context),
            GetLearnerKnowledgeStateInput.model_validate(payload),
        )

    async def record_handler(payload, context):
        return await record_learning_evidence(
            _require_db(context),
            _require_learner(context),
            RecordLearningEvidenceInput.model_validate(payload),
        )

    object_output = {"type": "object", "additionalProperties": True}
    definitions = [
        (
            "find_can_do_for_item",
            "Match an exercise to one primary can-do and evidence-backed atomic knowledge items.",
            FindCanDoForItemInput,
            item_handler,
            "read",
            "safe",
            ["db"],
        ),
        (
            "find_can_do_for_query",
            "Match a learner question to can-do statements and atomic knowledge items.",
            FindCanDoForQueryInput,
            query_handler,
            "read",
            "safe",
            ["db"],
        ),
        (
            "analyze_learner_response",
            "Classify target evidence as success, unsuccessful, no-attempt, or unrelated error.",
            AnalyzeLearnerResponseInput,
            analyze_handler,
            "read",
            "safe",
            [],
        ),
        (
            "get_learner_knowledge_state",
            "Read DKT, IRT, recent evidence, review due state, and common errors for the current learner.",
            GetLearnerKnowledgeStateInput,
            state_handler,
            "read",
            "safe",
            ["db", "learner_id"],
        ),
        (
            "record_learning_evidence",
            "Idempotently record observations and update derived learner state without accepting mastery values.",
            RecordLearningEvidenceInput,
            record_handler,
            "write",
            "keyed",
            ["db", "learner_id"],
        ),
    ]
    return [
        ToolBinding(
            spec=ToolSpec(
                name=name,
                version="1.0.0",
                description=description,
                input_schema=tool_input_schema(input_model),
                output_schema=object_output,
                risk_level=risk,
                source="internal",
                provider_ref="binnagent.learning_tools",
                injected_fields=injected_fields,
                idempotency=idempotency,
                required_scopes=["learner:read"] if risk == "read" else ["learner:write"],
            ),
            handler=handler,
        )
        for name, description, input_model, handler, risk, idempotency, injected_fields in definitions
    ]


def _require_db(context: ToolExecutionContext) -> AsyncSession:
    if context.db is None:
        raise ValueError("trusted database context is required")
    return context.db


def _require_learner(context: ToolExecutionContext):
    if context.learner_id is None:
        raise ValueError("trusted learner context is required")
    return context.learner_id


def _validate_candidates(candidates: list[ToolBinding]) -> None:
    seen: set[tuple[str, str]] = set()
    for binding in candidates:
        key = (binding.spec.name, binding.spec.version)
        if key in seen:
            raise ValueError(f"Duplicate tool registration: {key[0]}@{key[1]}")
        seen.add(key)
        if not binding.spec.name or len(binding.spec.name) > 120:
            raise ValueError("Invalid tool name")
        validate(instance={}, schema={"type": "object", "properties": {}})
        if not isinstance(binding.spec.input_schema, dict) or not isinstance(
            binding.spec.output_schema, dict
        ):
            raise ValueError(f"Invalid schema for {binding.spec.name}")


def _spec_hash(spec: ToolSpec) -> str:
    payload = spec.model_dump(
        mode="json",
        exclude={"enabled", "health_status", "registered_at", "last_health_check_at", "spec_hash"},
    )
    return stable_json_hash(payload)


def _now() -> datetime:
    return datetime.now(timezone.utc)


tool_catalog = ToolCatalogManager()
