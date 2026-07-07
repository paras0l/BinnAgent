import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.group_learning import (
    GroupLearningMessage,
    GroupLearningParticipant,
    GroupLearningSignal,
    GroupLearningSource,
)
from src.models.learning_progress import LearningProgressItem
from src.models.vocabulary import VocabularyItem, VocabularyItemSource
from src.models.writing_phrase import WritingPhrase
from src.vocabulary.learning import canonical_vocabulary_key


@dataclass(frozen=True)
class GroupLearningImportMessage:
    external_message_id: str
    external_member_key: str
    content_text: str
    occurred_at: datetime
    display_name: str | None = None
    message_type: str = "text"


@dataclass(frozen=True)
class GroupLearningImportResult:
    imported_count: int
    duplicate_count: int
    generated_signal_count: int
    ignored_count: int
    participant_count: int


@dataclass(frozen=True)
class SignalDraft:
    signal_type: str
    target_type: str
    target_label: str
    confidence: float
    evidence_text: str
    normalized_note: str | None
    recommendation_reason: str
    metadata: dict[str, Any]


def normalize_message_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_message_text(text).casefold().encode("utf-8")).hexdigest()


def detect_language_mix(text: str) -> str:
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", text))
    has_latin = bool(re.search(r"[A-Za-z]", text))
    if has_cjk and has_latin:
        return "mixed"
    if has_cjk:
        return "zh"
    if has_latin:
        return "en"
    return "unknown"


async def import_group_messages(
    db: AsyncSession,
    *,
    source_id: uuid.UUID,
    messages: list[GroupLearningImportMessage],
) -> GroupLearningImportResult:
    source = await _get_source(db, source_id)
    participants = await _participants_by_member_key(db, source.id)
    imported_count = 0
    duplicate_count = 0
    ignored_count = 0
    generated_signal_count = 0

    for raw_message in messages:
        text = normalize_message_text(raw_message.content_text)
        if not text or raw_message.message_type != "text":
            ignored_count += 1
            continue
        if source.allowed_senders and raw_message.external_member_key not in source.allowed_senders:
            ignored_count += 1
            continue

        participant = participants.get(raw_message.external_member_key)
        if participant is None:
            participant = GroupLearningParticipant(
                source_id=source.id,
                external_member_key=raw_message.external_member_key,
                display_name=raw_message.display_name or raw_message.external_member_key,
                learner_id=None,
                role="unknown",
                analysis_enabled=False,
                last_message_at=raw_message.occurred_at,
            )
            db.add(participant)
            await db.flush()
            participants[participant.external_member_key] = participant
        else:
            participant.display_name = raw_message.display_name or participant.display_name
            participant.last_message_at = raw_message.occurred_at

        message_hash = content_hash(text)
        duplicate = await _find_existing_message(
            db,
            source_id=source.id,
            external_message_id=raw_message.external_message_id,
            message_hash=message_hash,
        )
        if duplicate is not None:
            duplicate_count += 1
            if (
                duplicate.learner_id == source.learner_id
                and duplicate.ingestion_status == "processed"
                and text.startswith("#")
            ):
                generated_signal_count += await _write_missing_signal_drafts(
                    db,
                    source=source,
                    message=duplicate,
                    text=text,
                )
            elif duplicate.learner_id == source.learner_id and not text.startswith("#"):
                duplicate.ingestion_status = "pending_llm_analysis"
                duplicate.processed_at = None
            continue

        should_analyze = (
            source.status == "active"
            and participant.role == "learner"
            and bool(participant.analysis_enabled)
            and participant.learner_id == source.learner_id
        )
        tagged = text.startswith("#")
        message = GroupLearningMessage(
            source_id=source.id,
            external_message_id=raw_message.external_message_id,
            external_member_key=raw_message.external_member_key,
            learner_id=source.learner_id if should_analyze else None,
            message_type=raw_message.message_type,
            content_text=text,
            content_hash=message_hash,
            language_mix=detect_language_mix(text),
            occurred_at=raw_message.occurred_at,
            ingestion_status=(
                "processed"
                if should_analyze and tagged
                else "pending_llm_analysis"
                if should_analyze
                else "ignored_unmapped_participant"
            ),
            processed_at=datetime.now(timezone.utc) if should_analyze and tagged else None,
        )
        db.add(message)
        await db.flush()
        imported_count += 1

        if not should_analyze:
            ignored_count += 1
            continue

        if tagged:
            generated_signal_count += await _write_missing_signal_drafts(
                db,
                source=source,
                message=message,
                text=text,
            )

    if messages:
        source.last_seen_at = max(message.occurred_at for message in messages)
    source.last_import_summary = {
        "imported_count": imported_count,
        "duplicate_count": duplicate_count,
        "generated_signal_count": generated_signal_count,
        "ignored_count": ignored_count,
    }
    await db.flush()
    return GroupLearningImportResult(
        imported_count=imported_count,
        duplicate_count=duplicate_count,
        generated_signal_count=generated_signal_count,
        ignored_count=ignored_count,
        participant_count=len(participants),
    )


