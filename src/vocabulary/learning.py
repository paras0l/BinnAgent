import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.knowledge import CurriculumNode, KnowledgePoint, KnowledgeSource
from src.models.vocabulary import (
    ReviewSchedule,
    VocabularyAttempt,
    VocabularyItem,
    VocabularyItemSource,
    VocabularyMasteryVector,
    VocabularyMistake,
    VocabularyPracticeSession,
    VocabularyUserOverride,
)
from src.tools.free_dictionary import lookup_free_dictionary_batch


def canonical_vocabulary_key(value: str) -> str:
    value = value.casefold().replace("’", "'").strip()
    value = re.sub(r"[^a-z0-9'./ -]+", "", value)
    return re.sub(r"\s+", " ", value).strip(" .-/")


def source_label(source: KnowledgeSource, node: CurriculumNode) -> str:
    grade_label = {
        "grade-7": "七年级",
        "grade-8": "八年级",
        "grade-9": "九年级",
    }.get(source.grade, source.title)
    volume_label = "上" if source.volume == "upper" else "下" if source.volume == "lower" else ""
    volume = f"{grade_label}{volume_label}"
    unit = node.title.replace("Starter Unit", "SU").replace("Unit", "U").replace(" ", "")
    return f"{volume} · {unit}"


def _entry_kind(expression: str) -> str:
    if any(mark in expression for mark in ("?", "!", "...")):
        return "sentence_pattern"
    if len(expression) <= 8 and expression.replace(".", "").isupper():
        return "abbreviation"
    if " " in expression or "/" in expression:
        lower = expression.casefold()
        if lower.startswith(("be ", "look ", "make ", "take ", "get ", "have ")):
            return "collocation"
        return "phrase"
    if expression[:1].isupper():
        return "proper_noun"
    return "word"


@dataclass(frozen=True)
class EnrollmentResult:
    total: int
    newly_added: int
    source_linked: int
    already_known: int


