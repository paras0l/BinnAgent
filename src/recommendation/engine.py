import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.evidence.types import EvidenceRef
from src.models.knowledge import CurriculumNode, LearnerKnowledgeState
from src.models.vocabulary import ReviewSchedule
from src.recommendation.types import RecommendationInput, RecommendationPlan, RecommendationTask
from src.runtime.task_spec import SuccessCriteria, TaskSpec, TaskTarget, VerificationPolicy


class RecommendationEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_daily_plan(self, input: RecommendationInput) -> RecommendationPlan:
        tasks: list[RecommendationTask] = []
        tasks.extend(await self.rank_due_reviews(input))
        tasks.extend(await self.rank_weak_points(input))
        current_task = await self._current_curriculum_task(input)
        if current_task is not None:
            tasks.append(current_task)

        tasks = sorted(tasks, key=lambda task: (-task.priority_score, task.task_spec.task_id))
        if input.time_budget_minutes:
            tasks = _fit_time_budget(tasks, input.time_budget_minutes)
        mode = input.mode_hint or _infer_mode(tasks)
        return RecommendationPlan(
            plan_id=f"plan:{uuid.uuid4()}",
            learner_id=input.learner_id,
            mode=mode,
            reason=self.explain_recommendation(tasks, mode),
            confidence=0.75 if tasks else 0.35,
            tasks=tasks,
            evidence_refs=_dedupe_refs([ref for task in tasks for ref in task.evidence_refs]),
            generated_at=datetime.now(timezone.utc),
        )

    async def recommend_next_action(
        self,
        input: RecommendationInput,
    ) -> RecommendationTask | None:
        plan = await self.build_daily_plan(input)
        return plan.tasks[0] if plan.tasks else None

    async def rank_weak_points(self, input: RecommendationInput) -> list[RecommendationTask]:
        learner_id = _safe_uuid(input.learner_id)
        if learner_id is None:
            return []
        result = await self.db.execute(
            select(LearnerKnowledgeState)
            .where(
                LearnerKnowledgeState.learner_id == learner_id,
                LearnerKnowledgeState.mastery_score < 0.6,
            )
            .order_by(LearnerKnowledgeState.mastery_score.asc(), LearnerKnowledgeState.updated_at.desc())
            .limit(5)
        )
        tasks: list[RecommendationTask] = []
        for state in result.scalars().all():
            evidence = EvidenceRef(
                evidence_type="knowledge_point",
                evidence_id=str(state.knowledge_point_id),
                confidence=state.confidence or 0.6,
                reason="low mastery score",
                used_by="recommendation",
            )
            weakness_score = 1.0 - (state.mastery_score or 0.0)
            forgetting_risk = 1.0 if state.next_review_at and state.next_review_at <= datetime.now(timezone.utc) else 0.3
            priority = round(
                weakness_score * 0.35
                + forgetting_risk * 0.25
                + 0.2
                + 0.1
                + _preference_match(input) * 0.1,
                4,
            )
            tasks.append(
                RecommendationTask(
                    task_spec=_task_spec(
                        task_id=f"repair:{state.knowledge_point_id}",
                        task_type="repair_weakness",
                        source="recommendation",
                        objective="修复低掌握度知识点",
                        target_type="knowledge_point",
                        target_id=str(state.knowledge_point_id),
                        allowed_tools=["mastery.update", "memory.retrieve", "exercise.grade"],
                        evidence_refs=[evidence],
                    ),
                    priority_score=priority,
                    reason=f"掌握度 {state.mastery_score:.2f}，建议优先修复。",
                    evidence_refs=[evidence],
                    estimated_minutes=8,
                )
            )
        return tasks

    async def rank_due_reviews(self, input: RecommendationInput) -> list[RecommendationTask]:
        learner_id = _safe_uuid(input.learner_id)
        if learner_id is None:
            return []
        result = await self.db.execute(
            select(ReviewSchedule)
            .where(
                ReviewSchedule.learner_id == learner_id,
                ReviewSchedule.completed_at.is_(None),
                ReviewSchedule.scheduled_at <= datetime.now(timezone.utc),
            )
            .order_by(ReviewSchedule.scheduled_at.asc())
            .limit(5)
        )
        tasks: list[RecommendationTask] = []
        for review in result.scalars().all():
            target_type = "knowledge_point" if review.item_type == "knowledge" else review.item_type
            evidence = EvidenceRef(
                evidence_type="knowledge_point" if review.item_type == "knowledge" else "review_schedule",
                evidence_id=str(review.item_id if review.item_type == "knowledge" else review.id),
                reason="due review",
                used_by="recommendation",
            )
            tasks.append(
                RecommendationTask(
                    task_spec=_task_spec(
                        task_id=f"review:{review.id}",
                        task_type="review_due_item",
                        source="recommendation",
                        objective="完成到期复习",
                        target_type=target_type,
                        target_id=str(review.item_id),
                        allowed_tools=["review.schedule", "exercise.grade", "memory.retrieve"],
                        evidence_refs=[evidence],
                    ),
                    priority_score=0.8,
                    reason="复习已到期，优先防止遗忘。",
                    evidence_refs=[evidence],
                    estimated_minutes=6,
                )
            )
        return tasks

    def explain_recommendation(self, tasks: list[RecommendationTask], mode: str) -> str:
        if not tasks:
            return "暂无到期复习或薄弱项，保持教材顺序学习。"
        top = tasks[0]
        return f"{mode} 模式：{top.reason}"

    async def _current_curriculum_task(
        self,
        input: RecommendationInput,
    ) -> RecommendationTask | None:
        node_id = _safe_uuid(input.current_curriculum_node_id)
        if node_id is None:
            return None
        result = await self.db.execute(select(CurriculumNode).where(CurriculumNode.id == node_id))
        node = result.scalar_one_or_none()
        label = node.title if node is not None else "当前教材单元"
        evidence = EvidenceRef(
            evidence_type="knowledge_point",
            evidence_id=str(node_id),
            confidence=0.5,
            reason="current curriculum node",
            used_by="recommendation",
            metadata={"target_type": "curriculum_node"},
        )
        return RecommendationTask(
            task_spec=_task_spec(
                task_id=f"curriculum:{node_id}",
                task_type="learn_knowledge_point",
                source="recommendation",
                objective=f"按教材顺序学习 {label}",
                target_type="curriculum_node",
                target_id=str(node_id),
                allowed_tools=["rag.retrieve", "exercise.grade", "mastery.update"],
                evidence_refs=[evidence],
            ),
            priority_score=0.45,
            reason=f"继续当前教材节点：{label}。",
            evidence_refs=[evidence],
            estimated_minutes=node.estimated_minutes if node is not None else 10,
        )


