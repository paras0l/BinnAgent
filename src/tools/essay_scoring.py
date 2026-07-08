import uuid
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.prompts import PromptExecutionContext, PromptExecutor
from src.providers.router import router


@dataclass
class EssayScoringResult:
    score: float
    max_score: float
    strengths: list[str] = field(default_factory=list)
    key_issues: list[str] = field(default_factory=list)
    sentence_feedback: list[dict] = field(default_factory=list)
    error_patterns: list[dict] = field(default_factory=list)


class EssayScoringTool:
    MAX_WORDS = 300
    MIN_WORDS = 80

    async def score(
        self,
        text: str,
        prompt: Optional[str] = None,
        *,
        db: AsyncSession | None = None,
        learner_id: uuid.UUID | None = None,
    ) -> EssayScoringResult:
        word_count = len(text.split())

        if word_count < 10:
            return EssayScoringResult(
                score=0.0,
                max_score=25.0,
                key_issues=["Text too short to evaluate"],
                error_patterns=[],
            )

        return await self._score_via_llm(text, prompt, db=db, learner_id=learner_id)

    async def _score_via_llm(
        self,
        text: str,
        prompt: Optional[str] = None,
        *,
        db: AsyncSession | None = None,
        learner_id: uuid.UUID | None = None,
    ) -> EssayScoringResult:
        word_count = len(text.split())

        try:
            result = await PromptExecutor(db=db, model_router=router).execute(
                prompt_id="essay.scoring",
                variables={
                    "prompt_context": f"写作题目: {prompt}\n\n" if prompt else "",
                    "essay_text": text,
                },
                context=PromptExecutionContext(
                    learner_id=learner_id,
                    source_module="tools.essay_scoring",
                    task_id="essay_scoring",
                    target_type="essay",
                ),
                request_overrides={"task_type": "essay_scoring"},
            )
            if result.decision != "accepted" or result.validated_output is None:
                raise ValueError("essay scoring output was not accepted")
            parsed = result.validated_output
            score = float(parsed.get("score", 10.0))
            score = max(0.0, min(25.0, score))

            return EssayScoringResult(
                score=score,
                max_score=25.0,
                strengths=parsed.get("strengths", []),
                key_issues=parsed.get("key_issues", []),
                sentence_feedback=parsed.get("sentence_feedback", []),
                error_patterns=[],
            )
        except Exception:
            ratio = (word_count - self.MIN_WORDS) / max(1, self.MAX_WORDS - self.MIN_WORDS)
            score = round(max(5.0, min(25.0, 10.0 + ratio * 15.0)), 1)
            return EssayScoringResult(
                score=score,
                max_score=25.0,
                strengths=["Meets minimum word count"] if word_count >= self.MIN_WORDS else [],
                key_issues=["Unable to perform detailed analysis"]
                if word_count < self.MIN_WORDS
                else [],
                error_patterns=[],
            )


essay_scorer = EssayScoringTool()
