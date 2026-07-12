from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.knowledge import CurriculumNode, KnowledgePoint, KnowledgeSource
from src.models.learning_progress import LearningProgressItem
from src.prompts.executor import PromptExecutionContext, PromptExecutor
from src.providers.router import ModelRouter
from src.classroom.catalog import unit_catalog

ROOT = Path(__file__).resolve().parents[2]
AUDIO_ROOT = ROOT / "docs" / "books" / "audio" / "七年级上册-英语朗读宝"
UPPER_SOURCE_ID = uuid.UUID("c7000000-0000-4000-8000-000000000001")

AUDIO_BY_ORDINAL = {
    1: "01-Starter-Unit-1-Hello.mp3",
    2: "02-Starter-Unit-2-Keep-Tidy.mp3",
    3: "03-Starter-Unit-3-Welcome.mp3",
    4: "04-Unit-1-You-and-Me.mp3",
    5: "05-Unit-2-Were-Family.mp3",
    6: "06-Unit-3-My-School.mp3",
    7: "07-Unit-4-My-Favourite-Subject.mp3",
    8: "08-Unit-5-Fun-Clubs.mp3",
    9: "09-Unit-6-A-Day-in-the-Life.mp3",
    10: "10-Unit-7-Happy-Birthday.mp3",
}


class ClassroomNotFoundError(LookupError):
    pass


async def compose_classroom(
    db: AsyncSession,
    model_router: ModelRouter,
    *,
    learner_id: uuid.UUID,
    curriculum_node_id: uuid.UUID,
    time_budget_minutes: int,
) -> dict[str, Any]:
    row = (
        await db.execute(
            select(CurriculumNode, KnowledgeSource)
            .join(KnowledgeSource, KnowledgeSource.id == CurriculumNode.source_id)
            .where(CurriculumNode.id == curriculum_node_id)
        )
    ).first()
    if row is None:
        raise ClassroomNotFoundError("curriculum node not found")
    node, source = row
    points = list(
        (
            await db.scalars(
                select(KnowledgePoint)
                .where(KnowledgePoint.curriculum_node_id == node.id)
                .where(KnowledgePoint.status == "published")
                .order_by(KnowledgePoint.type, KnowledgePoint.title)
            )
        ).all()
    )
    fallback = _fallback_spec(node=node, source=source, points=points, minutes=time_budget_minutes)
    resume = await load_classroom_progress(
        db,
        learner_id=learner_id,
        classroom_id=fallback["classroom_id"],
    )
    generation_mode = "curated_fallback"
    if resume is None:
        try:
            # Local Ollama commonly needs several seconds for the first structured
            # response. Give composition enough room to be genuinely generative;
            # the curated classroom remains the deterministic fallback.
            async with asyncio.timeout(15):
                result = await PromptExecutor(db=db, model_router=model_router).execute(
                    prompt_id="classroom.ui.compose",
                    variables={
                        "unit": {"title": node.title, "subtitle": node.subtitle},
                        "time_budget_minutes": time_budget_minutes,
                        "knowledge_points": [
                            {"type": point.type, "title": point.title, "summary": point.summary}
                            for point in points[:12]
                        ],
                        "teaching_plan": fallback.get("teaching", {}),
                        "fallback_spec": fallback,
                    },
                    context=PromptExecutionContext(
                        learner_id=learner_id,
                        source_module="classroom",
                        target_type="curriculum_node",
                        target_id=node.id,
                    ),
                )
            if result.validated_output and result.decision != "rejected":
                generated = result.validated_output
                fallback["hero"] = {**fallback["hero"], **generated.get("hero", {})}
                fallback["focus"] = {**fallback["focus"], **generated.get("focus", {})}
                if generated.get("language_cards"):
                    fallback["language_cards"] = generated["language_cards"]
                generation_mode = "llm_generated"
        except Exception:
            # The classroom must remain usable when the model is slow or unavailable.
            pass
    fallback["generation_mode"] = generation_mode
    fallback["resume"] = resume
    return fallback


