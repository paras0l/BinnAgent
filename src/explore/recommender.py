import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.explore.capabilities import ExploreCapabilityRegistry, explore_capability_registry
from src.explore.schemas import (
    ExploreCapabilityRecommendation,
    ExploreCapabilitySpec,
    ExploreRecommendationContext,
)
from src.models.explore import ExploreFeaturePreference
from src.prompts import PromptExecutionContext, PromptExecutor
from src.providers.router import ModelRouter


@dataclass
class _ScoredCapability:
    spec: ExploreCapabilitySpec
    score: float
    reason: str
    source: str = "rule"


class ExploreCapabilityRecommender:
    def __init__(
        self,
        db: AsyncSession,
        *,
        registry: ExploreCapabilityRegistry = explore_capability_registry,
        rerank_with_llm: bool | None = None,
        model_router: ModelRouter | None = None,
    ):
        self.db = db
        self.registry = registry
        self.rerank_with_llm = (
            settings.explore_llm_rerank_enabled if rerank_with_llm is None else rerank_with_llm
        )
        self.model_router = model_router

    async def recommend_for_daily_lesson(
        self,
        context: ExploreRecommendationContext,
    ) -> list[ExploreCapabilityRecommendation]:
        return await self.recommend(context)

    async def recommend_for_knowledge_exercise(
        self,
        context: ExploreRecommendationContext,
    ) -> list[ExploreCapabilityRecommendation]:
        return await self.recommend(context)

    async def recommend(
        self,
        context: ExploreRecommendationContext,
        *,
        limit: int = 3,
    ) -> list[ExploreCapabilityRecommendation]:
        preferences = await self._load_preferences(context.learner_id)
        scored = self._score_candidates(context, preferences)
        if not scored:
            scored = self._fallback_candidates(context, preferences)

        scored = sorted(scored, key=lambda item: (-item.score, item.spec.capability_id))[:5]
        source = "rule" if any(item.source == "rule" for item in scored) else "fallback"
        if self.rerank_with_llm and self.model_router is not None and scored:
            try:
                scored = await self._rerank_with_llm(context, scored)
                source = "llm_rerank"
            except Exception:
                scored = sorted(scored, key=lambda item: (-item.score, item.spec.capability_id))
                source = "rule"

        return [
            self._to_recommendation(item, context, source=source)
            for item in scored[: max(1, min(limit, 3))]
        ]

    async def _load_preferences(
        self,
        learner_id: uuid.UUID,
    ) -> dict[str, ExploreFeaturePreference]:
        result = await self.db.execute(
            select(ExploreFeaturePreference).where(
                ExploreFeaturePreference.learner_id == learner_id
            )
        )
        return {item.feature_id: item for item in result.scalars().all()}

    def _score_candidates(
        self,
        context: ExploreRecommendationContext,
        preferences: dict[str, ExploreFeaturePreference],
    ) -> list[_ScoredCapability]:
        error_text = _error_text(context)
        target_type = _target_type(context)
        learning_skill = _learning_skill(context)
        mastery_need = _mastery_need(context.mastery_update)
        memory_relevance = 1.0 if context.memory_context else 0.0
        results: list[_ScoredCapability] = []

        for spec in self.registry.ready():
            if not _capability_is_contextually_eligible(spec, context):
                continue
            target_match = _target_match(spec, target_type, learning_skill)
            error_match = _error_match(spec, error_text)
            if not target_match and not error_match and mastery_need < 0.35:
                continue
            preference = preferences.get(spec.feature_id)
            preference_bonus = 1.0 if preference and preference.is_favorite else 0.0
            novelty_bonus = _novelty_bonus(preference, error_match)
            score = (
                0.35 * target_match
                + 0.25 * error_match
                + 0.15 * mastery_need
                + 0.10 * memory_relevance
                + 0.10 * preference_bonus
                + 0.05 * novelty_bonus
            ) * spec.priority_weight
            if score <= 0:
                continue
            results.append(
                _ScoredCapability(
                    spec=spec,
                    score=round(min(score, 1.0), 4),
                    reason=_reason_for(spec, context, target_match, error_match, mastery_need),
                )
            )
        return results

    def _fallback_candidates(
        self,
        context: ExploreRecommendationContext,
        preferences: dict[str, ExploreFeaturePreference],
    ) -> list[_ScoredCapability]:
        fallback_ids = ["daily-lesson", "vocab-review"]
        if _learning_skill(context) == "writing":
            fallback_ids = ["writing-phrasebook"]
        elif _learning_skill(context) == "grammar":
            fallback_ids = ["grammar-explain"]
        for capability_id in fallback_ids:
            spec = self.registry.get(capability_id)
            if spec and spec.status == "ready":
                preference = preferences.get(spec.feature_id)
                score = 0.55 + (0.05 if preference and preference.is_favorite else 0.0)
                return [
                    _ScoredCapability(
                        spec=spec,
                        score=score,
                        reason="当前上下文不足，先推荐一个通用学习入口继续推进。",
                        source="fallback",
                    )
                ]
        return []

    async def _rerank_with_llm(
        self,
        context: ExploreRecommendationContext,
        scored: list[_ScoredCapability],
    ) -> list[_ScoredCapability]:
        candidate_by_id = {item.spec.capability_id: item for item in scored}
        llm_items = await self._call_llm_rerank(context, scored)
        reranked: list[_ScoredCapability] = []
        for item in llm_items:
            capability_id = str(item.get("capability_id") or "")
            original = candidate_by_id.get(capability_id)
            if original is None:
                continue
            score = item.get("priority_score", original.score)
            reason = item.get("reason") or original.reason
            normalized_score = float(score) if isinstance(score, int | float) else original.score
            reranked.append(
                _ScoredCapability(
                    spec=original.spec,
                    score=round(max(0.0, min(normalized_score, 1.0)), 4),
                    reason=str(reason),
                )
            )
        if llm_items and not reranked:
            return scored
        return sorted(reranked, key=lambda item: (-item.score, item.spec.capability_id))

    async def _call_llm_rerank(
        self,
        context: ExploreRecommendationContext,
        scored: list[_ScoredCapability],
    ) -> list[dict[str, Any]]:
        if self.model_router is None:
            return []
        result = await PromptExecutor(db=self.db, model_router=self.model_router).execute(
            prompt_id="explore.capability_rerank",
            version="v1",
            variables={
                "context": _llm_context_payload(context),
                "candidates": [_llm_candidate_payload(item) for item in scored],
            },
            context=PromptExecutionContext(
                learner_id=context.learner_id,
                episode_id=context.episode_id,
                source_module="explore.recommender",
                target_type=_target_type(context),
                target_id=context.knowledge_point_id or _target_label(context),
                metadata={
                    "candidate_count": len(scored),
                    "learning_skill": _learning_skill(context),
                },
            ),
        )
        if result.validated_output is None or result.decision == "rejected":
            raise ValueError(result.schema_error_summary or "Invalid explore capability rerank output")
        recommendations = result.validated_output.get("recommendations")
        return recommendations if isinstance(recommendations, list) else []

    def _to_recommendation(
        self,
        scored: _ScoredCapability,
        context: ExploreRecommendationContext,
        *,
        source: str,
    ) -> ExploreCapabilityRecommendation:
        spec = scored.spec
        return ExploreCapabilityRecommendation(
            recommendation_id=f"caprec:{uuid.uuid4()}",
            capability_id=spec.capability_id,
            feature_id=spec.feature_id,
            title=spec.title,
            reason=scored.reason,
            priority_score=round(scored.score, 4),
            category=spec.category,
            action=spec.action,
            tool_target=spec.tool_target,
            route_hint=spec.route_hint,
            prompt_seed=spec.metadata.get("prompt") if isinstance(spec.metadata, dict) else None,
            input_payload={
                "knowledge_point_id": context.knowledge_point_id,
                "knowledge_point_title": context.knowledge_point_title,
                "learning_skill": _learning_skill(context),
            },
            evidence_refs=context.evidence_refs,
            source=source,  # type: ignore[arg-type]
        )


