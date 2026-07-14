from typing import Literal

from pydantic import BaseModel, Field


class TeachingPolicy(BaseModel):
    target_knowledge_points: list[str]
    difficulty_band: tuple[float, float]
    support_level: Literal["guided", "delayed_hint", "minimal"]
    evidence_mode: Literal["recall", "production"]
    practice_form: Literal["focused_recall", "near_transfer", "novel_transfer"]
    max_new_concepts: int = 1
    required_checks: list[str] = Field(
        default_factory=lambda: ["target_alignment", "difficulty_match"]
    )
    compiler_version: str = "teaching-policy-v1"


class TeachingPolicyCompiler:
    def compile(
        self,
        *,
        knowledge_point_id: str,
        mastery: float,
        retrievability: float,
        production: float = 0.0,
        dkt_prediction: float | None = None,
        dkt_enabled: bool = False,
    ) -> TeachingPolicy:
        effective = dkt_prediction if dkt_enabled and dkt_prediction is not None else mastery
        if effective < 0.35:
            return TeachingPolicy(
                target_knowledge_points=[knowledge_point_id],
                difficulty_band=(0.15, 0.35),
                support_level="guided",
                evidence_mode="recall",
                practice_form="focused_recall",
            )
        if effective <= 0.75:
            return TeachingPolicy(
                target_knowledge_points=[knowledge_point_id],
                difficulty_band=(0.4, 0.65),
                support_level="delayed_hint",
                evidence_mode="recall" if production < 0.6 else "production",
                practice_form="near_transfer",
            )
        due = retrievability < 0.8
        return TeachingPolicy(
            target_knowledge_points=[knowledge_point_id],
            difficulty_band=(0.7, 0.9) if due else (0.65, 0.8),
            support_level="minimal",
            evidence_mode="production",
            practice_form="novel_transfer",
        )
