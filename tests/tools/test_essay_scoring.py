from unittest.mock import AsyncMock

import pytest

from src.providers.base import ChatResponse
from src.tools import essay_scoring
from src.tools.essay_scoring import EssayScoringResult, EssayScoringTool


class TestEssayScoringFallback:
    @pytest.mark.asyncio
    async def test_invalid_llm_json_uses_word_count_fallback(self, monkeypatch):
        tool = EssayScoringTool()
        text = " ".join(["learning"] * 120)
        mock_router = AsyncMock()
        mock_router.chat = AsyncMock(
            return_value=ChatResponse(provider="ollama", model="gemma4:e2b", content="not json")
        )
        monkeypatch.setattr(essay_scoring, "router", mock_router)

        result = await tool.score(text)

        assert isinstance(result, EssayScoringResult)
        assert 5.0 <= result.score <= 25.0
        assert result.strengths == ["Meets minimum word count"]
        assert result.error_patterns == []
        request = mock_router.chat.await_args.args[0]
        assert request.task_type == "essay_scoring"
        assert request.max_tokens == 1024

    @pytest.mark.asyncio
    async def test_too_short_text_returns_zero_without_llm(self):
        tool = EssayScoringTool()

        result = await tool.score("too short")

        assert result.score == 0.0
        assert result.key_issues == ["Text too short to evaluate"]