def _target_type(context: ExploreRecommendationContext) -> str | None:
    task_spec = context.task_spec or {}
    target = task_spec.get("target") if isinstance(task_spec.get("target"), dict) else {}
    return (
        context.metadata.get("target_type")
        or target.get("target_type")
        or target.get("type")
        or ("knowledge_point" if context.knowledge_point_id else None)
    )


def _target_label(context: ExploreRecommendationContext) -> str | None:
    task_spec = context.task_spec or {}
    target = task_spec.get("target") if isinstance(task_spec.get("target"), dict) else {}
    metadata = context.metadata or {}
    target_metadata = target.get("metadata") if isinstance(target.get("metadata"), dict) else {}
    candidates = [
        metadata.get("target_label"),
        metadata.get("word"),
        metadata.get("term"),
        target.get("label"),
        target.get("target_label"),
        target_metadata.get("target_label"),
        target_metadata.get("word"),
        target_metadata.get("term"),
        context.knowledge_point_title,
    ]
    for payload in (context.grading_result, context.mastery_update, context.memory_context):
        if not isinstance(payload, dict):
            continue
        candidates.extend(
            [
                payload.get("target_label"),
                payload.get("word"),
                payload.get("term"),
                payload.get("vocabulary"),
            ]
        )
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _learning_skill(context: ExploreRecommendationContext) -> str | None:
    if context.learning_skill:
        return context.learning_skill
    task_spec = context.task_spec or {}
    metadata = task_spec.get("metadata") if isinstance(task_spec.get("metadata"), dict) else {}
    value = metadata.get("learning_skill") or metadata.get("skill")
    return str(value) if value else None


