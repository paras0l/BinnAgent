import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.vocabulary_agent import VocabularyAgentService, should_trigger_vocabulary_agent
from src.models.vocabulary import VocabularyItem
from src.providers.base import ChatResponse as ModelChatResponse


@pytest.fixture
def mock_db():
    db = MagicMock(spec=AsyncSession)
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def mock_router():
    router = MagicMock()
    router.chat = AsyncMock()
    return router


def _none_result():
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    return result


class TestVocabularyAgentService:
    @pytest.mark.asyncio
    async def test_capture_chat_turn_saves_structured_high_confidence_card(
        self, mock_db, mock_router
    ):
        learner_id = uuid.uuid4()
        mock_db.execute = AsyncMock(return_value=_none_result())
        mock_router.chat.return_value = ModelChatResponse(
            provider="ollama",
            model="gemma4:e2b",
            content="",
            structured={
                "cards": [
                    {
                        "word": "significant",
                        "phonetic": "/sɪɡˈnɪfɪkənt/",
                        "definition_zh": "重要的；显著的",
                        "definition_en": "important or noticeable",
                        "collocations": [
                            {
                                "phrase": "significant impact",
                                "translation_zh": "重大影响",
                            }
                        ],
                        "examples": [
                            {
                                "sentence": "The policy had a significant impact.",
                                "translation_zh": "这项政策产生了重大影响。",
                            }
                        ],
                        "memory_tip": "常用于写作表达影响很大。",
                        "exam_level": "CET-4",
                        "confidence": 0.92,
                    }
                ]
            },
        )

        result = await VocabularyAgentService(mock_db, mock_router).capture_chat_turn(
            learner_id=learner_id,
            user_message="讲解 significant",
            assistant_reply="significant means important.",
            source_ref="conversation_message:1",
        )

        assert result.saved_count == 1
        added_item = mock_db.add.call_args.args[0]
        assert isinstance(added_item, VocabularyItem)
        assert added_item.word == "significant"
        assert added_item.meanings == [
            {
                "definition_zh": "重要的；显著的",
                "definition_en": "important or noticeable",
                "source": "vocabulary_agent",
            }
        ]
        assert added_item.examples == [
            {
                "sentence": "The policy had a significant impact.",
                "translation_zh": "这项政策产生了重大影响。",
            }
        ]
        request = mock_router.chat.await_args.args[0]
        assert request.task_type == "vocabulary_agent_extract"
        assert request.response_schema
        assert request.preferred_model == "gemma4:e2b"

    @pytest.mark.asyncio
    async def test_capture_chat_turn_skips_low_quality_cards(self, mock_db, mock_router):
        mock_router.chat.return_value = ModelChatResponse(
            provider="ollama",
            model="gemma4:e2b",
            content="",
            structured={
                "cards": [
                    {
                        "word": "definition",
                        "phonetic": "/ˌdefɪˈnɪʃn/",
                        "definition_zh": "释义",
                        "definition_en": "definition",
                        "examples": [
                            {"sentence": "Definition is a label.", "translation_zh": "这是标签。"}
                        ],
                        "confidence": 0.99,
                    },
                    {
                        "word": "sustainable",
                        "phonetic": "/səˈsteɪnəbl/",
                        "definition_zh": "可持续的",
                        "definition_en": "able to continue",
                        "examples": [],
                        "confidence": 0.95,
                    },
                    {
                        "word": "prosperity",
                        "phonetic": "/prɒˈsperəti/",
                        "definition_zh": "繁荣",
                        "definition_en": "success",
                        "examples": [
                            {"sentence": "People seek prosperity.", "translation_zh": "人们追求繁荣。"}
                        ],
                        "confidence": 0.6,
                    },
                ]
            },
        )

        result = await VocabularyAgentService(mock_db, mock_router).capture_chat_turn(
            learner_id=uuid.uuid4(),
            user_message="讲解词汇",
            assistant_reply="...",
            source_ref=None,
        )

        assert result.saved_count == 0
        assert result.skipped_count == 3
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_capture_chat_turn_skips_card_without_phonetic(self, mock_db, mock_router):
        mock_router.chat.return_value = ModelChatResponse(
            provider="ollama",
            model="gemma4:e2b",
            content="",
            structured={
                "cards": [
                    {
                        "word": "significant",
                        "definition_zh": "重要的；显著的",
                        "definition_en": "important or noticeable",
                        "examples": [
                            {
                                "sentence": "The result is significant.",
                                "translation_zh": "这个结果很重要。",
                            }
                        ],
                        "confidence": 0.95,
                    }
                ]
            },
        )

        result = await VocabularyAgentService(mock_db, mock_router).capture_chat_turn(
            learner_id=uuid.uuid4(),
            user_message="讲解 significant",
            assistant_reply="...",
            source_ref=None,
        )

        assert result.saved_count == 0
        assert result.skipped_count == 1
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_capture_chat_turn_handles_invalid_json_without_raising(self, mock_db, mock_router):
        mock_router.chat.return_value = ModelChatResponse(
            provider="ollama",
            model="gemma4:e2b",
            content="not-json",
        )

        result = await VocabularyAgentService(mock_db, mock_router).capture_chat_turn(
            learner_id=uuid.uuid4(),
            user_message="讲解词汇",
            assistant_reply="...",
            source_ref=None,
        )

        assert result.failed is True
        mock_db.add.assert_not_called()


def test_should_trigger_vocabulary_agent_only_for_vocabulary_skill():
    assert should_trigger_vocabulary_agent(user_message="anything", skill_focus="vocabulary")
    assert should_trigger_vocabulary_agent(user_message="请作为 CET 词汇教练", skill_focus=None)
    assert not should_trigger_vocabulary_agent(user_message="请批改作文", skill_focus="writing")
