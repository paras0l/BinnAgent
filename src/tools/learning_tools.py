"""Agent-facing tools for the can-do -> evidence -> learner-state loop.

The functions in this module deliberately keep model-visible payloads separate
from the trusted learner/database context supplied by the runtime gateway.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adaptive.fsrs import FSRSState, retrievability
from src.mastery import AttemptSignal, MasteryEngine
from src.models.adaptive import AssessmentEvidence, FSRSReviewState, LearningEvidenceEvent
from src.models.knowledge import (
    ExerciseAttempt,
    GrammarCanDoProfile,
    KnowledgePoint,
    LearnerKnowledgeState,
)

MATCHER_VERSION = "can-do-hybrid-rules-v1"
ANALYZER_VERSION = "learner-response-rules-v1"
_TOKEN_RE = re.compile(r"[a-z]+(?:'[a-z]+)?|[\u4e00-\u9fff]+", re.IGNORECASE)
_NO_ATTEMPT = {"", "i don't know", "idk", "不知道", "不会", "跳过", "skip"}


class FindCanDoForItemInput(BaseModel):
    question: str = Field(min_length=1, max_length=5000)
    task_type: str = Field(min_length=1, max_length=80)
    correct_answer: str = Field(min_length=1, max_length=5000)
    explanation: str | None = Field(default=None, max_length=5000)
    knowledge_type: str = Field(default="grammar", max_length=40)
    top_k: int = Field(default=3, ge=1, le=10)


class FindCanDoForQueryInput(BaseModel):
    query: str = Field(min_length=1, max_length=5000)
    user_level: str | None = Field(default=None, max_length=10)
    conversation_context: list[str] = Field(default_factory=list, max_length=10)
    top_k: int = Field(default=3, ge=1, le=10)


class AnalyzeLearnerResponseInput(BaseModel):
    question_id: str = Field(min_length=1, max_length=255)
    question: str = Field(min_length=1, max_length=5000)
    expected_answer: str = Field(min_length=1, max_length=5000)
    learner_answer: str = Field(max_length=5000)
    linked_can_do_ids: list[str] = Field(default_factory=list, max_length=20)


class GetLearnerKnowledgeStateInput(BaseModel):
    knowledge_ids: list[str] = Field(min_length=1, max_length=50)
    recent_evidence_limit: int = Field(default=5, ge=1, le=20)


LearningOutcome = Literal["SUCCESS", "UNSUCCESSFUL", "NO_ATTEMPT", "UNRELATED_ERROR"]


class LearningObservationInput(BaseModel):
    knowledge_id: str = Field(min_length=1, max_length=255)
    outcome: LearningOutcome
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: dict[str, Any] = Field(default_factory=dict)
    evidence_mode: Literal[
        "recognition", "recall", "spelling", "listening", "context_use", "production"
    ] = "recall"
    item_difficulty_prior: float = Field(default=0.5, ge=0.0, le=1.0)


class RecordLearningEvidenceInput(BaseModel):
    source: str = Field(min_length=1, max_length=50)
    question_id: str | None = Field(default=None, max_length=255)
    observations: list[LearningObservationInput] = Field(default_factory=list, max_length=20)
    event_id: str = Field(min_length=1, max_length=255)
    raw_evidence: dict[str, Any] = Field(default_factory=dict)
    operation: Literal["record", "revoke"] = "record"
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_operation(self) -> "RecordLearningEvidenceInput":
        if self.operation == "record" and not self.observations:
            raise ValueError("record requires at least one observation")
        if self.operation == "revoke" and not self.reason:
            raise ValueError("revoke requires a reason")
        return self


@dataclass(frozen=True)
class _Candidate:
    profile: GrammarCanDoProfile
    point: KnowledgePoint
    score: float
    reason: str


async def find_can_do_for_item(
    db: AsyncSession, payload: FindCanDoForItemInput
) -> dict[str, Any]:
    text = " ".join(
        part for part in (payload.question, payload.correct_answer, payload.explanation) if part
    )
    candidates = await _rank_candidates(db, text, payload.top_k)
    atomic_kcs = _atomic_kcs(payload.question, payload.correct_answer)
    matches = [_candidate_payload(candidate, role="primary" if index == 0 else "alternative")
               for index, candidate in enumerate(candidates)]
    primary = matches[0] if matches and matches[0]["confidence"] >= 0.65 else None
    alternatives = matches[1:] if primary else matches
    terminology_mismatch = _has_whether_wh_mismatch(text, candidates[0] if candidates else None)
    return {
        "primary": primary,
        "atomic_kcs": atomic_kcs,
        "alternatives": alternatives,
        "needs_review": primary is None
        or primary["confidence"] < 0.85
        or terminology_mismatch,
        "matcher_version": MATCHER_VERSION,
    }


async def find_can_do_for_query(
    db: AsyncSession, payload: FindCanDoForQueryInput
) -> dict[str, Any]:
    text = " ".join([payload.query, *payload.conversation_context])
    candidates = await _rank_candidates(db, text, payload.top_k)
    atomic = _atomic_kcs(text, _suggested_correction(text))
    matches = [
        {
            "can_do_id": _can_do_id(candidate.profile, candidate.point),
            "knowledge_point_id": str(candidate.point.id),
            "confidence": candidate.score,
            "reason": candidate.reason,
        }
        for candidate in candidates
        if candidate.score >= 0.35
    ]
    return {
        "intent": _query_intent(payload.query),
        "matches": matches,
        "atomic_kcs": [item["id"] for item in atomic],
        "evidence": [item["evidence"] for item in atomic],
        "recommended_response_level": payload.user_level or "A2",
        "clarification_required": not matches or matches[0]["confidence"] < 0.65,
        "matcher_version": MATCHER_VERSION,
    }


def analyze_learner_response(payload: AnalyzeLearnerResponseInput) -> dict[str, Any]:
    expected = _normalize(payload.expected_answer)
    learner = _normalize(payload.learner_answer)
    atomic = _atomic_kcs(payload.learner_answer, payload.expected_answer)
    if learner in _NO_ATTEMPT:
        outcome: LearningOutcome = "NO_ATTEMPT"
        confidence = 0.99
        reason = "learner_did_not_attempt_target_structure"
    elif learner == expected:
        outcome = "SUCCESS"
        confidence = 1.0
        reason = "answer_matches_reference"
    elif atomic:
        outcome = "UNSUCCESSFUL"
        confidence = max(item["confidence"] for item in atomic)
        reason = "target_structure_was_attempted_but_contains_a_target_error"
    elif _target_structure_preserved(payload.expected_answer, payload.learner_answer):
        outcome = "UNRELATED_ERROR"
        confidence = 0.86
        reason = "target_structure_is_correct_but_other_text_differs"
    else:
        similarity = SequenceMatcher(None, expected, learner).ratio()
        outcome = "UNSUCCESSFUL" if similarity >= 0.45 else "NO_ATTEMPT"
        confidence = round(max(0.65, similarity), 3)
        reason = (
            "answer_differs_in_or_near_target_structure"
            if outcome == "UNSUCCESSFUL"
            else "answer_avoids_target_structure"
        )
    ids = list(dict.fromkeys([*payload.linked_can_do_ids, *(item["id"] for item in atomic)]))
    observations = [
        {
            "knowledge_id": knowledge_id,
            "outcome": outcome,
            "confidence": confidence,
            "evidence": {
                "question_id": payload.question_id,
                "learner_answer": payload.learner_answer,
                "expected_answer": payload.expected_answer,
                "reason": reason,
                "spans": [item["evidence"] for item in atomic],
            },
        }
        for knowledge_id in ids
    ]
    return {
        "overall_outcome": outcome,
        "confidence": confidence,
        "reason": reason,
        "observations": observations,
        "atomic_kcs": atomic,
        "analyzer_version": ANALYZER_VERSION,
    }


async def get_learner_knowledge_state(
    db: AsyncSession,
    learner_id: uuid.UUID,
    payload: GetLearnerKnowledgeStateInput,
) -> dict[str, Any]:
    points = await _resolve_points(db, payload.knowledge_ids)
    now = datetime.now(timezone.utc)
    states: list[dict[str, Any]] = []
    for requested_id in payload.knowledge_ids:
        point = points.get(requested_id)
        if point is None:
            states.append({"knowledge_id": requested_id, "status": "not_found"})
            continue
        state_result = await db.execute(
            select(LearnerKnowledgeState).where(
                LearnerKnowledgeState.learner_id == learner_id,
                LearnerKnowledgeState.knowledge_point_id == point.id,
            )
        )
        state = state_result.scalar_one_or_none()
        fsrs_result = await db.execute(
            select(FSRSReviewState).where(
                FSRSReviewState.learner_id == learner_id,
                FSRSReviewState.knowledge_point_id == point.id,
            )
        )
        fsrs = fsrs_result.scalar_one_or_none()
        evidence_result = await db.execute(
            select(AssessmentEvidence)
            .where(
                AssessmentEvidence.learner_id == learner_id,
                AssessmentEvidence.knowledge_point_id == point.id,
                AssessmentEvidence.invalidated_at.is_(None),
            )
            .order_by(AssessmentEvidence.created_at.desc())
            .limit(payload.recent_evidence_limit)
        )
        evidence = list(evidence_result.scalars().all())
        current_retrievability = (
            retrievability(
                FSRSState(
                    difficulty=fsrs.difficulty,
                    stability_days=fsrs.stability_days,
                    last_review_at=fsrs.last_review_at,
                    next_review_at=fsrs.next_review_at,
                    review_count=fsrs.review_count,
                ),
                now,
            )
            if fsrs
            else None
        )
        error_counts: dict[str, int] = {}
        for row in evidence:
            for tag in row.error_tags or []:
                error_counts[tag] = error_counts.get(tag, 0) + 1
        states.append(
            {
                "knowledge_id": requested_id,
                "knowledge_point_id": str(point.id),
                "canonical_key": point.canonical_key,
                "title": point.title,
                "status": state.status if state else "not_started",
                "dkt_mastery_probability": state.dkt_shadow_prediction if state else None,
                "irt_ability": float(state.ability or state.mastery_score) if state else 0.0,
                "predicted_success": state.predicted_success if state else None,
                "confidence": float(state.confidence) if state else 0.0,
                "retrievability": current_retrievability,
                "due_for_review": bool(
                    (fsrs and fsrs.next_review_at <= now)
                    or (state and state.next_review_at and state.next_review_at <= now)
                ),
                "next_review_at": (
                    fsrs.next_review_at.isoformat()
                    if fsrs
                    else state.next_review_at.isoformat()
                    if state and state.next_review_at
                    else None
                ),
                "common_errors": [
                    {"tag": tag, "count": count}
                    for tag, count in sorted(error_counts.items(), key=lambda item: -item[1])
                ],
                "recent_evidence": [
                    {
                        "evidence_id": str(row.id),
                        "outcome_score": row.outcome_score,
                        "confidence": row.semantic_confidence,
                        "evidence_mode": row.evidence_mode,
                        "evidence_ref": row.evidence_ref,
                        "occurred_at": row.created_at.isoformat() if row.created_at else None,
                    }
                    for row in evidence
                ],
                "state_model_version": state.state_model_version if state else None,
            }
        )
    return {"learner_id": str(learner_id), "states": states, "as_of": now.isoformat()}


async def record_learning_evidence(
    db: AsyncSession,
    learner_id: uuid.UUID,
    payload: RecordLearningEvidenceInput,
) -> dict[str, Any]:
    existing_result = await db.execute(
        select(LearningEvidenceEvent).where(
            LearningEvidenceEvent.learner_id == learner_id,
            LearningEvidenceEvent.event_id == payload.event_id,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if payload.operation == "revoke":
        if existing is None:
            raise ValueError("learning evidence event not found")
        return await _revoke_event(db, existing, payload.reason or "revoked")
    if existing is not None:
        return {**dict(existing.result or {}), "idempotent_replay": True}

    event = LearningEvidenceEvent(
        learner_id=learner_id,
        event_id=payload.event_id,
        source=payload.source,
        question_id=payload.question_id,
        observations=[item.model_dump(mode="json") for item in payload.observations],
        raw_evidence=payload.raw_evidence,
        matcher_model_version=MATCHER_VERSION,
        status="processing",
        result={},
    )
    db.add(event)
    await db.flush()
    points = await _resolve_points(db, [item.knowledge_id for item in payload.observations])
    observation_results: list[dict[str, Any]] = []
    for index, observation in enumerate(payload.observations):
        point = points.get(observation.knowledge_id)
        if point is None:
            observation_results.append(
                {
                    "knowledge_id": observation.knowledge_id,
                    "status": "not_applied",
                    "reason": "knowledge_item_not_found",
                }
            )
            continue
        score = _outcome_score(observation.outcome)
        attempt = ExerciseAttempt(
            learner_id=learner_id,
            question_id=None,
            submitted_answer=str(observation.evidence.get("learner_answer", "")),
            correct=score >= 0.6,
            response_time_ms=None,
            exercise_id=f"agent-tool:{payload.event_id}:{index}",
            target_type="knowledge_point",
            target_id=str(point.id),
            target_label=point.title,
            answer=str(observation.evidence.get("expected_answer", "")),
            result="correct" if score >= 0.6 else "incorrect",
            metadata_={
                "source": payload.source,
                "agent_event_id": payload.event_id,
                "outcome": observation.outcome,
                "raw_evidence": observation.evidence,
            },
            source_context={"agent_learning_evidence_event_id": str(event.id)},
            should_update_mastery=True,
            should_create_error_pattern=observation.outcome == "UNSUCCESSFUL",
            should_create_memory_evidence=True,
        )
        db.add(attempt)
        await db.flush()
        result = await MasteryEngine(db).update_from_attempt(
            AttemptSignal(
                learner_id=str(learner_id),
                target_type="knowledge_point",
                target_id=str(point.id),
                correct=score >= 0.6,
                score=score,
                error_type=_error_type(observation),
                source=payload.source,
                metadata={
                    "attempt_id": str(attempt.id),
                    "question_id": payload.question_id,
                    "evidence_mode": observation.evidence_mode,
                    "semantic_confidence": observation.confidence,
                    "item_difficulty_prior": observation.item_difficulty_prior,
                    "interaction_type": "assessment",
                    "agent_event_id": payload.event_id,
                },
            )
        )
        update_blocked = bool(result.metadata.get("update_blocked"))
        observation_results.append(
            {
                "knowledge_id": observation.knowledge_id,
                "knowledge_point_id": str(point.id),
                "status": "review_required" if update_blocked else "applied",
                "outcome": observation.outcome,
                "attempt_id": str(attempt.id),
                "evidence_id": result.metadata.get("evidence_id"),
                "mastery_before": result.previous_score,
                "mastery_after": result.new_score,
                "state_model_version": "irt-1pl-v1",
                "reason": result.metadata.get("reason") if update_blocked else None,
            }
        )
    applied = sum(item["status"] == "applied" for item in observation_results)
    event.status = "applied" if applied == len(observation_results) else "partial" if applied else "no_updates"
    event.result = {
        "event_id": payload.event_id,
        "status": event.status,
        "matcher_model_version": MATCHER_VERSION,
        "observation_results": observation_results,
        "idempotent_replay": False,
    }
    await db.flush()
    return dict(event.result)


async def _revoke_event(
    db: AsyncSession, event: LearningEvidenceEvent, reason: str
) -> dict[str, Any]:
    from src.adaptive.correction import EvidenceCorrectionService

    if event.revoked_at is not None:
        return {**dict(event.result or {}), "revoked": True, "idempotent_replay": True}
    revoked: list[dict[str, Any]] = []
    for item in (event.result or {}).get("observation_results", []):
        raw_id = item.get("evidence_id")
        if not raw_id:
            continue
        correction = await EvidenceCorrectionService(db).invalidate_and_recompute(
            uuid.UUID(raw_id), reason=reason
        )
        revoked.append(
            {
                "evidence_id": str(correction.evidence_id),
                "mastery_after_replay": correction.mastery,
                "replayed_evidence_count": correction.replayed_evidence_count,
            }
        )
    event.revoked_at = datetime.now(timezone.utc)
    event.revoke_reason = reason
    event.status = "revoked"
    event.result = {**dict(event.result or {}), "status": "revoked", "revoked": revoked}
    await db.flush()
    return {**dict(event.result), "idempotent_replay": False}


async def _rank_candidates(db: AsyncSession, text: str, top_k: int) -> list[_Candidate]:
    result = await db.execute(
        select(GrammarCanDoProfile, KnowledgePoint)
        .join(KnowledgePoint, KnowledgePoint.id == GrammarCanDoProfile.knowledge_point_id)
        .where(KnowledgePoint.status == "published")
    )
    ranked = [
        candidate
        for profile, point in result.all()
        if (candidate := _score_candidate(text, profile, point)).score > 0
    ]
    ranked.sort(key=lambda item: (-item.score, item.profile.external_id or 0, str(item.point.id)))
    return ranked[:top_k]


def _score_candidate(
    text: str, profile: GrammarCanDoProfile, point: KnowledgePoint
) -> _Candidate:
    query_tokens = set(_tokens(text))
    searchable = " ".join(
        str(value or "")
        for value in (
            profile.can_do_statement,
            profile.guideword,
            profile.lexical_range,
            profile.category,
            profile.subcategory,
            point.title,
            " ".join(profile.positive_examples or []),
        )
    )
    candidate_tokens = set(_tokens(searchable))
    overlap = query_tokens & candidate_tokens
    lexical = len(overlap) / max(3, min(len(query_tokens), 18))
    lower = text.lower()
    statement = profile.can_do_statement.lower()
    bonuses: list[tuple[float, str]] = []
    if "wonder" in lower and "wonder" in statement:
        bonuses.append((0.38, "matched reporting verb 'wonder'"))
    if any(word in lower for word in ("whether", " if ")) and any(
        word in statement for word in ("whether", "if")
    ):
        bonuses.append((0.24, "matched whether/if subordinate-clause form"))
    if re.search(r"\b(what|who|where|when|why|how)\b", lower) and "wh-" in statement:
        bonuses.append((0.24, "matched wh-clause form"))
    if _contains_reported_question(lower) and "report" in statement:
        bonuses.append((0.16, "matched reported-question context"))
    if _contains_backshift(lower) and any(word in statement for word in ("tense shift", "reported")):
        bonuses.append((0.16, "matched tense-backshift evidence"))
    if "whether" in lower and "'wh-'word" in statement and "whether" not in statement:
        bonuses.append((-0.12, "terminology mismatch: whether versus wh-word"))
    raw = 0.18 + lexical * 0.9 + sum(value for value, _ in bonuses)
    score = round(min(0.99, max(0.0, raw)), 3)
    evidence_terms = sorted(overlap, key=lambda item: (-len(item), item))[:6]
    reasons = [reason for _, reason in bonuses if not reason.startswith("terminology")]
    if evidence_terms:
        reasons.append(f"lexical evidence: {', '.join(evidence_terms)}")
    mismatch = [reason for _, reason in bonuses if reason.startswith("terminology")]
    return _Candidate(profile, point, score, "; ".join([*reasons, *mismatch]) or "weak lexical match")


async def _resolve_points(
    db: AsyncSession, knowledge_ids: list[str]
) -> dict[str, KnowledgePoint]:
    uuid_values = [_safe_uuid(value.removeprefix("egp:")) for value in knowledge_ids]
    point_uuids = [value for value in uuid_values if value is not None]
    external_ids = [
        int(value.removeprefix("egp:"))
        for value in knowledge_ids
        if value.startswith("egp:") and value.removeprefix("egp:").isdigit()
    ]
    conditions = [KnowledgePoint.canonical_key.in_(knowledge_ids)]
    if point_uuids:
        conditions.append(KnowledgePoint.id.in_(point_uuids))
    if external_ids:
        conditions.append(GrammarCanDoProfile.external_id.in_(external_ids))
    result = await db.execute(
        select(KnowledgePoint, GrammarCanDoProfile)
        .outerjoin(GrammarCanDoProfile, GrammarCanDoProfile.knowledge_point_id == KnowledgePoint.id)
        .where(or_(*conditions), KnowledgePoint.status == "published")
    )
    resolved: dict[str, KnowledgePoint] = {}
    for point, profile in result.all():
        aliases = {str(point.id), point.canonical_key}
        if profile and profile.external_id is not None:
            aliases.add(f"egp:{profile.external_id}")
        for requested in knowledge_ids:
            if requested in aliases:
                resolved[requested] = point
    return resolved


def _candidate_payload(candidate: _Candidate, *, role: str) -> dict[str, Any]:
    return {
        "id": _can_do_id(candidate.profile, candidate.point),
        "knowledge_point_id": str(candidate.point.id),
        "statement": candidate.profile.can_do_statement,
        "cefr_level": candidate.profile.cefr_level,
        "confidence": candidate.score,
        "role": role,
        "reason": candidate.reason,
    }


def _can_do_id(profile: GrammarCanDoProfile, point: KnowledgePoint) -> str:
    return f"egp:{profile.external_id}" if profile.external_id is not None else str(point.id)


def _atomic_kcs(incorrect: str, correct: str) -> list[dict[str, Any]]:
    before, after = incorrect.lower(), correct.lower()
    results: list[dict[str, Any]] = []
    inversion = re.search(
        r"\b(?:whether|if|what|who|where|when|why|how)\s+(will|would|can|could|do|does|did|is|are|was|were)\s+([a-z]+)",
        before,
    )
    if inversion and not re.search(
        rf"\b(?:whether|if|what|who|where|when|why|how)\s+{re.escape(inversion.group(1))}\s+{re.escape(inversion.group(2))}\b",
        after,
    ):
        corrected = _first_embedded_clause(after)
        results.append(
            {
                "id": "grammar.reported_question.word_order",
                "label": "间接疑问句使用陈述语序",
                "confidence": 0.98,
                "evidence": {"incorrect": inversion.group(0), "correct": corrected},
            }
        )
    for source, target in (("will", "would"), ("can", "could"), ("may", "might")):
        if re.search(rf"\b{source}\b", before) and re.search(rf"\b{target}\b", after):
            results.append(
                {
                    "id": "grammar.reported_speech.backshift",
                    "label": "间接引语中的时态后移",
                    "confidence": 0.93,
                    "evidence": {"incorrect": source, "correct": target},
                }
            )
            break
    if re.search(r"\bdo\s+(?:a|the)\s+decision\b", before) and re.search(
        r"\bmake\s+(?:a|the)\s+decision\b", after
    ):
        results.append(
            {
                "id": "vocabulary.collocation.make_a_decision",
                "label": "make a decision 搭配",
                "confidence": 0.99,
                "evidence": {"incorrect": "do a decision", "correct": "make a decision"},
            }
        )
    return results


def _target_structure_preserved(expected: str, learner: str) -> bool:
    expected_lower, learner_lower = expected.lower(), learner.lower()
    signatures = [
        r"\b(?:whether|if)\s+(?:the\s+)?[a-z]+\s+(?:would|could|might|was|were|had)\b",
        r"\bmake\s+(?:a|the)\s+decision\b",
    ]
    present = [pattern for pattern in signatures if re.search(pattern, expected_lower)]
    return bool(present) and all(re.search(pattern, learner_lower) for pattern in present)


def _suggested_correction(text: str) -> str:
    backshifts = {"will": "would", "can": "could", "may": "might"}
    corrected = re.sub(
        r"\b(whether|if)\s+(will|can|may)\s+(the\s+\w+|he|she|it|they|we|you|i)\s+(\w+)",
        lambda match: (
            f"{match.group(1)} {match.group(3)} "
            f"{backshifts[match.group(2).lower()]} {match.group(4)}"
        ),
        text,
        flags=re.IGNORECASE,
    )
    return corrected


def _first_embedded_clause(text: str) -> str:
    match = re.search(r"\b(?:whether|if|what|who|where|when|why|how)\b[^,.?!]*", text)
    return match.group(0).strip() if match else text.strip()


def _has_whether_wh_mismatch(text: str, candidate: _Candidate | None) -> bool:
    return bool(
        candidate
        and "whether" in text.lower()
        and "'wh-'word" in candidate.profile.can_do_statement.lower()
        and "whether" not in candidate.profile.can_do_statement.lower()
    )


def _query_intent(query: str) -> str:
    lower = query.lower()
    if any(token in lower for token in ("为什么", "grammar", "语法", "whether", "时态")):
        return "grammar_question"
    if any(token in lower for token in ("单词", "词", "collocation", "搭配")):
        return "vocabulary_question"
    return "learning_question"


def _contains_reported_question(text: str) -> bool:
    return bool(
        re.search(r"\b(?:ask(?:ed)?|wonder(?:ed|ing)?)\b", text)
        and re.search(r"\b(?:whether|if|what|who|where|when|why|how)\b", text)
    )


def _contains_backshift(text: str) -> bool:
    return bool(re.search(r"\b(?:would|could|might|had)\b", text))


def _outcome_score(outcome: LearningOutcome) -> float:
    return 1.0 if outcome in {"SUCCESS", "UNRELATED_ERROR"} else 0.0


def _error_type(observation: LearningObservationInput) -> str | None:
    if observation.outcome in {"SUCCESS", "UNRELATED_ERROR"}:
        return None
    return observation.knowledge_id[:160]


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split()).rstrip(".?!。？！")


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text) if len(token) > 1]


def _safe_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        return None


def tool_input_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return strict-enough JSON schema for the execution gateway."""
    schema = model.model_json_schema()
    schema["additionalProperties"] = False
    return schema