async def _write_missing_signal_drafts(
    db: AsyncSession,
    *,
    source: GroupLearningSource,
    message: GroupLearningMessage,
    text: str,
) -> int:
    generated_count = 0
    for draft in extract_signal_drafts(text, source=source):
        existing = await _find_existing_signal_for_draft(db, message.id, draft)
        if existing is not None:
            continue
        signal = GroupLearningSignal(
            message_id=message.id,
            learner_id=source.learner_id,
            signal_type=draft.signal_type,
            target_type=draft.target_type,
            target_label=draft.target_label,
            confidence=draft.confidence,
            evidence_text=draft.evidence_text,
            normalized_note=draft.normalized_note,
            recommendation_reason=draft.recommendation_reason,
            status="candidate",
            metadata_=draft.metadata,
        )
        db.add(signal)
        generated_count += 1
    return generated_count


async def _find_existing_signal_for_draft(
    db: AsyncSession,
    message_id: uuid.UUID,
    draft: SignalDraft,
) -> GroupLearningSignal | None:
    result = await db.execute(
        select(GroupLearningSignal).where(
            GroupLearningSignal.message_id == message_id,
            GroupLearningSignal.signal_type == draft.signal_type,
            GroupLearningSignal.target_type == draft.target_type,
            GroupLearningSignal.target_label == draft.target_label,
        )
    )
    return result.scalar_one_or_none()


def extract_signal_drafts(text: str, *, source: GroupLearningSource | None = None) -> list[SignalDraft]:
    normalized = normalize_message_text(text)
    drafts: list[SignalDraft] = []
    lower = normalized.casefold()
    tagged = normalized.startswith("#")

    if match := re.match(r"#单词\s+(.+)", normalized):
        word = match.group(1).strip()
        drafts.append(
            _draft(
                "desired_vocabulary",
                "vocabulary",
                word,
                0.98,
                normalized,
                f"用户主动标记想学习词汇：{word}",
                "主动 #单词 标签，可信度高，可进入词汇候选。",
                tagged=True,
            )
        )
    if match := re.match(r"#语法\s+(.+)", normalized):
        topic = match.group(1).strip()
        drafts.append(
            _draft(
                "desired_grammar",
                "grammar",
                topic,
                0.96,
                normalized,
                f"用户主动标记想学习语法：{topic}",
                "主动 #语法 标签，适合进入语法推荐。",
                tagged=True,
            )
        )
    if match := re.match(r"#收藏\s+(.+)", normalized):
        sentence = match.group(1).strip()
        drafts.append(_good_sentence_draft(sentence, evidence=normalized, confidence=0.94, tagged=True))
    if match := re.match(r"#怎么说\s+(.+)", normalized):
        zh_text = match.group(1).strip()
        drafts.append(_expression_gap_draft(zh_text, evidence=normalized, confidence=0.95, tagged=True))
    if match := re.match(r"#纠错\s+(.+)", normalized):
        corrected = match.group(1).strip()
        drafts.extend(_grammar_error_drafts(corrected, evidence=normalized, confidence=0.96, tagged=True))

    drafts.extend(_grammar_error_drafts(normalized, evidence=normalized, confidence=0.93, tagged=tagged))

    if re.search(r"\bhave been [a-z]+ing\b.+\bfor\b", lower):
        drafts.append(
            _draft(
                "grammar_correct_usage",
                "grammar",
                "present perfect continuous",
                0.79,
                normalized,
                "自然聊天中正确使用现在完成进行时。",
                "群聊自然聊天证据权重较低，但可作为语法熟练度弱证据。",
                weight=0.3,
                source_status=getattr(source, "status", None),
            )
        )

    if "太绝对" in normalized or "怎么说" in normalized or "委婉" in normalized:
        drafts.append(_expression_gap_draft(normalized, evidence=normalized, confidence=0.86, tagged=tagged))

    if _looks_like_good_sentence(normalized):
        drafts.append(_good_sentence_draft(normalized, evidence=normalized, confidence=0.91, tagged=tagged))

    return _dedupe_drafts(drafts)


