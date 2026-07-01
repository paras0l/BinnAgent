import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session, get_model_router
from src.config import settings
from src.exercises.attempt_service import ExerciseTargetType
from src.exercises.item_mapper import exercise_question_to_item
from src.knowledge.exercises import ensure_unit_exercises
from src.models.knowledge import CurriculumNode
from src.models.learner import Learner
from src.providers.base import ChatRequest
from src.providers.router import ModelRouter

router = APIRouter(
    prefix="/api/learners/{learner_id}/exercises",
    tags=["exercises"],
)

ExerciseType = Literal["single_choice", "fill_blank"]


class ExerciseTargetPayload(BaseModel):
    type: ExerciseTargetType
    id: str = Field(min_length=1, max_length=255)
    label: str = Field(min_length=1, max_length=255)


class GenerateExerciseContext(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    page: str | None = Field(default=None, max_length=200)
    explanation: str | None = Field(default=None, max_length=2000)
    examples: list[str] = Field(default_factory=list, max_length=8)
    learner_level: str | None = Field(
        default=None,
        max_length=80,
        validation_alias=AliasChoices("learnerLevel", "learner_level"),
        serialization_alias="learnerLevel",
    )


class GenerateExercisesRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    target: ExerciseTargetPayload
    count: int = Field(default=3, ge=1, le=3)
    exercise_types: list[ExerciseType] | None = Field(
        default=None,
        validation_alias=AliasChoices("exerciseTypes", "exercise_types"),
        serialization_alias="exerciseTypes",
    )
    context: GenerateExerciseContext | None = None


GENERATED_EXERCISE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "skill": {"type": "string", "enum": ["grammar", "vocabulary", "reading"]},
                    "type": {"type": "string", "enum": ["single_choice", "fill_blank"]},
                    "prompt": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "correctAnswer": {"type": "string"},
                    "acceptedAnswers": {"type": "array", "items": {"type": "string"}},
                    "explanation": {"type": "string"},
                    "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
                    "metadata": {"type": "object"},
                },
                "required": [
                    "skill",
                    "type",
                    "prompt",
                    "correctAnswer",
                    "explanation",
                    "difficulty",
                ],
                "additionalProperties": True,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


