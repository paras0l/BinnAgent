import inspect
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.prompt_execution import PromptExecutionRecord
from src.observability import observe
from src.prompts.registry import PromptRegistry, RenderedPrompt, prompt_registry
from src.prompts.validation import maybe_validate_json_text, validate_output_schema
from src.providers.base import ChatRequest
from src.providers.router import ModelRouter

FallbackParser = Callable[[str], dict[str, Any] | None]


@dataclass
class PromptExecutionContext:
    learner_id: uuid.UUID | None = None
    episode_id: uuid.UUID | None = None
    task_id: str | None = None
    source_module: str = "unknown"
    target_type: str | None = None
    target_id: str | uuid.UUID | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptExecutionResult:
    prompt_id: str
    prompt_version: str
    prompt_hash: str
    input_hash: str
    input_schema: str | None
    output_schema: str | None
    output_schema_json: dict[str, Any] | None
    validated_output: dict[str, Any] | None
    schema_validation_status: str
    schema_error_summary: str | None
    repair_used: bool
    fallback_used: bool
    parse_mode: str
    confidence: float | None
    decision: str
    raw_output: str
    provider: str | None
    model: str | None
    finish_reason: str | None
    langfuse_trace_id: str | None
    langfuse_observation_id: str | None
    execution_record_id: uuid.UUID | None