async def coach_textbook_task(
    db: AsyncSession,
    model_router: ModelRouter,
    *,
    learner_id: uuid.UUID,
    curriculum_node_id: uuid.UUID,
    task_id: str,
    answer: str,
) -> dict[str, Any]:
    row = (
        await db.execute(
            select(CurriculumNode, KnowledgeSource)
            .join(KnowledgeSource, KnowledgeSource.id == CurriculumNode.source_id)
            .where(CurriculumNode.id == curriculum_node_id)
        )
    ).first()
    if row is None:
        raise ClassroomNotFoundError("curriculum node not found")
    node, source = row
    catalog_unit = unit_catalog(node.ordinal) if source.id == UPPER_SOURCE_ID else None
    task = next(
        (item for item in (catalog_unit or {}).get("textbook_tasks", []) if item["id"] == task_id),
        None,
    )
    if task is None:
        raise ClassroomNotFoundError("textbook task not found")
    response: dict[str, Any] = {
        "diagnosis": "作答已记录，先检查是否按活动编号覆盖了教材页中的每一小题。",
        "evidence": [f"当前答案共 {len(answer.strip())} 个字符"],
        "hint": "逐题核对题号；听力题可回到上一阶段重听对应 Section，其他题先圈出关键词。",
        "next_action": "continue" if len(answer.strip()) >= 12 else "review_pattern",
        "generation_mode": "curated_fallback",
    }
    try:
        async with asyncio.timeout(10):
            result = await PromptExecutor(db=db, model_router=model_router).execute(
                prompt_id="classroom.textbook.coach",
                variables={
                    "unit": {"title": node.title, "subtitle": node.subtitle},
                    "task": {
                        "title": task["title"],
                        "printed_page": task["printed_page"],
                        "instruction": task["instruction"],
                    },
                    "source_text": task.get("source_text", ""),
                    "vocabulary": [
                        item["term"] for item in (catalog_unit or {}).get("vocabulary", [])[:30]
                    ],
                    "teaching_focus": list((catalog_unit or {}).get("teaching", {}).values())[:4],
                    "answer": answer,
                },
                context=PromptExecutionContext(
                    learner_id=learner_id,
                    source_module="classroom",
                    target_type="curriculum_node",
                    target_id=node.id,
                ),
            )
        if result.validated_output and result.decision != "rejected":
            response.update(result.validated_output)
            if isinstance(response.get("evidence"), str):
                response["evidence"] = [response["evidence"]]
            response["generation_mode"] = "llm_generated"
    except Exception:
        pass
    return response