@router.get("")
async def list_exercises_for_target(
    learner_id: uuid.UUID,
    target_type: ExerciseTargetType = Query(),
    target_id: str = Query(min_length=1),
    limit: int = Query(default=12, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    await _ensure_learner_exists(db, learner_id)
    if target_type != "curriculum_node":
        return []

    curriculum_node_id = _parse_uuid(target_id, "target_id must be a valid curriculum node id")
    result = await db.execute(select(CurriculumNode).where(CurriculumNode.id == curriculum_node_id))
    node = result.scalar_one_or_none()
    if node is None:
        raise HTTPException(status_code=404, detail="Curriculum node not found")

    questions = await ensure_unit_exercises(
        db,
        source_id=node.source_id,
        curriculum_node_id=node.id,
    )
    return [
        exercise_question_to_item(question, target_label=node.title)
        for question in questions[:limit]
    ]


@router.post("/generate")
async def generate_exercises(
    learner_id: uuid.UUID,
    body: GenerateExercisesRequest,
    db: AsyncSession = Depends(get_db_session),
    model_router: ModelRouter = Depends(get_model_router),
) -> list[dict[str, Any]]:
    await _ensure_learner_exists(db, learner_id)
    prompt = _build_generation_prompt(body)
    try:
        response = await model_router.chat(
            ChatRequest(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是 BinnAgent 的英语练习题生成器。"
                            "只输出符合 schema 的 JSON，不要输出 Markdown。"
                            "题目必须严格围绕 target，不要生成超出知识点范围的题。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                task_type="exercise_generate",
                temperature=0.2,
                max_tokens=1800,
                response_schema=GENERATED_EXERCISE_SCHEMA,
                preferred_model=settings.ollama_utility_model,
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="AI 练习生成暂时不可用") from exc

    structured = response.structured
    if not isinstance(structured, dict):
        raise HTTPException(status_code=502, detail="AI 练习生成结果格式错误")
    raw_items = structured.get("items")
    if not isinstance(raw_items, list):
        raise HTTPException(status_code=502, detail="AI 练习生成结果缺少题目")
    return [
        _normalize_generated_item(item, target=body.target, index=index)
        for index, item in enumerate(raw_items[: body.count], start=1)
        if isinstance(item, dict)
    ]


async def _ensure_learner_exists(db: AsyncSession, learner_id: uuid.UUID) -> None:
    result = await db.execute(select(Learner.id).where(Learner.id == learner_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Learner not found")


def _parse_uuid(value: str, error: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=error) from exc


def _build_generation_prompt(body: GenerateExercisesRequest) -> str:
    target = body.target
    types = ", ".join(body.exercise_types or ["single_choice", "fill_blank"])
    context = body.context
    context_lines: list[str] = []
    if context is not None:
        if context.page:
            context_lines.append(f"页面：{context.page}")
        if context.learner_level:
            context_lines.append(f"学习者水平：{context.learner_level}")
        if context.explanation:
            context_lines.append(f"知识点说明：{context.explanation}")
        if context.examples:
            context_lines.append("例子：" + " / ".join(context.examples[:8]))
    return (
        f"请生成 {body.count} 道英语学习验收题。\n"
        f"target.type: {target.type}\n"
        f"target.id: {target.id}\n"
        f"target.label: {target.label}\n"
        f"允许题型：{types}\n"
        f"上下文：\n{chr(10).join(context_lines) if context_lines else '无'}\n\n"
        "要求：\n"
        "1. 每道题必须验收当前 target，不要泛泛出题。\n"
        "2. grammar_topic 侧重语法选择/填空；vocabulary_item 侧重词义、搭配、句中用法；"
        "word_part 侧重词根词缀意义和拆词；reading_passage 侧重主旨、细节、句子理解；"
        "curriculum_node 侧重单元知识验收。\n"
        "3. single_choice 必须给 4 个 options，correctAnswer 必须等于其中一个选项。\n"
        "4. fill_blank 的 options 可以为空，acceptedAnswers 给 1-3 个可接受答案。\n"
        "5. explanation 用中文解释为什么答案正确。\n"
    )


def _normalize_generated_item(
    item: dict[str, Any],
    *,
    target: ExerciseTargetPayload,
    index: int,
) -> dict[str, Any]:
    exercise_type = item.get("type") if item.get("type") in ("single_choice", "fill_blank") else "fill_blank"
    options = _string_list(item.get("options"))
    correct_answer = str(item.get("correctAnswer") or item.get("correct_answer") or "").strip()
    if exercise_type == "single_choice":
        options = options[:4]
        if correct_answer and correct_answer not in options:
            options = [correct_answer, *options]
        options = options[:4]
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    return {
        "id": f"generated-{target.type}-{target.id}-{uuid.uuid4().hex[:10]}-{index}",
        "target": target.model_dump(),
        "skill": _skill_for_target(target.type, item.get("skill")),
        "type": exercise_type,
        "prompt": str(item.get("prompt") or "").strip(),
        "options": options,
        "correctAnswer": correct_answer,
        "acceptedAnswers": _string_list(item.get("acceptedAnswers") or item.get("accepted_answers")),
        "explanation": str(item.get("explanation") or "").strip(),
        "difficulty": item.get("difficulty") if item.get("difficulty") in ("easy", "medium", "hard") else "easy",
        "source": {
            "type": "generated",
            "name": "ai_generated",
        },
        "metadata": {
            **metadata,
            "generatedBy": "ai",
            "targetType": target.type,
            "targetId": target.id,
        },
    }


def _skill_for_target(target_type: ExerciseTargetType, value: Any) -> str:
    if value in ("grammar", "vocabulary", "reading"):
        return str(value)
    if target_type == "grammar_topic":
        return "grammar"
    if target_type == "reading_passage":
        return "reading"
    return "vocabulary"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