async def enroll_unit_vocabulary(
    db: AsyncSession,
    learner_id: uuid.UUID,
    node: CurriculumNode,
) -> EnrollmentResult:
    source_result = await db.execute(
        select(KnowledgeSource).where(KnowledgeSource.id == node.source_id)
    )
    source = source_result.scalar_one()
    point_result = await db.execute(
        select(KnowledgePoint)
        .where(
            KnowledgePoint.curriculum_node_id == node.id,
            KnowledgePoint.type == "vocabulary",
            KnowledgePoint.status == "published",
        )
        .order_by(KnowledgePoint.content["unit_order"].as_integer().asc())
    )
    points = [
        point
        for point in point_result.scalars().all()
        if (point.content or {}).get("role") == "unit_wordlist"
    ]
    keys = [
        canonical_vocabulary_key((point.content or {}).get("lemma") or point.title)
        for point in points
    ]
    item_result = (
        await db.execute(
            select(VocabularyItem).where(
                VocabularyItem.learner_id == learner_id,
                VocabularyItem.canonical_key.in_(keys),
            )
        )
        if keys
        else None
    )
    items_by_key = {
        item.canonical_key: item for item in (item_result.scalars().all() if item_result else [])
    }
    lookup_words = [
        point.title
        for point, key in zip(points, keys, strict=True)
        if key not in items_by_key or items_by_key[key].dictionary_enriched_at is None
    ]
    dictionary_entries = await lookup_free_dictionary_batch(lookup_words) if lookup_words else {}
    newly_added = 0
    already_known = 0
    for point, key in zip(points, keys, strict=True):
        item = items_by_key.get(key)
        dictionary_entry = dictionary_entries.get(point.title)
        if item is None:
            item = VocabularyItem(
                learner_id=learner_id,
                word=point.title,
                canonical_key=key,
                entry_kind=_entry_kind(point.title),
                preferred_accent="auto",
                phonetic=dictionary_entry.phonetic if dictionary_entry else None,
                phonetic_uk=dictionary_entry.phonetic_uk if dictionary_entry else None,
                phonetic_us=dictionary_entry.phonetic_us if dictionary_entry else None,
                audio_url=dictionary_entry.audio_url if dictionary_entry else None,
                audio_uk=dictionary_entry.audio_uk if dictionary_entry else None,
                audio_us=dictionary_entry.audio_us if dictionary_entry else None,
                level=source.grade,
                meanings=dictionary_entry.meanings if dictionary_entry else [],
                dictionary_senses=(
                    dictionary_entry.dictionary_senses if dictionary_entry else []
                ),
                word_forms=dictionary_entry.word_forms if dictionary_entry else {},
                dictionary_tags=dictionary_entry.dictionary_tags if dictionary_entry else [],
                collocations=[],
                examples=dictionary_entry.examples if dictionary_entry else [],
                source_ref=f"knowledge:{point.id}",
                dictionary_provider=(dictionary_entry.provider if dictionary_entry else None),
                dictionary_enriched_at=(
                    None
                    if dictionary_entry and dictionary_entry.provider.endswith("_error")
                    else datetime.now(timezone.utc)
                ),
                status="learning",
                confidence=0.0,
                review_count=0,
                next_review_at=datetime.now(timezone.utc),
            )
            db.add(item)
            items_by_key[key] = item
            newly_added += 1
        else:
            already_known += 1
            if dictionary_entry:
                item.phonetic = dictionary_entry.phonetic
                item.phonetic_uk = dictionary_entry.phonetic_uk
                item.phonetic_us = dictionary_entry.phonetic_us
                item.audio_url = dictionary_entry.audio_url
                item.audio_uk = dictionary_entry.audio_uk
                item.audio_us = dictionary_entry.audio_us
                item.meanings = dictionary_entry.meanings
                item.dictionary_senses = dictionary_entry.dictionary_senses
                item.word_forms = dictionary_entry.word_forms
                item.dictionary_tags = dictionary_entry.dictionary_tags
                item.examples = dictionary_entry.examples
                item.dictionary_provider = dictionary_entry.provider
                item.dictionary_enriched_at = (
                    None
                    if dictionary_entry.provider.endswith("_error")
                    else datetime.now(timezone.utc)
                )
    await db.flush()

    item_ids = [items_by_key[key].id for key in keys]
    existing_sources_result = (
        await db.execute(
            select(VocabularyItemSource).where(
                VocabularyItemSource.learner_id == learner_id,
                VocabularyItemSource.curriculum_node_id == node.id,
                VocabularyItemSource.vocabulary_item_id.in_(item_ids),
                VocabularyItemSource.source_type == "textbook_unit",
            )
        )
        if item_ids
        else None
    )
    existing_source_keys = {
        (item.vocabulary_item_id, item.source_id)
        for item in (existing_sources_result.scalars().all() if existing_sources_result else [])
    }
    linked = 0
    label = source_label(source, node)
    for point, key in zip(points, keys, strict=True):
        item = items_by_key[key]
        source_key = (item.id, str(point.id))
        if source_key in existing_source_keys:
            continue
        db.add(
            VocabularyItemSource(
                learner_id=learner_id,
                vocabulary_item_id=item.id,
                source_type="textbook_unit",
                source_id=str(point.id),
                source_version_id=str(source.id),
                reason="current_unit_core_word",
                priority=0.8,
                curriculum_node_id=node.id,
                display_label=label,
                context_snapshot={
                    "book": source.title,
                    "unit": node.title,
                    "source_page": point.source_page,
                    "unit_order": (point.content or {}).get("unit_order"),
                    "dictionary_provider": (
                        dictionary_entries.get(point.title).provider
                        if dictionary_entries.get(point.title)
                        else None
                    ),
                },
                active=True,
            )
        )
        linked += 1
    await db.flush()
    return EnrollmentResult(
        total=len(points),
        newly_added=newly_added,
        source_linked=linked,
        already_known=already_known,
    )