async def accept_signal(db: AsyncSession, signal: GroupLearningSignal) -> GroupLearningSignal:
    if signal.status == "accepted" and signal.applied_target_id is not None:
        return signal

    if signal.signal_type in {"good_sentence", "phrase_candidate", "expression_gap"}:
        target = await _apply_to_writing_phrase(db, signal)
        signal.applied_target_type = "writing_phrase"
        signal.applied_target_id = target.id
    elif signal.signal_type in {"desired_vocabulary", "vocabulary_candidate"}:
        target = await _apply_to_vocabulary(db, signal)
        signal.applied_target_type = "vocabulary_item"
        signal.applied_target_id = target.id
    else:
        target = await _apply_to_learning_progress(db, signal)
        signal.applied_target_type = "learning_progress_item"
        signal.applied_target_id = target.id

    signal.status = "accepted"
    await db.flush()
    await db.refresh(signal)
    return signal


async def cleanup_expired_messages(db: AsyncSession, source: GroupLearningSource) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=source.raw_retention_days)
    result = await db.execute(
        select(GroupLearningMessage).where(
            GroupLearningMessage.source_id == source.id,
            GroupLearningMessage.occurred_at < cutoff,
            GroupLearningMessage.content_text.is_not(None),
        )
    )
    messages = result.scalars().all()
    for message in messages:
        message.content_text = None
        message.ingestion_status = "raw_deleted_retention"
    await db.flush()
    return len(messages)


async def delete_all_raw_messages(db: AsyncSession, source: GroupLearningSource) -> int:
    result = await db.execute(
        select(GroupLearningMessage).where(
            GroupLearningMessage.source_id == source.id,
            GroupLearningMessage.content_text.is_not(None),
        )
    )
    messages = result.scalars().all()
    for message in messages:
        message.content_text = None
        message.ingestion_status = "raw_deleted_manual"
    await db.flush()
    return len(messages)


async def _get_source(db: AsyncSession, source_id: uuid.UUID) -> GroupLearningSource:
    result = await db.execute(select(GroupLearningSource).where(GroupLearningSource.id == source_id))
    source = result.scalar_one_or_none()
    if source is None:
        raise ValueError("Group learning source not found")
    return source


async def _participants_by_member_key(
    db: AsyncSession, source_id: uuid.UUID
) -> dict[str, GroupLearningParticipant]:
    result = await db.execute(
        select(GroupLearningParticipant).where(GroupLearningParticipant.source_id == source_id)
    )
    return {participant.external_member_key: participant for participant in result.scalars().all()}


async def _find_existing_message(
    db: AsyncSession,
    *,
    source_id: uuid.UUID,
    external_message_id: str,
    message_hash: str,
) -> GroupLearningMessage | None:
    result = await db.execute(
        select(GroupLearningMessage).where(
            GroupLearningMessage.source_id == source_id,
            or_(
                GroupLearningMessage.external_message_id == external_message_id,
                GroupLearningMessage.content_hash == message_hash,
            ),
        )
    )
    return result.scalar_one_or_none()