def _task_spec(
    *,
    task_id: str,
    task_type: str,
    source: str,
    objective: str,
    target_type: str,
    target_id: str,
    allowed_tools: list[str],
    evidence_refs: list[EvidenceRef],
) -> TaskSpec:
    return TaskSpec(
        task_id=task_id,
        task_type=task_type,
        source=source,
        objective=objective,
        target=TaskTarget(target_type=target_type, target_id=target_id, label=objective),
        difficulty=None,
        allowed_tools=allowed_tools,
        success_criteria=SuccessCriteria(min_accuracy=0.8, requires_explanation=True),
        verification_policy=VerificationPolicy(
            required_checks=["episode_started", "exercise_graded", "mastery_update_valid"],
            require_evidence=True,
        ),
        metadata={"evidence_refs": [ref.model_dump(mode="json") for ref in evidence_refs]},
    )


def _safe_uuid(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _fit_time_budget(
    tasks: list[RecommendationTask],
    time_budget_minutes: int,
) -> list[RecommendationTask]:
    selected: list[RecommendationTask] = []
    used = 0
    for task in tasks:
        minutes = task.estimated_minutes or 5
        if selected and used + minutes > time_budget_minutes:
            continue
        selected.append(task)
        used += minutes
    return selected


def _infer_mode(tasks: list[RecommendationTask]) -> str:
    if not tasks:
        return "textbook_guided"
    top_type = tasks[0].task_spec.task_type
    if top_type == "review_due_item":
        return "review"
    if top_type == "repair_weakness":
        return "weakness_repair"
    return "textbook_guided"


def _preference_match(input: RecommendationInput) -> float:
    return 1.0 if input.mode_hint in {"weakness_repair", "review", "textbook_guided"} else 0.0


def _dedupe_refs(refs: list[EvidenceRef]) -> list[EvidenceRef]:
    seen: set[tuple[str, str]] = set()
    result: list[EvidenceRef] = []
    for ref in refs:
        key = (ref.evidence_type, ref.evidence_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(ref)
    return result