class PromptExecutor:
    def __init__(
        self,
        *,
        db: AsyncSession | None = None,
        model_router: ModelRouter | None = None,
        registry: PromptRegistry = prompt_registry,
    ) -> None:
        self.db = db
        self.model_router = model_router
        self.registry = registry

    async def execute(
        self,
        *,
        prompt_id: str,
        variables: dict[str, Any],
        context: PromptExecutionContext,
        version: str | None = None,
        request_overrides: dict[str, Any] | None = None,
        fallback_parser: FallbackParser | None = None,
    ) -> PromptExecutionResult:
        if self.model_router is None:
            raise ValueError("PromptExecutor.execute requires a model_router")

        rendered = self.registry.render(prompt_id=prompt_id, version=version, variables=variables)
        langfuse_trace_id: str | None = None
        langfuse_observation_id: str | None = None
        metadata = _langfuse_metadata(rendered, context)
        with observe(
            f"prompt.{rendered.prompt_id}",
            as_type="generation",
            input=rendered.prompt,
            metadata=metadata,
        ) as observation:
            langfuse_trace_id, langfuse_observation_id = _extract_langfuse_ids(observation)
            response = await self.model_router.chat(
                _chat_request(rendered, model_router=self.model_router, overrides=request_overrides)
            )
            raw_output = response.content
            if observation is not None:
                observation.update(output=raw_output)

        return await self._finalize(
            rendered=rendered,
            raw_output=raw_output,
            context=context,
            fallback_parser=fallback_parser,
            provider=response.provider,
            model=response.model,
            finish_reason=response.finish_reason,
            provider_repair_used=bool(response.usage.get("retry_count")),
            langfuse_trace_id=langfuse_trace_id,
            langfuse_observation_id=langfuse_observation_id,
        )

    async def execute_messages(
        self,
        *,
        prompt_id: str,
        variables: dict[str, Any],
        messages: list[dict[str, str]],
        context: PromptExecutionContext,
        version: str | None = None,
        request_overrides: dict[str, Any] | None = None,
        fallback_parser: FallbackParser | None = None,
    ) -> PromptExecutionResult:
        if self.model_router is None:
            raise ValueError("PromptExecutor.execute_messages requires a model_router")

        rendered = self.registry.render(prompt_id=prompt_id, version=version, variables=variables)
        langfuse_trace_id: str | None = None
        langfuse_observation_id: str | None = None
        metadata = _langfuse_metadata(rendered, context)
        with observe(
            f"prompt.{rendered.prompt_id}",
            as_type="generation",
            input=messages,
            metadata=metadata,
        ) as observation:
            langfuse_trace_id, langfuse_observation_id = _extract_langfuse_ids(observation)
            response = await self.model_router.chat(
                _chat_request(
                    rendered,
                    messages=messages,
                    model_router=self.model_router,
                    overrides=request_overrides,
                )
            )
            raw_output = response.content
            if observation is not None:
                observation.update(output=raw_output)

        return await self._finalize(
            rendered=rendered,
            raw_output=raw_output,
            context=context,
            fallback_parser=fallback_parser,
            provider=response.provider,
            model=response.model,
            finish_reason=response.finish_reason,
            provider_repair_used=bool(response.usage.get("retry_count")),
            langfuse_trace_id=langfuse_trace_id,
            langfuse_observation_id=langfuse_observation_id,
        )

    async def stream_messages(
        self,
        *,
        prompt_id: str,
        variables: dict[str, Any],
        messages: list[dict[str, str]],
        context: PromptExecutionContext,
        version: str | None = None,
        request_overrides: dict[str, Any] | None = None,
    ) -> AsyncIterator[Any]:
        if self.model_router is None:
            raise ValueError("PromptExecutor.stream_messages requires a model_router")

        rendered = self.registry.render(prompt_id=prompt_id, version=version, variables=variables)
        langfuse_trace_id: str | None = None
        langfuse_observation_id: str | None = None
        chunks: list[str] = []
        finish_reason: str | None = None
        metadata = {**_langfuse_metadata(rendered, context), "stream": True}
        with observe(
            f"prompt.{rendered.prompt_id}.stream",
            as_type="generation",
            input=messages,
            metadata=metadata,
        ) as observation:
            langfuse_trace_id, langfuse_observation_id = _extract_langfuse_ids(observation)
            async for chunk in self.model_router.stream_chat(
                _chat_request(
                    rendered,
                    messages=messages,
                    model_router=self.model_router,
                    overrides=request_overrides,
                )
            ):
                content = getattr(chunk, "content", "") if not isinstance(chunk, str) else chunk
                chunk_finish_reason = getattr(chunk, "finish_reason", None)
                if content:
                    chunks.append(content)
                if chunk_finish_reason:
                    finish_reason = chunk_finish_reason
                yield chunk
            raw_output = "".join(chunks)
            if observation is not None:
                observation.update(output=raw_output)

        await self._finalize(
            rendered=rendered,
            raw_output=raw_output,
            context=context,
            fallback_parser=None,
            provider=None,
            model=None,
            finish_reason=finish_reason,
            provider_repair_used=False,
            langfuse_trace_id=langfuse_trace_id,
            langfuse_observation_id=langfuse_observation_id,
        )

    async def execute_with_raw_output(
        self,
        *,
        prompt_id: str,
        variables: dict[str, Any],
        raw_output: str,
        context: PromptExecutionContext,
        version: str | None = None,
        fallback_parser: FallbackParser | None = None,
    ) -> PromptExecutionResult:
        rendered = self.registry.render(prompt_id=prompt_id, version=version, variables=variables)
        langfuse_trace_id: str | None = None
        langfuse_observation_id: str | None = None
        metadata = {
            **_langfuse_metadata(rendered, context),
            "input_mode": "provided_raw_output",
        }
        with observe(
            f"prompt.{rendered.prompt_id}.manual",
            as_type="generation",
            input=rendered.prompt,
            metadata=metadata,
        ) as observation:
            langfuse_trace_id, langfuse_observation_id = _extract_langfuse_ids(observation)
            if observation is not None:
                observation.update(output=raw_output)

        return await self._finalize(
            rendered=rendered,
            raw_output=raw_output,
            context=context,
            fallback_parser=fallback_parser,
            provider=None,
            model=None,
            finish_reason=None,
            provider_repair_used=False,
            langfuse_trace_id=langfuse_trace_id,
            langfuse_observation_id=langfuse_observation_id,
        )

    async def _finalize(
        self,
        *,
        rendered: RenderedPrompt,
        raw_output: str,
        context: PromptExecutionContext,
        fallback_parser: FallbackParser | None,
        provider: str | None,
        model: str | None,
        finish_reason: str | None,
        provider_repair_used: bool,
        langfuse_trace_id: str | None,
        langfuse_observation_id: str | None,
    ) -> PromptExecutionResult:
        payload: dict[str, Any] | None = None
        schema_validation_status = "not_applicable"
        schema_error_summary: str | None = None
        repair_used = provider_repair_used
        fallback_used = False
        parse_mode = "text_only"
        decision = "accepted"

        if rendered.output_schema_json is not None:
            validation = maybe_validate_json_text(raw_output, rendered.output_schema_json)
            payload = validation.payload
            repair_used = provider_repair_used or validation.repair_used
            parse_mode = "provider_repair" if provider_repair_used else validation.parse_mode
            schema_error_summary = validation.error_summary
            if validation.valid and payload is not None:
                schema_validation_status = "repaired" if repair_used else "passed"
                decision = "accepted"
            else:
                fallback_payload = fallback_parser(raw_output) if fallback_parser else None
                fallback_validation = (
                    validate_output_schema(fallback_payload, rendered.output_schema_json)
                    if fallback_payload is not None
                    else None
                )
                if fallback_payload is not None and fallback_validation and fallback_validation.valid:
                    payload = fallback_payload
                    fallback_used = True
                    schema_validation_status = "fallback"
                    parse_mode = "regex_fallback"
                    decision = "review_required"
                else:
                    schema_validation_status = "failed"
                    decision = "rejected"
                    if fallback_validation and fallback_validation.error_summary:
                        schema_error_summary = fallback_validation.error_summary
        confidence = _infer_confidence(payload)

        record_id = await self._record(
            rendered=rendered,
            context=context,
            schema_validation_status=schema_validation_status,
            schema_error_summary=schema_error_summary,
            repair_used=repair_used,
            fallback_used=fallback_used,
            parse_mode=parse_mode,
            confidence=confidence,
            decision=decision,
            langfuse_trace_id=langfuse_trace_id,
            langfuse_observation_id=langfuse_observation_id,
        )
        return PromptExecutionResult(
            prompt_id=rendered.prompt_id,
            prompt_version=rendered.version,
            prompt_hash=rendered.prompt_hash,
            input_hash=rendered.input_hash,
            input_schema=rendered.input_schema,
            output_schema=rendered.output_schema,
            output_schema_json=rendered.output_schema_json,
            validated_output=payload,
            schema_validation_status=schema_validation_status,
            schema_error_summary=schema_error_summary,
            repair_used=repair_used,
            fallback_used=fallback_used,
            parse_mode=parse_mode,
            confidence=confidence,
            decision=decision,
            raw_output=raw_output,
            provider=provider,
            model=model,
            finish_reason=finish_reason,
            langfuse_trace_id=langfuse_trace_id,
            langfuse_observation_id=langfuse_observation_id,
            execution_record_id=record_id,
        )

    async def _record(
        self,
        *,
        rendered: RenderedPrompt,
        context: PromptExecutionContext,
        schema_validation_status: str,
        schema_error_summary: str | None,
        repair_used: bool,
        fallback_used: bool,
        parse_mode: str,
        confidence: float | None,
        decision: str,
        langfuse_trace_id: str | None,
        langfuse_observation_id: str | None,
    ) -> uuid.UUID | None:
        if self.db is None:
            return None

        record = PromptExecutionRecord(
            id=uuid.uuid4(),
            learner_id=context.learner_id,
            episode_id=context.episode_id,
            task_id=context.task_id,
            source_module=context.source_module,
            prompt_id=rendered.prompt_id,
            prompt_version=rendered.version,
            prompt_hash=rendered.prompt_hash,
            input_hash=rendered.input_hash,
            input_schema=rendered.input_schema,
            output_schema=rendered.output_schema,
            model_policy_snapshot=dict(rendered.model_policy),
            adaptive_policy_snapshot=dict(context.metadata.get("teaching_policy") or {}),
            teaching_policy_decision_id=_optional_uuid(
                context.metadata.get("teaching_policy_decision_id")
            ),
            langfuse_trace_id=langfuse_trace_id,
            langfuse_observation_id=langfuse_observation_id,
            schema_validation_status=schema_validation_status,
            schema_error_summary=schema_error_summary,
            repair_used=repair_used,
            fallback_used=fallback_used,
            parse_mode=parse_mode,
            confidence=confidence,
            decision=decision,
            target_type=context.target_type,
            target_id=str(context.target_id) if context.target_id is not None else None,
        )
        add_result = self.db.add(record)
        if inspect.isawaitable(add_result):
            await add_result
        flush_result = self.db.flush()
        if inspect.isawaitable(flush_result):
            await flush_result
        return record.id


