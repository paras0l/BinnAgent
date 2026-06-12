from dataclasses import dataclass, field
from typing import Optional

from src.providers.base import ChatRequest
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

    async def score(self, text: str, prompt: Optional[str] = None) -> EssayScoringResult:
        word_count = len(text.split())

        if word_count < 10:
            return EssayScoringResult(
                score=0.0,
                max_score=25.0,
                key_issues=["Text too short to evaluate"],
                error_patterns=[],
            )

        return await self._score_via_llm(text, prompt)

    async def _score_via_llm(self, text: str, prompt: Optional[str] = None) -> EssayScoringResult:
        import json as _json

        word_count = len(text.split())
        context = f"写作题目: {prompt}\n\n" if prompt else ""
        user_msg = (
            f"{context}请对以下英语作文进行评分和反馈。\n\n"
            f"作文内容:\n{text}\n\n"
            "请用JSON格式回复，包含: "
            '{"score": 0-25的分数, "strengths": ["优点"], '
            '"key_issues": ["需要改进的地方"], '
            '"sentence_feedback": [{"sentence": "原句", "feedback": "反馈"}]}'
        )

        try:
            response = await router.chat(
                ChatRequest(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "你是一位专业的英语作文评分老师，熟悉CET-4和CET-6写作评分标准。"
                                "请从词汇、语法、结构、内容四个方面评分，总分25分。"
                                "请用JSON格式回复。"
                            ),
                        },
                        {"role": "user", "content": user_msg},
                    ],
                    task_type="essay_scoring",
                    temperature=0.3,
                    max_tokens=1024,
                )
            )
            content = response.content

            parsed = _json.loads(content)
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