def _capability_is_contextually_eligible(
    spec: ExploreCapabilitySpec,
    context: ExploreRecommendationContext,
) -> bool:
    target_label = _target_label(context)
    if not target_label:
        return True
    if spec.capability_id == "word-roots-affixes" and _looks_like_proper_noun_target(target_label):
        return False
    if spec.capability_id == "vocabulary-detail" and _looks_like_bare_name_target(target_label):
        return False
    return True


def _looks_like_proper_noun_target(value: str) -> bool:
    normalized = _normalize_target_label(value)
    if not normalized:
        return False
    if normalized.lower().startswith(("unit ", "lesson ", "starter unit ")):
        return False
    if " " in normalized or "-" in normalized:
        tokens = [token for token in normalized.replace("-", " ").split() if token]
        return bool(tokens) and all(_is_capitalized_name_token(token) for token in tokens)
    return _is_capitalized_name_token(normalized)


def _looks_like_bare_name_target(value: str) -> bool:
    normalized = _normalize_target_label(value)
    if not normalized:
        return False
    return _looks_like_proper_noun_target(normalized)


def _normalize_target_label(value: str) -> str:
    return value.strip().strip("\"'`“”‘’.,:;!?()[]{}")


def _is_capitalized_name_token(value: str) -> bool:
    if len(value) < 2 or not value.isalpha() or not value.isascii():
        return False
    return value[0].isupper() and value[1:].islower()


def _llm_context_payload(context: ExploreRecommendationContext) -> dict[str, Any]:
    return {
        "target_label": _target_label(context),
        "target_type": _target_type(context),
        "knowledge_point_id": context.knowledge_point_id,
        "knowledge_point_title": context.knowledge_point_title,
        "learning_skill": _learning_skill(context),
        "subskill": context.subskill,
        "error_text": _error_text(context),
        "grading_result": context.grading_result or {},
        "mastery_update": context.mastery_update or {},
        "memory_context": context.memory_context or {},
        "metadata": context.metadata or {},
        "evidence_refs": context.evidence_refs[:5],
    }


