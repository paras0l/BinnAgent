import random
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.knowledge import ExerciseQuestion, KnowledgePoint


def _distractors(point: KnowledgePoint, peers: list[KnowledgePoint]) -> list[str]:
    values = [peer.title for peer in peers if peer.id != point.id and peer.title != point.title]
    values.extend(["以上都不正确", "需要结合更多上下文判断"])
    return values[:3]


async def ensure_unit_exercises(
    db: AsyncSession,
    *,
    source_id: uuid.UUID,
    curriculum_node_id: uuid.UUID,
) -> list[ExerciseQuestion]:
    existing_result = await db.execute(
        select(ExerciseQuestion)
        .where(
            ExerciseQuestion.curriculum_node_id == curriculum_node_id,
            ExerciseQuestion.status == "published",
        )
        .order_by(ExerciseQuestion.created_at)
    )
    existing = list(existing_result.scalars().all())
    if existing:
        return existing

    point_result = await db.execute(
        select(KnowledgePoint)
        .where(
            KnowledgePoint.curriculum_node_id == curriculum_node_id,
            KnowledgePoint.status.in_(("published", "draft")),
        )
        .order_by(KnowledgePoint.created_at)
        .limit(8)
    )
    points = list(point_result.scalars().all())
    questions: list[ExerciseQuestion] = []
    for point in points[:5]:
        distractors = _distractors(point, points)
        options = [point.title, *distractors]
        random.Random(str(point.id)).shuffle(options)
        question = ExerciseQuestion(
            source_id=source_id,
            curriculum_node_id=curriculum_node_id,
            knowledge_point_id=point.id,
            question_type="multiple_choice",
            stem=f"下列哪一项最符合这个教材知识点：{point.summary}",
            options=options,
            answer=point.title,
            explanation=f"教材知识点「{point.title}」：{point.summary}",
            difficulty=point.difficulty,
            status="published",
            metadata_={"generator": "knowledge-point-template-v1"},
        )
        db.add(question)
        questions.append(question)
    await db.flush()
    return questions