def _optional_uuid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _chat_request(
    rendered: RenderedPrompt,
    *,
    messages: list[dict[str, str]] | None = None,
    model_router: ModelRouter | None = None,
    overrides: dict[str, Any] | None = None,
) -> ChatRequest:
    policy = rendered.model_policy
    overrides = overrides or {}
    preferred_provider = (
        overrides.get("preferred_provider")
        or policy.get("preferred_provider")
        or policy.get("provider")
        or (
            getattr(model_router, "default_provider", settings.model_provider)
            if model_router is not None
            else settings.model_provider
        )
    )
    default_model = policy.get("default_model")
    preferred_model = (
        overrides.get("preferred_model")
        or policy.get("preferred_model")
        or policy.get("model")
    )
    preferred_model = _resolve_model_for_provider(
        provider=str(preferred_provider),
        default_model=default_model,
        preferred_model=preferred_model,
    )

    metadata = {
        "prompt_id": rendered.prompt_id,
        "prompt_version": rendered.version,
        "prompt_hash": rendered.prompt_hash,
        "input_hash": rendered.input_hash,
    }
    thinking = overrides.get("thinking", policy.get("thinking"))
    if thinking in {"enabled", "disabled"}:
        metadata["thinking"] = str(thinking)

    return ChatRequest(
        messages=messages or [{"role": "user", "content": rendered.prompt}],
        task_type=str(overrides.get("task_type") or rendered.prompt_id),
        temperature=float(overrides.get("temperature", policy.get("temperature", 0.3))),
        max_tokens=int(overrides.get("max_tokens", policy.get("max_tokens", 2000))),
        response_schema=rendered.output_schema_json,
        metadata=metadata,
        preferred_provider=str(preferred_provider),
        preferred_model=preferred_model,
        local_only=bool(overrides.get("local_only", policy.get("local_only", True))),
    )