def _grammar_error_drafts(
    text: str,
    *,
    evidence: str,
    confidence: float,
    tagged: bool,
) -> list[SignalDraft]:
    lower = text.casefold()
    drafts: list[SignalDraft] = []
    if re.search(r"\bi am agree\b", lower):
        drafts.append(
            _draft(
                "grammar_error",
                "grammar",
                "agree 不需要 be",
                confidence,
                evidence,
                "agree 是动词，这里不需要 be；自然表达是 I agree with you.",
                "写入语法推荐和学习画像弱点，后续可练 agree with / be in agreement with。",
                tagged=tagged,
                correction="I agree with you.",
                weight=0.4,
            )
        )
    return drafts


def _expression_gap_draft(
    text: str,
    *,
    evidence: str,
    confidence: float,
    tagged: bool,
) -> SignalDraft:
    return _draft(
        "expression_gap",
        "writing_phrase",
        "委婉反驳 / hedging",
        confidence,
        evidence,
        "这像是中文表达缺口，适合沉淀为英语观点表达。",
        "可学表达：That claim may be too strong. / I think this view needs more nuance.",
        tagged=tagged,
        suggested_expressions=[
            "That claim may be too strong.",
            "I think this view needs more nuance.",
        ],
        source_text=text,
    )


def _good_sentence_draft(
    sentence: str,
    *,
    evidence: str,
    confidence: float,
    tagged: bool,
) -> SignalDraft:
    label = sentence
    if re.search(r"what matters most is not .+ but .+", sentence.casefold()):
        label = "What matters most is not A, but B."
    return _draft(
        "good_sentence",
        "writing_phrase",
        label,
        confidence,
        evidence,
        "这是可迁移的作文句式，适合进入好句收藏候选。",
        "强调重点 / 对比结构，可用于观点强调和学习反思。",
        tagged=tagged,
        sentence=sentence,
    )


def _looks_like_good_sentence(text: str) -> bool:
    lower = text.casefold()
    return bool(
        re.search(r"what matters most is not .+ but .+", lower)
        or ("not how" in lower and "but how" in lower)
    )


def _draft(
    signal_type: str,
    target_type: str,
    target_label: str,
    confidence: float,
    evidence_text: str,
    normalized_note: str,
    recommendation_reason: str,
    **metadata: Any,
) -> SignalDraft:
    return SignalDraft(
        signal_type=signal_type,
        target_type=target_type,
        target_label=target_label.strip()[:255],
        confidence=confidence,
        evidence_text=evidence_text,
        normalized_note=normalized_note,
        recommendation_reason=recommendation_reason,
        metadata=metadata,
    )


def _dedupe_drafts(drafts: list[SignalDraft]) -> list[SignalDraft]:
    seen: set[tuple[str, str]] = set()
    unique: list[SignalDraft] = []
    for draft in drafts:
        key = (draft.signal_type, draft.target_label.casefold())
        if key in seen:
            continue
        seen.add(key)
        unique.append(draft)
    return unique


async def _apply_to_writing_phrase(
    db: AsyncSession,
    signal: GroupLearningSignal,
) -> WritingPhrase:
    text = _phrase_text_from_signal(signal)
    normalized = _normalize_phrase_text(text)
    result = await db.execute(
        select(WritingPhrase).where(
            WritingPhrase.learner_id == signal.learner_id,
            WritingPhrase.normalized_text == normalized,
        )
    )
    phrase = result.scalar_one_or_none()
    if phrase is None:
        phrase = WritingPhrase(
            learner_id=signal.learner_id,
            text=text,
            normalized_text=normalized,
            chinese_meaning=signal.normalized_note,
            explanation=signal.recommendation_reason,
            usage_scene="群聊学习线索捕捉",
            usage_position="body",
            tags=["群聊线索", signal.signal_type],
            examples=[{"sentence": text, "translation": signal.normalized_note or ""}],
            notes=[signal.evidence_text],
            mistakes=[],
            source_type="group_learning_signal",
            source_ref=str(signal.id),
            source_raw_text=signal.evidence_text,
            register_level=None,
            difficulty=2,
            is_favorite=False,
            is_archived=False,
            review_enabled=True,
            metadata_={"group_learning_signal_id": str(signal.id)},
        )
        db.add(phrase)
        await db.flush()
    return phrase


