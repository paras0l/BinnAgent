import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.memory.retriever import MemoryRetriever
from src.memory.schemas import MemoryEventInput
from src.memory.writer import MemoryWriter
from src.models.learner import Learner
from src.tools.essay_scoring import essay_scorer

router = APIRouter(prefix="/api/learners/{learner_id}/essay-review", tags=["essay-review"])


class EssayReviewRequest(BaseModel):
    text: str = Field(min_length=10, max_length=8000)
    prompt: str | None = Field(default=None, max_length=1000)


class EssayReviewResponse(BaseModel):
    score: float
    max_score: float
    strengths: list[str]
    key_issues: list[str]
    sentence_feedback: list[dict]
    historical_weaknesses: list[dict]
    improvement_notes: list[str]
    memory_context: dict


@router.post("", response_model=EssayReviewResponse)
async def review_essay(
    learner_id: uuid.UUID,
    body: EssayReviewRequest,
    db: AsyncSession = Depends(get_db_session),
) -> EssayReviewResponse:
    learner_result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if learner_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")

    context = await MemoryRetriever(db).for_essay_review(
        learner_id=learner_id,
        limit=6,
    )
    historical_weaknesses = [
        {
            "id": item.id,
            "summary": item.summary,
            "confidence": item.confidence,
            "evidence": item.evidence_refs,
        }
        for item in context.loaded_items
    ]
    prompt = _prompt_with_memory(body.prompt, historical_weaknesses)
    result = await essay_scorer.score(body.text, prompt=prompt)

    now = datetime.now(timezone.utc)
    writer = MemoryWriter(db)
    submitted = await writer.record_event(
        MemoryEventInput(
            learner_id=learner_id,
            event_type="essay_submitted",
            skill="writing",
            subskill="essay",
            source_type="essay_review",
            payload={"prompt": body.prompt, "word_count": len(body.text.split())},
            confidence=1.0,
            occurred_at=now,
            created_by="user",
        )
    )
    await writer.record_event(
        MemoryEventInput(
            learner_id=learner_id,
            event_type="essay_feedback_received",
            skill="writing",
            subskill="essay",
            source_type="essay_review",
            source_id=str(submitted.id),
            payload={
                "score": result.score,
                "max_score": result.max_score,
                "strengths": result.strengths,
                "key_issues": result.key_issues,
                "historical_weaknesses": historical_weaknesses,
            },
            confidence=0.9,
            occurred_at=now,
        )
    )
    for issue in result.key_issues[:3]:
        await writer.record_event(
            MemoryEventInput(
                learner_id=learner_id,
                event_type="chat_error_observed",
                skill="writing",
                subskill="essay",
                source_type="essay_review",
                source_id=str(submitted.id),
                payload={
                    "pattern": _issue_pattern(issue),
                    "description": issue,
                    "source_score": result.score,
                },
                confidence=0.7,
                occurred_at=now,
            )
        )
    await db.flush()

    return EssayReviewResponse(
        score=result.score,
        max_score=result.max_score,
        strengths=result.strengths,
        key_issues=result.key_issues,
        sentence_feedback=result.sentence_feedback,
        historical_weaknesses=historical_weaknesses,
        improvement_notes=_improvement_notes(result.key_issues, historical_weaknesses),
        memory_context={
            "loaded_items": [item.id for item in context.loaded_items],
            "loaded_item_layers": [item.layer for item in context.loaded_items],
            "context_layer": context.layer,
            "excluded_items": context.excluded_items,
            "retrieval_reason": context.retrieval_reason,
        },
    )


def _prompt_with_memory(prompt: str | None, weaknesses: list[dict]) -> str | None:
    if not weaknesses:
        return prompt
    memory_text = "历史写作记忆：" + "；".join(str(item["summary"]) for item in weaknesses[:3])
    return f"{prompt or ''}\n{memory_text}".strip()


def _issue_pattern(issue: str) -> str:
    lowered = issue.lower()
    if "article" in lowered or "冠词" in issue:
        return "missing_articles"
    if "transition" in lowered or "连接" in issue or "递进" in issue:
        return "weak_transition"
    if "tense" in lowered or "时态" in issue:
        return "tense_confusion"
    if "spelling" in lowered or "拼写" in issue:
        return "spelling_error"
    return "essay_issue"


def _improvement_notes(key_issues: list[str], weaknesses: list[dict]) -> list[str]:
    if not weaknesses:
        return ["本次批改已建立写作记忆，后续会对比是否复发或改善。"]
    notes: list[str] = []
    issue_text = " ".join(key_issues).lower()
    for weakness in weaknesses[:3]:
        summary = str(weakness.get("summary", ""))
        status = "仍需关注" if any(token in issue_text for token in summary.lower().split()[:3]) else "本次可对照观察"
        notes.append(f"{status}：{summary}")
    return notes