def _resolve_model_for_provider(
    *,
    provider: str,
    default_model: Any,
    preferred_model: Any,
) -> str | None:
    normalized_provider = provider.strip().lower()
    model = str(preferred_model) if preferred_model else None
    if normalized_provider != "ollama" and model in {
        settings.ollama_chat_model,
        settings.ollama_utility_model,
    }:
        model = None
    if model is not None:
        return model
    if normalized_provider == "deepseek":
        if default_model == "ollama_utility":
            return settings.deepseek_utility_model
        return settings.deepseek_chat_model
    if normalized_provider == "longcat":
        if default_model == "ollama_utility":
            return settings.longcat_utility_model
        return settings.longcat_chat_model
    if default_model == "ollama_utility":
        return settings.ollama_utility_model
    if default_model == "ollama_chat":
        return settings.ollama_chat_model
    return None


def _langfuse_metadata(
    rendered: RenderedPrompt,
    context: PromptExecutionContext,
) -> dict[str, Any]:
    return {
        "prompt_id": rendered.prompt_id,
        "prompt_version": rendered.version,
        "prompt_hash": rendered.prompt_hash,
        "input_hash": rendered.input_hash,
        "input_schema": rendered.input_schema,
        "output_schema": rendered.output_schema,
        "model_policy": rendered.model_policy,
        "source_module": context.source_module,
        "learner_id": str(context.learner_id) if context.learner_id else None,
        "episode_id": str(context.episode_id) if context.episode_id else None,
        "task_id": context.task_id,
        "target_type": context.target_type,
        "target_id": str(context.target_id) if context.target_id is not None else None,
        **context.metadata,
    }


def _extract_langfuse_ids(observation: Any) -> tuple[str | None, str | None]:
    if observation is None:
        return None, None
    observation_id = _string_attr(observation, "id") or _string_attr(observation, "observation_id")
    trace_id = _string_attr(observation, "trace_id")
    trace = getattr(observation, "trace", None)
    if trace_id is None and trace is not None:
        trace_id = _string_attr(trace, "id")
    return trace_id, observation_id


def _string_attr(obj: Any, name: str) -> str | None:
    value = getattr(obj, name, None)
    return str(value) if value else None


def _infer_confidence(payload: dict[str, Any] | None) -> float | None:
    if payload is None:
        return None
    value = payload.get("confidence")
    if isinstance(value, int | float):
        return _clamp_confidence(float(value))
    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        scores: list[float] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            score = item.get("confidence", item.get("quality_score"))
            if isinstance(score, int | float):
                scores.append(_clamp_confidence(float(score)))
        if scores:
            return min(scores)
    cards = payload.get("cards")
    if isinstance(cards, list):
        scores = []
        for item in cards:
            if not isinstance(item, dict):
                continue
            score = item.get("confidence")
            if isinstance(score, int | float):
                scores.append(_clamp_confidence(float(score)))
        if scores:
            return min(scores)
    return None


def _clamp_confidence(value: float) -> float:
    return max(0.0, min(value, 1.0))