async def _apply_to_vocabulary(db: AsyncSession, signal: GroupLearningSignal) -> VocabularyItem:
    word = signal.target_label.strip()
    canonical = canonical_vocabulary_key(word)
    result = await db.execute(
        select(VocabularyItem).where(
            VocabularyItem.learner_id == signal.learner_id,
            VocabularyItem.canonical_key == canonical,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        item = VocabularyItem(
            learner_id=signal.learner_id,
            word=word,
            canonical_key=canonical,
            entry_kind="phrase" if " " in canonical else "word",
            preferred_accent="auto",
            level="custom",
            meanings=[],
            dictionary_senses=[],
            word_forms={},
            dictionary_tags=["group_learning"],
            collocations=[],
            examples=[],
            source_ref=f"group_learning_signal:{signal.id}",
            status="learning",
            confidence=signal.confidence,
            review_count=0,
            next_review_at=datetime.now(timezone.utc),
        )
        db.add(item)
        await db.flush()
    await _ensure_vocabulary_source(db, signal, item)
    return item


async def _ensure_vocabulary_source(
    db: AsyncSession,
    signal: GroupLearningSignal,
    item: VocabularyItem,
) -> None:
    result = await db.execute(
        select(VocabularyItemSource).where(
            VocabularyItemSource.learner_id == signal.learner_id,
            VocabularyItemSource.vocabulary_item_id == item.id,
            VocabularyItemSource.source_type == "group_learning_signal",
            VocabularyItemSource.source_id == str(signal.id),
        )
    )
    source = result.scalar_one_or_none()
    if source is None:
        db.add(
            VocabularyItemSource(
                learner_id=signal.learner_id,
                vocabulary_item_id=item.id,
                source_type="group_learning_signal",
                source_id=str(signal.id),
                reason=signal.signal_type,
                priority=signal.confidence,
                display_label="群聊学习线索",
                context_snapshot={
                    "evidence_text": signal.evidence_text,
                    "recommendation_reason": signal.recommendation_reason,
                },
                active=True,
            )
        )


async def _apply_to_learning_progress(
    db: AsyncSession,
    signal: GroupLearningSignal,
) -> LearningProgressItem:
    item_id = re.sub(r"[^a-z0-9_-]+", "-", signal.target_label.casefold()).strip("-")[:150]
    if not item_id:
        item_id = signal.signal_type
    result = await db.execute(
        select(LearningProgressItem).where(
            LearningProgressItem.learner_id == signal.learner_id,
            LearningProgressItem.skill == "grammar",
            LearningProgressItem.item_id == item_id,
        )
    )
    item = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    metadata = {
        "group_learning_signal_id": str(signal.id),
        "signal_type": signal.signal_type,
        "confidence": signal.confidence,
        "evidence_text": signal.evidence_text,
        "recommendation_reason": signal.recommendation_reason,
    }
    if item is None:
        item = LearningProgressItem(
            learner_id=signal.learner_id,
            skill="grammar",
            item_id=item_id,
            title=signal.target_label,
            status="opened",
            is_favorite=False,
            opened_count=1,
            last_opened_at=now,
            metadata_=metadata,
        )
        db.add(item)
        await db.flush()
    else:
        item.opened_count = (item.opened_count or 0) + 1
        item.last_opened_at = now
        item.metadata_ = {**(item.metadata_ or {}), **metadata}
    return item


def _phrase_text_from_signal(signal: GroupLearningSignal) -> str:
    metadata = signal.metadata_ or {}
    if sentence := metadata.get("sentence"):
        return str(sentence)
    if expressions := metadata.get("suggested_expressions"):
        if isinstance(expressions, list) and expressions:
            return str(expressions[0])
    return signal.target_label


def _normalize_phrase_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).lower()
