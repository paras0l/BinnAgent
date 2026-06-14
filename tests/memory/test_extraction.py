import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.memory.extraction import MemoryExtractionService
from src.models.error_pattern import ErrorPattern
from src.models.session import LearningSession


@pytest.fixture
def mock_db():
    db = MagicMock(spec=AsyncSession)
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


def _one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


class TestMemoryExtractionService:
    @pytest.mark.asyncio
    async def test_chat_vocabulary_learning_creates_recent_session_without_vocab_write(self, mock_db):
        learner_id = uuid.uuid4()
        thread_id = uuid.uuid4()
        message_id = uuid.uuid4()
        mock_db.execute = AsyncMock(return_value=_one(None))

        result = await MemoryExtractionService(mock_db).capture_chat_turn(
            learner_id=learner_id,
            user_message="讲解 significant 这个单词的意思",
            assistant_reply="significant: important or large enough to be noticed",
            thread_id=thread_id,
            assistant_message_id=message_id,
        )

        added = [call.args[0] for call in mock_db.add.call_args_list]
        assert result.session_created is True
        assert any(
            isinstance(obj, LearningSession) and obj.session_type == "chat_learning"
            for obj in added
        )

    @pytest.mark.asyncio
    async def test_chat_casual_message_does_not_write_memory(self, mock_db):
        result = await MemoryExtractionService(mock_db).capture_chat_turn(
            learner_id=uuid.uuid4(),
            user_message="你好呀",
            assistant_reply="你好，今天想学点什么？",
        )

        assert result.error_count == 0
        assert result.session_created is False
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_chat_evaluable_writing_records_error_pattern(self, mock_db):
        mock_db.execute = AsyncMock(return_value=_one(None))

        result = await MemoryExtractionService(mock_db).capture_chat_turn(
            learner_id=uuid.uuid4(),
            user_message=(
                "请批改作文: I go to school yesterday and I think environment protection "
                "is important for every students in modern society."
            ),
            assistant_reply="主要问题：时态需要统一，另外存在主谓一致错误。",
            skill_focus="writing",
        )

        added = [call.args[0] for call in mock_db.add.call_args_list]
        assert result.error_count == 2
        assert any(
            isinstance(obj, ErrorPattern) and obj.pattern == "tense_confusion"
            for obj in added
        )
        assert any(
            isinstance(obj, ErrorPattern) and obj.pattern == "subject_verb_agreement"
            for obj in added
        )

    @pytest.mark.asyncio
    async def test_session_result_records_vocab_list_and_feedback_errors(self, mock_db):
        mock_db.execute = AsyncMock(return_value=_one(None))

        result = await MemoryExtractionService(mock_db).capture_session_result(
            learner_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            result={
                "active_skill": "vocabulary",
                "input_materials": [
                    {
                        "type": "vocabulary_list",
                        "words": [
                            {
                                "word": "sustainable",
                                "definition": "able to continue over time",
                            }
                        ],
                    }
                ],
                "agent_feedback": {"key_issues": ["注意 collocation 搭配"]},
            },
        )

        added = [call.args[0] for call in mock_db.add.call_args_list]
        assert result.error_count == 1
        assert any(isinstance(obj, ErrorPattern) and obj.pattern == "word_choice" for obj in added)