def _align_letters(answer: str, correct: str) -> list[dict[str, Any]]:
    rows, cols = len(answer) + 1, len(correct) + 1
    cost = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        cost[i][0] = i
    for j in range(cols):
        cost[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            cost[i][j] = min(
                cost[i - 1][j] + 1,
                cost[i][j - 1] + 1,
                cost[i - 1][j - 1] + (answer[i - 1] != correct[j - 1]),
            )
    aligned: list[dict[str, Any]] = []
    i, j = len(answer), len(correct)
    while i or j:
        if i and j and cost[i][j] == cost[i - 1][j - 1] + (answer[i - 1] != correct[j - 1]):
            status = "match" if answer[i - 1] == correct[j - 1] else "substitution"
            aligned.append({"answer": answer[i - 1], "correct": correct[j - 1], "status": status})
            i -= 1
            j -= 1
        elif j and cost[i][j] == cost[i][j - 1] + 1:
            aligned.append({"answer": None, "correct": correct[j - 1], "status": "missing"})
            j -= 1
        else:
            aligned.append({"answer": answer[i - 1], "correct": None, "status": "extra"})
            i -= 1
    aligned.reverse()
    return aligned


def spelling_feedback(answer: str, correct: str) -> tuple[str | None, list[dict[str, Any]], str]:
    if answer == correct:
        return None, _align_letters(answer, correct), "拼对了"
    if len(answer) == len(correct) and any(
        answer[index : index + 2] == correct[index : index + 2][::-1]
        and answer[:index] == correct[:index]
        and answer[index + 2 :] == correct[index + 2 :]
        for index in range(max(0, len(answer) - 1))
    ):
        return "transposition", _align_letters(answer, correct), "有两个字母的顺序换了，再听一遍。"
    diff = _align_letters(answer, correct)
    first = next(item for item in diff if item["status"] != "match")
    if first["status"] == "missing":
        return "omission", diff, f"你漏掉了字母 {first['correct']}。"
    if first["status"] == "extra":
        return "insertion", diff, f"这里多了一个 {first['answer']}。"
    return "substitution", diff, f"这里应该是 {first['correct']}，不是 {first['answer']}。"


MASTERY_DIMENSIONS = (
    "recognition",
    "recall",
    "spelling",
    "listening",
    "context_use",
    "production",
)


def default_mastery_vector(confidence: float = 0.0) -> dict[str, float]:
    value = round(max(0.0, min(1.0, confidence)), 3)
    return {dimension: value for dimension in MASTERY_DIMENSIONS}


def mastery_to_dict(mastery: VocabularyMasteryVector | None, confidence: float = 0.0) -> dict[str, float]:
    if mastery is None:
        return default_mastery_vector(confidence)
    return {
        "recognition": mastery.recognition if mastery.recognition is not None else confidence,
        "recall": mastery.recall if mastery.recall is not None else confidence,
        "spelling": mastery.spelling if mastery.spelling is not None else confidence,
        "listening": mastery.listening if mastery.listening is not None else confidence,
        "context_use": mastery.context_use if mastery.context_use is not None else confidence,
        "production": mastery.production if mastery.production is not None else confidence,
    }


def dimensions_for_drill(drill_type: str, result: str) -> tuple[str, ...]:
    if drill_type == "spelling":
        return ("spelling", "listening")
    if drill_type in {"new", "new_learning"}:
        return ("recognition", "context_use")
    if drill_type == "context":
        return ("context_use", "recall")
    if result == "revealed":
        return ("recognition",)
    return ("recognition", "recall")


async def ensure_mastery_vector(
    db: AsyncSession, item: VocabularyItem
) -> VocabularyMasteryVector:
    result = await db.execute(
        select(VocabularyMasteryVector).where(
            VocabularyMasteryVector.learner_id == item.learner_id,
            VocabularyMasteryVector.vocabulary_item_id == item.id,
        )
    )
    mastery = result.scalar_one_or_none()
    if mastery is not None:
        return mastery
    base = default_mastery_vector(item.confidence)
    mastery = VocabularyMasteryVector(
        learner_id=item.learner_id,
        vocabulary_item_id=item.id,
        **base,
    )
    db.add(mastery)
    await db.flush()
    return mastery


def _adjust_mastery_value(value: float, *, result: str, score: float, hint_count: int) -> float:
    if result == "correct":
        gain = 0.16 * max(0.2, min(score, 1.0))
        if hint_count:
            gain *= 0.55
        return round(min(1.0, value + gain), 3)
    penalty = 0.12 if result == "incorrect" else 0.05
    return round(max(0.0, value - penalty), 3)


async def update_item_after_attempt(
    db: AsyncSession,
    item: VocabularyItem,
    *,
    result: str,
    score: float,
    hint_count: int,
    drill_type: str,
) -> None:
    now = datetime.now(timezone.utc)
    before = item.confidence
    mastery = await ensure_mastery_vector(db, item)
    item.review_count += 1
    item.last_reviewed_at = now
    if result == "correct":
        gain = 0.12 if drill_type == "spelling" else 0.1
        if hint_count:
            gain *= 0.5
        item.confidence = min(1.0, item.confidence + gain * score)
        interval = [1, 2, 4, 7, 15, 30][min(item.review_count - 1, 5)]
        item.next_review_at = now + timedelta(days=interval)
        if item.confidence >= 0.9:
            item.status = "mastered"
    else:
        item.confidence = max(0.0, item.confidence - (0.12 if result == "incorrect" else 0.04))
        item.status = "learning"
        item.next_review_at = now + timedelta(days=1)
    for dimension in dimensions_for_drill(drill_type, result):
        current = float(getattr(mastery, dimension))
        setattr(
            mastery,
            dimension,
            _adjust_mastery_value(current, result=result, score=score, hint_count=hint_count),
        )
    db.add(
        ReviewSchedule(
            learner_id=item.learner_id,
            item_type="vocabulary",
            item_id=item.id,
            scheduled_at=now,
            completed_at=now,
            result=result,
            confidence_before=before,
            confidence_after=item.confidence,
            recommended_next_drill=drill_type,
        )
    )


def current_item_id(session: VocabularyPracticeSession) -> uuid.UUID | None:
    if session.current_index >= len(session.item_ids):
        return None
    return uuid.UUID(str(session.item_ids[session.current_index]))


async def record_attempt(
    db: AsyncSession,
    *,
    session: VocabularyPracticeSession,
    item: VocabularyItem,
    idempotency_key: str,
    drill_type: str,
    answer: str | None,
    result: str,
    score: float,
    error_type: str | None,
    letter_diff: list[dict[str, Any]],
    response_time_ms: int | None,
    hint_count: int,
    replay_count: int,
) -> VocabularyAttempt:
    attempt = VocabularyAttempt(
        session_id=session.id,
        learner_id=session.learner_id,
        vocabulary_item_id=item.id,
        drill_type=drill_type,
        idempotency_key=idempotency_key,
        answer=answer,
        normalized_answer=canonical_vocabulary_key(answer or "") or None,
        result=result,
        score=score,
        error_type=error_type,
        letter_diff=letter_diff,
        response_time_ms=response_time_ms,
        hint_count=hint_count,
        replay_count=replay_count,
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    await update_item_after_attempt(
        db,
        item,
        result=result,
        score=score,
        hint_count=hint_count,
        drill_type=drill_type,
    )
    if result == "correct":
        session.correct_count += 1
    if hint_count:
        session.hinted_count += 1
    if result == "revealed":
        session.revealed_count += 1
    await db.flush()
    if result == "incorrect":
        db.add(
            VocabularyMistake(
                learner_id=session.learner_id,
                vocabulary_item_id=item.id,
                attempt_id=attempt.id,
                mistake_type=error_type or drill_type,
                note=None,
                correction=item.word,
                active=True,
            )
        )
        await db.flush()
    return attempt


async def excluded_item_ids(db: AsyncSession, learner_id: uuid.UUID) -> set[uuid.UUID]:
    result = await db.execute(
        select(VocabularyUserOverride.vocabulary_item_id).where(
            VocabularyUserOverride.learner_id == learner_id,
            VocabularyUserOverride.excluded_from_review.is_(True),
        )
    )
    return set(result.scalars().all())