def _llm_candidate_payload(item: _ScoredCapability) -> dict[str, Any]:
    spec = item.spec
    return {
        "capability_id": spec.capability_id,
        "title": spec.title,
        "category": spec.category,
        "learning_skill": spec.learning_skill,
        "description": spec.description,
        "recommended_when": spec.recommended_when,
        "not_recommended_when": spec.not_recommended_when,
        "expected_learning_outcome": spec.expected_learning_outcome,
        "rule_score": item.score,
        "rule_reason": item.reason,
    }


def _error_text(context: ExploreRecommendationContext) -> str:
    parts: list[str] = []
    for payload in (context.grading_result, context.mastery_update, context.metadata):
        if not isinstance(payload, dict):
            continue
        for key in ("error_type", "weakness_tags", "feedback", "summary", "subskill"):
            value = payload.get(key)
            if value:
                parts.append(str(value))
    if context.subskill:
        parts.append(context.subskill)
    return " ".join(parts).lower()


def _target_match(
    spec: ExploreCapabilitySpec,
    target_type: str | None,
    learning_skill: str | None,
) -> float:
    score = 0.0
    if target_type and target_type in spec.supported_target_types:
        score = max(score, 1.0)
    if learning_skill and learning_skill == spec.learning_skill:
        score = max(score, 0.9)
    if target_type == "knowledge_point" and spec.capability_id == "grammar-explain":
        score = max(score, 0.8)
    return score


def _error_match(spec: ExploreCapabilitySpec, error_text: str) -> float:
    if not error_text:
        return 0.0
    direct = any(token.lower() in error_text for token in spec.supported_error_types)
    if direct:
        return 1.0
    category_rules = {
        "grammar": ["grammar", "tense", "clause", "article", "主谓", "从句"],
        "writing": ["writing", "essay", "transition", "cohesion", "collocation", "connector"],
        "vocabulary": ["vocabulary", "word", "spelling", "meaning", "recall"],
        "reading": ["reading", "inference", "main idea", "定位", "detail"],
        "speaking": ["pronunciation", "speaking", "phonetic", "fluency", "rhythm"],
    }
    return 0.85 if any(token in error_text for token in category_rules.get(spec.category, [])) else 0.0


def _mastery_need(mastery_update: dict[str, Any] | None) -> float:
    if not isinstance(mastery_update, dict):
        return 0.0
    forgetting_risk = mastery_update.get("forgetting_risk")
    new_score = mastery_update.get("new_score")
    if isinstance(forgetting_risk, int | float):
        return min(1.0, max(0.0, float(forgetting_risk)))
    if isinstance(new_score, int | float):
        return min(1.0, max(0.0, 1.0 - float(new_score)))
    return 0.4 if mastery_update else 0.0


def _novelty_bonus(preference: ExploreFeaturePreference | None, error_match: float) -> float:
    if preference is None or preference.last_used_at is None:
        return 1.0
    if error_match >= 0.9:
        return 0.5
    now = datetime.now(timezone.utc)
    last_used = preference.last_used_at
    if last_used.tzinfo is None:
        last_used = last_used.replace(tzinfo=timezone.utc)
    hours = (now - last_used).total_seconds() / 3600
    if hours < 24:
        return -0.4
    if hours < 72:
        return 0.2
    return 0.8


def _reason_for(
    spec: ExploreCapabilitySpec,
    context: ExploreRecommendationContext,
    target_match: float,
    error_match: float,
    mastery_need: float,
) -> str:
    if error_match >= 0.9:
        return f"本次练习暴露了与「{spec.title}」匹配的错因，适合马上补一个专项入口。"
    if target_match >= 0.9:
        return f"当前学习目标和「{spec.title}」高度相关，可以帮助巩固这个知识点。"
    if mastery_need >= 0.5:
        return f"掌握度信号显示仍有遗忘风险，建议用「{spec.title}」继续巩固。"
    if context.knowledge_point_title:
        return f"围绕「{context.knowledge_point_title}」继续练习，适合打开「{spec.title}」。"
    return f"根据最近学习上下文，推荐使用「{spec.title}」。"