async def load_classroom_progress(
    db: AsyncSession,
    *,
    learner_id: uuid.UUID,
    classroom_id: str,
) -> dict[str, Any] | None:
    item = await db.scalar(
        select(LearningProgressItem).where(
            LearningProgressItem.learner_id == learner_id,
            LearningProgressItem.skill == "daily_classroom",
            LearningProgressItem.item_id == classroom_id,
        )
    )
    if item is None:
        return None
    metadata = item.metadata_ or {}
    return {
        "current_phase_id": metadata.get("current_phase_id", "launch"),
        "completed_phase_ids": metadata.get("completed_phase_ids", []),
        "flipped_card_ids": metadata.get("flipped_card_ids", []),
        "listened_cue_ids": metadata.get("listened_cue_ids", []),
        "textbook_task_answers": metadata.get("textbook_task_answers", {}),
        "grammar_answers": metadata.get("grammar_answers", {}),
        "grammar_transfer": metadata.get("grammar_transfer", ""),
        "vocabulary_confidence": metadata.get("vocabulary_confidence", {}),
        "continuous_audio_played": bool(metadata.get("continuous_audio_played", False)),
        "status": item.status,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


async def save_classroom_progress(
    db: AsyncSession,
    *,
    learner_id: uuid.UUID,
    curriculum_node_id: uuid.UUID,
    classroom_id: str,
    current_phase_id: str,
    completed_phase_ids: list[str],
    flipped_card_ids: list[str],
    listened_cue_ids: list[str],
    textbook_task_answers: dict[str, str] | None = None,
    grammar_answers: dict[str, str] | None = None,
    grammar_transfer: str = "",
    vocabulary_confidence: dict[str, str] | None = None,
    continuous_audio_played: bool = False,
    completed: bool,
) -> dict[str, Any]:
    node = await db.get(CurriculumNode, curriculum_node_id)
    expected_classroom_id = f"{curriculum_node_id}:v1"
    if node is None or classroom_id != expected_classroom_id:
        raise ClassroomNotFoundError("classroom not found")

    item = await db.scalar(
        select(LearningProgressItem).where(
            LearningProgressItem.learner_id == learner_id,
            LearningProgressItem.skill == "daily_classroom",
            LearningProgressItem.item_id == classroom_id,
        )
    )
    now = datetime.now(UTC)
    metadata = {
        "curriculum_node_id": str(curriculum_node_id),
        "current_phase_id": current_phase_id,
        "completed_phase_ids": _unique_strings(completed_phase_ids, limit=12),
        "flipped_card_ids": _unique_strings(flipped_card_ids, limit=12),
        "listened_cue_ids": _unique_strings(listened_cue_ids, limit=240),
        "textbook_task_answers": {
            str(key)[:80]: str(value)[:2000]
            for key, value in (textbook_task_answers or {}).items()
            if str(key).strip() and str(value).strip()
        },
        "grammar_answers": {
            str(key)[:80]: str(value)[:500]
            for key, value in (grammar_answers or {}).items()
            if str(key).strip() and str(value).strip()
        },
        "grammar_transfer": grammar_transfer.strip()[:2000],
        "vocabulary_confidence": {
            str(key)[:80]: str(value)
            for key, value in (vocabulary_confidence or {}).items()
            if str(key).strip() and value in {"known", "fuzzy", "unknown"}
        },
        "continuous_audio_played": continuous_audio_played,
        "schema_version": "1.0",
    }
    if item is None:
        item = LearningProgressItem(
            learner_id=learner_id,
            skill="daily_classroom",
            item_id=classroom_id,
            title=f"{node.title} · {node.subtitle or '每日课堂'}",
            status="learned" if completed else "in_progress",
            opened_count=1,
            last_opened_at=now,
            learned_at=now if completed else None,
            metadata_=metadata,
        )
        db.add(item)
    else:
        item.status = "learned" if completed else "in_progress"
        item.last_opened_at = now
        item.learned_at = item.learned_at or (now if completed else None)
        item.metadata_ = metadata
    await db.flush()
    return {
        "classroom_id": classroom_id,
        "status": item.status,
        "saved_at": now.isoformat(),
    }


def audio_path(track: str) -> Path:
    allowed = set(AUDIO_BY_ORDINAL.values())
    if track not in allowed:
        raise ClassroomNotFoundError("audio track not found")
    path = AUDIO_ROOT / track
    if not path.is_file():
        raise ClassroomNotFoundError("audio track not found")
    return path


def timeline_payload(track: str) -> dict[str, Any] | None:
    path = audio_path(track).with_suffix(".timeline.json")
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _unique_strings(values: list[str], *, limit: int) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))[:limit]


