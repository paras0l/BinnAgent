import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.vocabulary import (
    ReviewSchedule,
    VocabularyItem,
    VocabularyMasteryVector,
    VocabularyMistake,
    VocabularyPracticeSession,
)
from src.vocabulary.learning import canonical_vocabulary_key, record_attempt, spelling_feedback


def test_canonical_key_normalizes_case_spacing_and_smart_apostrophe() -> None:
    assert canonical_vocabulary_key("  What’s   this? ") == "what's this"


def test_spelling_feedback_reports_omission() -> None:
    error_type, diff, message = spelling_feedback("mornng", "morning")

    assert error_type == "omission"
    assert any(item == {"answer": None, "correct": "i", "status": "missing"} for item in diff)
    assert "i" in message


def test_spelling_feedback_reports_transposition() -> None:
    error_type, _, message = spelling_feedback("freind", "friend")

    assert error_type == "transposition"
    assert "顺序" in message


def test_spelling_feedback_accepts_exact_answer() -> None:
    error_type, diff, message = spelling_feedback("hello", "hello")

    assert error_type is None
    assert all(item["status"] == "match" for item in diff)
    assert message == "拼对了"


@pytest.mark.asyncio
async def test_record_attempt_updates_mastery_and_writes_mistake() -> None:
    learner_id = uuid.uuid4()
    item_id = uuid.uuid4()
    session_id = uuid.uuid4()
    item = VocabularyItem(
        learner_id=learner_id,
        word="friend",
        canonical_key="friend",
        entry_kind="word",
        status="learning",
        confidence=0.4,
        review_count=1,
    )
    item.id = item_id
    session = VocabularyPracticeSession(
        learner_id=learner_id,
        mode="spelling",
        prompt_mode="audio",
        accent="uk",
        status="in_progress",
        item_ids=[str(item_id)],
        current_index=0,
        correct_count=0,
        hinted_count=0,
        revealed_count=0,
        started_at=MagicMock(),
    )
    session.id = session_id
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = VocabularyMasteryVector(
        learner_id=learner_id,
        vocabulary_item_id=item_id,
        recognition=0.4,
        recall=0.4,
        spelling=0.4,
        listening=0.4,
        context_use=0.4,
        production=0.4,
    )
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    added: list[object] = []
    db.add = MagicMock(side_effect=added.append)

    attempt = await record_attempt(
        db,
        session=session,
        item=item,
        idempotency_key="attempt-1",
        drill_type="spelling",
        answer="freind",
        result="incorrect",
        score=0.0,
        error_type="transposition",
        letter_diff=[],
        response_time_ms=1200,
        hint_count=1,
        replay_count=2,
    )

    assert attempt.result == "incorrect"
    assert item.confidence == pytest.approx(0.28)
    assert any(isinstance(value, ReviewSchedule) for value in added)
    mistake = next(value for value in added if isinstance(value, VocabularyMistake))
    assert mistake.mistake_type == "transposition"
    assert mistake.correction == "friend"
