import uuid
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base
from src.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_sources"
    __table_args__ = (
        UniqueConstraint("owner_learner_id", "sha256", name="uq_knowledge_sources_owner_sha256"),
    )

    owner_learner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    publisher: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    edition: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    grade: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    volume: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="uploaded")
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="private")
    object_key: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unit_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    knowledge_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )


class ParserRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "parser_runs"

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parser_id: Mapped[str] = mapped_column(String(120), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(80), nullable=False)
    parser_profile_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    book_manifest_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    pdf_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    input_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running", index=True)
    stage: Mapped[str] = mapped_column(String(40), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    quality_report: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    quality_score: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    artifact_refs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ParserReviewItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "parser_review_items"

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parser_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parser_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    issue_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    evidence_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    suggested_fix: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by_learner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class CurriculumNode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "curriculum_nodes"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "parent_id", "ordinal", name="uq_curriculum_source_parent_ordinal"
        ),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_nodes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    node_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ordinal: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_page: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    end_page: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    estimated_minutes: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    learning_objectives: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=list)


class KnowledgePoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_points"
    __table_args__ = (UniqueConstraint("canonical_key", name="uq_knowledge_points_canonical_key"),)

    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    curriculum_node_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_nodes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    canonical_key: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_page: Mapped[str] = mapped_column(String(30), nullable=False)
    difficulty: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="published")
    content: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)


class GrammarCanDoProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Assessment-ready metadata for a canonical grammar KnowledgePoint."""

    __tablename__ = "grammar_can_do_profiles"
    __table_args__ = (
        UniqueConstraint("knowledge_point_id", name="uq_grammar_can_do_profile_point"),
        Index("ix_grammar_can_do_category_cefr", "category", "cefr_level"),
    )

    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, unique=True)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(100), nullable=False)
    cefr_level: Mapped[str] = mapped_column(String(4), nullable=False)
    construct_type: Mapped[str] = mapped_column(String(20), nullable=False)
    guideword: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lexical_range: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    can_do_statement: Mapped[str] = mapped_column(Text, nullable=False)
    success_criteria: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    failure_criteria: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    positive_examples: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    negative_examples: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    prerequisites: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    detection_hints: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    catalog_version: Mapped[str] = mapped_column(String(40), nullable=False, default="g7-v1")
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    source_attribution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class GrammarCurriculumMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "grammar_curriculum_mappings"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_point_id",
            "curriculum_node_id",
            name="uq_grammar_curriculum_mapping",
        ),
    )

    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    curriculum_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(String(20), nullable=False, default="teaches")
    evidence_source: Mapped[str] = mapped_column(String(80), nullable=False, default="curated")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)


class KnowledgeChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("source_id", "chunk_index", name="uq_knowledge_chunk_source_index"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    curriculum_node_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(768), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )


class ExerciseQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exercise_questions"

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    curriculum_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    knowledge_point_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    question_type: Mapped[str] = mapped_column(String(30), nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[Optional[list[str]]] = mapped_column(JSONB, nullable=True, default=list)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    difficulty_prior: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    difficulty_calibrated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    difficulty_model_version: Mapped[str] = mapped_column(
        String(80), nullable=False, default="irt-prior-v1"
    )
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.72, index=True)
    quality_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="accepted", index=True
    )
    generator_version: Mapped[str] = mapped_column(
        String(80), nullable=False, default="curated-v1", index=True
    )
    quality_dimensions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="published")
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )


class ExerciseGenerationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exercise_generation_runs"
    __table_args__ = (
        Index(
            "uq_exercise_generation_runs_active_dedupe",
            "dedupe_key",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
        Index(
            "ix_exercise_generation_runs_claim",
            "status",
            "priority",
            "created_at",
        ),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    curriculum_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curriculum_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by_learner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    generator_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    requested_count: Mapped[int] = mapped_column(Integer, nullable=False, default=16)
    generated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metrics: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)


class ExerciseAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "exercise_attempts"

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exercise_questions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    submitted_answer: Mapped[str] = mapped_column(Text, nullable=False)
    correct: Mapped[bool] = mapped_column(nullable=False)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    exercise_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_label: Mapped[str] = mapped_column(String(255), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )
    source_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    should_update_mastery: Mapped[bool] = mapped_column(nullable=False, default=True)
    should_create_error_pattern: Mapped[bool] = mapped_column(nullable=False, default=False)
    should_create_memory_evidence: Mapped[bool] = mapped_column(nullable=False, default=True)


class LearnerKnowledgeState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learner_knowledge_states"
    __table_args__ = (
        UniqueConstraint("learner_id", "knowledge_point_id", name="uq_learner_knowledge_state"),
    )

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="learning")
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    predicted_success: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dkt_shadow_prediction: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    state_model_version: Mapped[str] = mapped_column(
        String(80), nullable=False, default="irt-1pl-v1"
    )
    exposure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    evidence_summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)


class KnowledgeLearningEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_learning_events"

    learner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    knowledge_point_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