def _fallback_spec(*, node: CurriculumNode, source: KnowledgeSource, points: list[KnowledgePoint], minutes: int) -> dict[str, Any]:
    summaries = {point.type: point.summary for point in points}
    catalog_unit = unit_catalog(node.ordinal) if source.id == UPPER_SOURCE_ID else None
    words: list[str] = []
    for point in points:
        if point.type != "vocabulary":
            continue
        content = point.content or {}
        words.extend(str(word) for word in content.get("words", []))
        if not words:
            words.extend(part.strip() for part in point.summary.replace("、", ",").split(",") if part.strip())
    catalog_words = list(catalog_unit.get("vocabulary", [])) if catalog_unit else []
    primary_words = list(catalog_unit.get("primary_review_vocabulary", [])) if catalog_unit else []
    teaching = catalog_unit.get("teaching", {}) if catalog_unit else {}
    grammar_lab = catalog_unit.get("grammar_lab") if catalog_unit else None
    learning_goals = [
        item
        for item in teaching.get("学习目标", teaching.get("单元学习目标", []))
        if not item.endswith("能够：")
    ]
    if catalog_words:
        words = [str(item["term"]) for item in catalog_words]
    audio = AUDIO_BY_ORDINAL.get(node.ordinal) if source.id == UPPER_SOURCE_ID else None
    phases = [
        {"id": "launch", "kind": "briefing", "title": "入场 · 明确任务", "minutes": 2, "icon": "sparkles"},
        {"id": "notice", "kind": "cards", "title": "词汇 · 新词与小学复现", "minutes": max(3, minutes // 5), "icon": "scan"},
    ]
    if grammar_lab:
        phases.append({"id": "grammar", "kind": "grammar", "title": "语法 · 看懂并会用", "minutes": max(6, minutes // 4), "icon": "braces"})
    if audio:
        phases.append({"id": "listen", "kind": "audio", "title": "听辨 · 教材原声", "minutes": max(4, minutes // 4), "icon": "headphones"})
    if catalog_unit and catalog_unit.get("textbook_tasks"):
        phases.append({"id": "textbook", "kind": "textbook", "title": "教材 · 完成原题", "minutes": max(5, minutes // 3), "icon": "book-open"})
    phases.extend([
        {"id": "practice", "kind": "challenge", "title": "诊断 · AI 挑战", "minutes": max(4, minutes // 4), "icon": "target"},
        {"id": "reflect", "kind": "reflection", "title": "收束 · 学习复盘", "minutes": 2, "icon": "flag"},
    ])
    return {
        "schema_version": "1.0",
        "classroom_id": f"{node.id}:v1",
        "source": {"id": str(source.id), "title": source.title, "edition": source.edition or ""},
        "unit": {"id": str(node.id), "title": node.title, "subtitle": node.subtitle or "", "ordinal": node.ordinal},
        "hero": {
            "eyebrow": "PEP 2024 · AI ORGANIZED CLASS",
            "title": f"{node.title} · {node.subtitle or '今日课堂'}",
            "mission": (
                "；".join(learning_goals[:2])
                if learning_goals
                else summaries.get("text_note", f"围绕 {node.subtitle or node.title} 完成词汇激活、原声听辨、教材做题和 AI 诊断。")
            ),
            "coach_message": "教材负责提供可信内容，AI 负责发现你卡在哪里、何时给提示、下一步练什么。今天先听懂和做题，再用挑战确认是否真正掌握。",
        },
        "phases": phases,
        "language_cards": [
            {
                "id": f"word-{index}",
                "front": word,
                "back": (
                    f"{catalog_words[index].get('meaning_zh', '')} · 想一个教材语境"
                    if index < len(catalog_words)
                    else "说出含义并想一个教材语境"
                ),
                "accent": ["violet", "cyan", "amber", "rose"][index % 4],
            }
            for index, word in enumerate(words[:8])
        ] or [
            {"id": "theme", "front": node.subtitle or node.title, "back": summaries.get("grammar", "用英语说出本单元主题。"), "accent": "violet"}
        ],
        "focus": {
            "grammar": (
                str(grammar_lab.get("can_do"))
                if grammar_lab
                else summaries.get("grammar", "在真实语境中发现并使用本单元核心句型。")
            ),
            "question": f"你能用英语谈谈 {node.subtitle or node.title} 吗？",
        },
        "audio": (
            {
                "track": audio,
                "timeline_available": (AUDIO_ROOT / audio).with_suffix(".timeline.json").is_file(),
            }
            if audio
            else None
        ),
        "vocabulary": {
            "core_count": len(catalog_words),
            "primary_review_count": len(primary_words),
            "core": catalog_words,
            "primary_review": primary_words,
        },
        "teaching": teaching,
        "grammar_lab": grammar_lab,
        "textbook_tasks": catalog_unit.get("textbook_tasks", []) if catalog_unit else [],
        "completion": {"xp": 60, "memory_message": "课堂结果会同步到掌握度、学习记忆与复习计划。"},
    }
