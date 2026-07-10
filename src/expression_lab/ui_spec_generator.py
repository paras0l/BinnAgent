from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.expression_lab.schemas import ExpressionUiSpec
from src.expression_lab.ui_spec_validator import (
    build_fixed_fallback,
    build_text_fallback,
    expression_ui_fallback_parser,
    validate_ui_spec,
)
from src.memory.retriever import MemoryRetriever
from src.models.expression_lab import ExpressionLabSession
from src.models.learner import LearnerProfile
from src.prompts.executor import PromptExecutionContext, PromptExecutor
from src.providers.router import ModelRouter


GenerationMode = Literal["full", "retry", "regenerate_block", "practice_only"]


@dataclass(frozen=True)
class GenerationOutcome:
    status: Literal["ready", "partial", "error"]
    ui_spec: dict[str, Any]
    grading_spec: dict[str, Any]
    diagnostics: dict[str, Any]
    model_id: str | None
    prompt_id: str
    prompt_version: str
    prompt_hash: str | None
    execution_record_id: str | None = None


class ExpressionUiSpecGenerator:
    prompt_id = "expression_lab.ui_spec"
    prompt_version = "v1"

    def __init__(
        self,
        db: AsyncSession,
        model_router: ModelRouter,
        *,
        executor: PromptExecutor | None = None,
    ) -> None:
        self.db = db
        self.model_router = model_router
        self.executor = executor or PromptExecutor(db=db, model_router=model_router)

    async def generate(
        self,
        session: ExpressionLabSession,
        *,
        mode: GenerationMode = "full",
        block_id: str | None = None,
        instruction: str | None = None,
    ) -> GenerationOutcome:
        context_issue: str | None = None
        try:
            profile, memory_text = await self._learner_context(session)
        except Exception:
            profile = {"current_level": session.current_level}
            memory_text = ""
            context_issue = "learner_context_unavailable"
        source = {
            "type": session.source_type,
            "source_id": session.source_ref,
            "evidence": session.source_snapshot,
        }
        variables = {
            "generation_mode": mode,
            "session_id": str(session.id),
            "input_type": session.input_type,
            "input_text": session.input_text,
            "context": session.context,
            "style_goal": session.style_goal,
            "current_level": session.current_level,
            "needs_practice": session.needs_practice,
            "source": source,
            "block_id": block_id,
            "instruction": instruction,
            "learner_profile": profile,
            "memory_context": memory_text,
            "current_ui_spec": session.ui_spec_json or {},
        }

        try:
            execution = await self.executor.execute(
                prompt_id=self.prompt_id,
                version=self.prompt_version,
                variables=variables,
                context=PromptExecutionContext(
                    learner_id=session.learner_id,
                    episode_id=session.episode_id,
                    task_id=f"expression-lab:{session.id}:{mode}",
                    source_module="expression_lab",
                    target_type="expression_lab_session",
                    target_id=session.id,
                    metadata={"generation_mode": mode, "block_id": block_id},
                ),
                fallback_parser=lambda raw: expression_ui_fallback_parser(
                    raw,
                    session_id=session.id,
                    input_text=session.input_text,
                    input_type=session.input_type,
                    context=session.context,
                    style_goal=session.style_goal,
                    source_type=session.source_type,
                    source_ref=session.source_ref,
                ),
            )
        except Exception as exc:
            return self._deterministic_outcome(
                session,
                stage="provider_error_fixed_fallback",
                error_code=type(exc).__name__,
            )

        payload = execution.validated_output
        if payload is None:
            deterministic = self._deterministic_outcome(
                session,
                stage="rejected_fixed_fallback",
                error_code="prompt_output_rejected",
            )
            return GenerationOutcome(
                **{
                    **deterministic.__dict__,
                    "prompt_hash": execution.prompt_hash,
                    "model_id": _model_id(execution.provider, execution.model),
                    "execution_record_id": (
                        str(execution.execution_record_id)
                        if execution.execution_record_id is not None
                        else None
                    ),
                }
            )

        validation = validate_ui_spec(
            payload,
            session_id=session.id,
            input_text=session.input_text,
            input_type=session.input_type,
            context=session.context,
            style_goal=session.style_goal,
            source_type=session.source_type,
            source_ref=session.source_ref,
        )
        if not validation.valid or validation.render_payload is None:
            return self._deterministic_outcome(
                session,
                stage="post_validation_fixed_fallback",
                error_code="ui_spec_invalid_after_prompt",
                prompt_hash=execution.prompt_hash,
                model_id=_model_id(execution.provider, execution.model),
                execution_record_id=(
                    str(execution.execution_record_id)
                    if execution.execution_record_id is not None
                    else None
                ),
            )

        degraded = execution.schema_validation_status == "fallback" or bool(
            validation.removed_block_ids or validation.removed_action_ids
        )
        diagnostics = {
            "generation_mode": mode,
            "schema_validation_status": execution.schema_validation_status,
            "repair_used": execution.repair_used,
            "fallback_used": execution.fallback_used,
            "parse_mode": execution.parse_mode,
            "decision": execution.decision,
            "validation_issues": list(validation.issues),
            "removed_block_ids": list(validation.removed_block_ids),
            "removed_action_ids": list(validation.removed_action_ids),
            "fallback_stage": validation.fallback_stage,
            "context_issue": context_issue,
        }
        return GenerationOutcome(
            status="partial" if degraded else "ready",
            ui_spec=validation.render_payload,
            grading_spec=validation.grading_spec,
            diagnostics=diagnostics,
            model_id=_model_id(execution.provider, execution.model),
            prompt_id=execution.prompt_id,
            prompt_version=execution.prompt_version,
            prompt_hash=execution.prompt_hash,
            execution_record_id=(
                str(execution.execution_record_id)
                if execution.execution_record_id is not None
                else None
            ),
        )

    async def _learner_context(
        self, session: ExpressionLabSession
    ) -> tuple[dict[str, Any], str]:
        profile_result = await self.db.execute(
            select(LearnerProfile).where(LearnerProfile.learner_id == session.learner_id)
        )
        profile = profile_result.scalar_one_or_none()
        profile_payload = {
            "current_level": session.current_level or getattr(profile, "current_level", None),
            "target_exam": getattr(profile, "target_exam", None),
            "target_score": getattr(profile, "target_score", None),
            "interest_topics": getattr(profile, "interest_topics", None) or [],
            "weak_skills": getattr(profile, "weak_skills", None) or [],
        }
        skill = (
            "vocabulary"
            if session.input_type == "learning_target" and "word" in session.input_text.casefold()
            else "writing"
        )
        memory = await MemoryRetriever(self.db).retrieve_context(
            learner_id=session.learner_id,
            reason="expression_lab",
            skill=skill,
            limit=6,
        )
        return profile_payload, memory.prompt_text()

    def _deterministic_outcome(
        self,
        session: ExpressionLabSession,
        *,
        stage: str,
        error_code: str,
        prompt_hash: str | None = None,
        model_id: str | None = None,
        execution_record_id: str | None = None,
    ) -> GenerationOutcome:
        full_payload = build_fixed_fallback(
            session_id=session.id,
            input_text=session.input_text,
            input_type=session.input_type,
            context=session.context,
            style_goal=session.style_goal,
            source_type=session.source_type,
            source_ref=session.source_ref,
        )
        validation = validate_ui_spec(
            full_payload,
            session_id=session.id,
            input_text=session.input_text,
            input_type=session.input_type,
            context=session.context,
            style_goal=session.style_goal,
            source_type=session.source_type,
            source_ref=session.source_ref,
        )
        if not validation.valid or validation.render_payload is None:
            full_payload = build_text_fallback(
                session_id=session.id,
                input_text=session.input_text,
                input_type=session.input_type,
                context=session.context,
                style_goal=session.style_goal,
                source_type=session.source_type,
                source_ref=session.source_ref,
            )
            validation = validate_ui_spec(
                full_payload,
                session_id=session.id,
                input_text=session.input_text,
                input_type=session.input_type,
                context=session.context,
                style_goal=session.style_goal,
                source_type=session.source_type,
                source_ref=session.source_ref,
            )
            stage = "text_fallback"
        if validation.render_payload is None:
            return GenerationOutcome(
                status="error",
                ui_spec={},
                grading_spec={},
                diagnostics={"fallback_stage": "failed", "error_code": "fallback_invalid"},
                model_id=model_id,
                prompt_id=self.prompt_id,
                prompt_version=self.prompt_version,
                prompt_hash=prompt_hash,
                execution_record_id=execution_record_id,
            )
        return GenerationOutcome(
            status="partial",
            ui_spec=validation.render_payload,
            grading_spec=validation.grading_spec,
            diagnostics={
                "schema_validation_status": "fallback",
                "fallback_used": True,
                "fallback_stage": stage,
                "error_code": error_code,
                "validation_issues": list(validation.issues),
            },
            model_id=model_id,
            prompt_id=self.prompt_id,
            prompt_version=self.prompt_version,
            prompt_hash=prompt_hash,
            execution_record_id=execution_record_id,
        )


def generation_variables_json(variables: dict[str, Any]) -> str:
    """Stable helper used by prompt evals and diagnostics."""

    return json.dumps(variables, ensure_ascii=False, sort_keys=True)


def _model_id(provider: str | None, model: str | None) -> str | None:
    if model and provider:
        return f"{provider}:{model}"
    return model or provider


def assert_ui_spec(payload: dict[str, Any]) -> ExpressionUiSpec:
    return ExpressionUiSpec.model_validate(payload)
