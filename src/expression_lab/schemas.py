from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


InputType = Literal["zh_intent", "en_draft", "good_sentence", "learning_target"]
ActionType = Literal[
    "save_writing_phrase",
    "save_vocabulary",
    "save_grammar_point",
    "create_practice",
    "copy_expression",
    "dismiss_suggestion",
    "mark_completed",
]
PracticeType = Literal[
    "translation",
    "rewrite",
    "natural_choice",
    "fill_blank",
    "scenario_choice",
    "sentence_building",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class BlockUi(StrictModel):
    collapsible: bool = False
    emphasis: Literal["primary", "secondary", "subtle"] = "secondary"
    initially_collapsed: bool = False


class VariantItem(StrictModel):
    id: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=600)
    chinese_explanation: str = Field(min_length=1, max_length=800)
    context: str = Field(default="通用", max_length=300)
    tone_tags: list[str] = Field(default_factory=list, max_length=6)
    naturalness: int = Field(default=80, ge=0, le=100)
    difficulty: int = Field(default=2, ge=1, le=5)
    why_it_works: str = Field(default="", max_length=900)
    use_when: str = Field(default="", max_length=600)
    avoid_when: str = Field(default="", max_length=600)
    key_pattern: str = Field(default="", max_length=600)
    example: str = Field(default="", max_length=1000)
    example_translation: str = Field(default="", max_length=1000)
    action_id: str | None = Field(default=None, max_length=120)


class ExpressionVariantsData(StrictModel):
    variants: list[VariantItem] = Field(min_length=2, max_length=5)


class TonePoint(StrictModel):
    id: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=120)
    expression: str = Field(min_length=1, max_length=600)
    position: int = Field(ge=0, le=100)
    explanation: str = Field(default="", max_length=500)


class ToneSpectrumData(StrictModel):
    dimension: Literal["directness", "formality", "strength", "warmth"] = "directness"
    left_label: str = Field(default="委婉", max_length=80)
    right_label: str = Field(default="直接", max_length=80)
    points: list[TonePoint] = Field(min_length=2, max_length=7)


class SentenceChange(StrictModel):
    operation: Literal["add", "delete", "replace", "keep"]
    original: str = Field(default="", max_length=500)
    replacement: str = Field(default="", max_length=500)
    explanation: str = Field(min_length=1, max_length=700)


class SentenceDiffData(StrictModel):
    original: str = Field(min_length=1, max_length=1200)
    corrected: str = Field(min_length=1, max_length=1200)
    changes: list[SentenceChange] = Field(min_length=1, max_length=20)
    summary: str = Field(default="", max_length=800)


class DiagramNode(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=240)
    kind: Literal["fixed", "slot", "connector", "example"] = "slot"


class DiagramEdge(StrictModel):
    source: str = Field(min_length=1, max_length=80)
    target: str = Field(min_length=1, max_length=80)
    label: str = Field(default="", max_length=120)


class PatternDiagramData(StrictModel):
    pattern: str = Field(min_length=1, max_length=1000)
    nodes: list[DiagramNode] = Field(min_length=1, max_length=20)
    edges: list[DiagramEdge] = Field(default_factory=list, max_length=30)
    example: str = Field(default="", max_length=1000)
    svg: str | None = Field(default=None, max_length=40_000)


class UsageItem(StrictModel):
    id: str = Field(min_length=1, max_length=120)
    expression: str = Field(min_length=1, max_length=500)
    meaning: str = Field(min_length=1, max_length=600)
    register_level: str = Field(alias="register", min_length=1, max_length=120)
    context: str = Field(min_length=1, max_length=400)
    common_collocations: list[str] = Field(default_factory=list, max_length=8)
    avoid_when: str = Field(default="", max_length=500)


class UsageComparisonData(StrictModel):
    items: list[UsageItem] = Field(min_length=2, max_length=6)


class VocabularyEntry(StrictModel):
    id: str = Field(min_length=1, max_length=120)
    word: str = Field(min_length=1, max_length=255)
    meaning: str = Field(min_length=1, max_length=700)
    collocations: list[str] = Field(default_factory=list, max_length=10)
    examples: list[str] = Field(default_factory=list, max_length=6)
    synonyms: list[str] = Field(default_factory=list, max_length=8)
    action_id: str | None = Field(default=None, max_length=120)


class VocabularyFocusData(StrictModel):
    entries: list[VocabularyEntry] = Field(min_length=1, max_length=8)


class MinimalPair(StrictModel):
    wrong: str = Field(min_length=1, max_length=600)
    correct: str = Field(min_length=1, max_length=600)
    explanation: str = Field(default="", max_length=700)


class GrammarFocusData(StrictModel):
    topic: str = Field(min_length=1, max_length=255)
    rule: str = Field(min_length=1, max_length=1600)
    error: str = Field(default="", max_length=800)
    correction: str = Field(default="", max_length=800)
    minimal_pairs: list[MinimalPair] = Field(min_length=1, max_length=6)
    action_id: str | None = Field(default=None, max_length=120)


class PracticeQuestion(StrictModel):
    id: str = Field(min_length=1, max_length=120)
    type: PracticeType
    prompt: str = Field(min_length=1, max_length=1200)
    options: list[str] = Field(default_factory=list, max_length=8)
    answer: str = Field(min_length=1, max_length=1200)
    accepted_answers: list[str] = Field(default_factory=list, max_length=12)
    target_expression: str | None = Field(default=None, max_length=600)
    hint: str = Field(default="回到场景，先想你真正要表达的意思。", max_length=700)
    explanation: str = Field(default="", max_length=1000)
    skill: Literal["writing", "grammar", "vocabulary"] = "writing"


class MicroPracticeData(StrictModel):
    instructions: str = Field(default="完成下面的小练习", max_length=500)
    questions: list[PracticeQuestion] = Field(min_length=1, max_length=3)


class TransferSlot(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    placeholder: str = Field(default="", max_length=240)
    examples: list[str] = Field(default_factory=list, max_length=6)


class TransferBuilderData(StrictModel):
    template: str = Field(min_length=1, max_length=1200)
    slots: list[TransferSlot] = Field(min_length=1, max_length=8)
    example: str = Field(min_length=1, max_length=1200)
    preview_prefix: str = Field(default="", max_length=300)


class SandboxWidgetData(StrictModel):
    html: str = Field(default="", max_length=40_000)
    css: str = Field(default="", max_length=30_000)
    javascript: str = Field(default="", max_length=30_000)
    allowed_events: list[
        Literal[
            "selection_changed",
            "answer_submitted",
            "interaction",
            "action",
            "answer",
            "change",
        ]
    ] = (
        Field(default_factory=list, max_length=6)
    )
    height: int = Field(default=320, ge=160, le=720)
    timeout_ms: int = Field(default=5000, ge=500, le=10_000)


class BaseBlock(StrictModel):
    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=700)
    ui: BlockUi = Field(default_factory=BlockUi)


class ExpressionVariantsBlock(BaseBlock):
    type: Literal["expression_variants"]
    data: ExpressionVariantsData


class ToneSpectrumBlock(BaseBlock):
    type: Literal["tone_spectrum"]
    data: ToneSpectrumData


class SentenceDiffBlock(BaseBlock):
    type: Literal["sentence_diff"]
    data: SentenceDiffData


class PatternDiagramBlock(BaseBlock):
    type: Literal["pattern_diagram"]
    data: PatternDiagramData


class UsageComparisonBlock(BaseBlock):
    type: Literal["usage_comparison"]
    data: UsageComparisonData


class VocabularyFocusBlock(BaseBlock):
    type: Literal["vocabulary_focus"]
    data: VocabularyFocusData


class GrammarFocusBlock(BaseBlock):
    type: Literal["grammar_focus"]
    data: GrammarFocusData


class MicroPracticeBlock(BaseBlock):
    type: Literal["micro_practice"]
    data: MicroPracticeData


class TransferBuilderBlock(BaseBlock):
    type: Literal["transfer_builder"]
    data: TransferBuilderData


class SandboxWidgetBlock(BaseBlock):
    type: Literal["sandbox_widget"]
    data: SandboxWidgetData


ExpressionBlock = Annotated[
    Union[
        ExpressionVariantsBlock,
        ToneSpectrumBlock,
        SentenceDiffBlock,
        PatternDiagramBlock,
        UsageComparisonBlock,
        VocabularyFocusBlock,
        GrammarFocusBlock,
        MicroPracticeBlock,
        TransferBuilderBlock,
        SandboxWidgetBlock,
    ],
    Field(discriminator="type"),
]


class SaveWritingPhrasePayload(StrictModel):
    text: str = Field(min_length=1, max_length=1200)
    chinese_meaning: str = Field(default="", max_length=1200)
    explanation: str = Field(default="", max_length=1600)
    usage_scene: str = Field(default="", max_length=600)
    register_level: str | None = Field(default=None, alias="register", max_length=80)
    template: str | None = Field(default=None, max_length=1000)
    examples: list[str] = Field(default_factory=list, max_length=8)
    tags: list[str] = Field(default_factory=list, max_length=12)


class SaveVocabularyPayload(StrictModel):
    word: str = Field(min_length=1, max_length=255)
    meaning: str = Field(default="", max_length=1000)
    collocations: list[str] = Field(default_factory=list, max_length=12)
    examples: list[str] = Field(default_factory=list, max_length=8)
    source_expression: str = Field(default="", max_length=1200)
    reason: str = Field(default="Expression Lab 推荐", max_length=500)


class SaveGrammarPointPayload(StrictModel):
    topic: str = Field(min_length=1, max_length=255)
    rule: str = Field(min_length=1, max_length=1800)
    error: str = Field(default="", max_length=1000)
    correction: str = Field(default="", max_length=1000)
    minimal_pairs: list[MinimalPair] = Field(default_factory=list, max_length=8)


class CreatePracticePayload(StrictModel):
    count: int = Field(default=1, ge=1, le=3)
    focus: str = Field(default="", max_length=500)


class CopyExpressionPayload(StrictModel):
    text: str = Field(min_length=1, max_length=1200)


class DismissSuggestionPayload(StrictModel):
    reason: str = Field(default="", max_length=500)


class MarkCompletedPayload(StrictModel):
    note: str = Field(default="", max_length=500)


class BaseLearningAction(StrictModel):
    id: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=160)
    block_id: str | None = Field(default=None, max_length=120)
    requires_confirmation: bool = False
    editable_fields: list[str] = Field(default_factory=list, max_length=12)


class SaveWritingPhraseAction(BaseLearningAction):
    type: Literal["save_writing_phrase"]
    payload: SaveWritingPhrasePayload
    requires_confirmation: bool = True


class SaveVocabularyAction(BaseLearningAction):
    type: Literal["save_vocabulary"]
    payload: SaveVocabularyPayload
    requires_confirmation: bool = True


class SaveGrammarPointAction(BaseLearningAction):
    type: Literal["save_grammar_point"]
    payload: SaveGrammarPointPayload
    requires_confirmation: bool = True


class CreatePracticeAction(BaseLearningAction):
    type: Literal["create_practice"]
    payload: CreatePracticePayload = Field(default_factory=CreatePracticePayload)


class CopyExpressionAction(BaseLearningAction):
    type: Literal["copy_expression"]
    payload: CopyExpressionPayload


class DismissSuggestionAction(BaseLearningAction):
    type: Literal["dismiss_suggestion"]
    payload: DismissSuggestionPayload = Field(default_factory=DismissSuggestionPayload)


class MarkCompletedAction(BaseLearningAction):
    type: Literal["mark_completed"]
    payload: MarkCompletedPayload = Field(default_factory=MarkCompletedPayload)


LearningAction = Annotated[
    Union[
        SaveWritingPhraseAction,
        SaveVocabularyAction,
        SaveGrammarPointAction,
        CreatePracticeAction,
        CopyExpressionAction,
        DismissSuggestionAction,
        MarkCompletedAction,
    ],
    Field(discriminator="type"),
]


class ExpressionSource(StrictModel):
    type: Literal["manual", "group_learning_signal"] = "manual"
    source_id: str | None = Field(default=None, max_length=255)


class ExpressionIntent(StrictModel):
    input_type: InputType
    text: str = Field(min_length=1, max_length=4000)
    context: str | None = Field(default=None, max_length=120)
    goal: str | None = Field(default=None, max_length=120)


class SuggestedAsset(StrictModel):
    type: Literal["writing_phrase", "vocabulary", "grammar_point", "practice"]
    label: str = Field(min_length=1, max_length=160)
    action_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=500)


class ExpressionUiSpec(StrictModel):
    version: Literal["expression_ui.v1"] = "expression_ui.v1"
    session_id: str
    source: ExpressionSource
    intent: ExpressionIntent
    layout: str = Field(default="adaptive", min_length=1, max_length=80)
    blocks: list[ExpressionBlock] = Field(min_length=1, max_length=20)
    suggested_assets: list[SuggestedAsset] = Field(default_factory=list, max_length=20)
    learning_actions: list[LearningAction] = Field(default_factory=list, max_length=30)
    fallback_message: str | None = Field(default=None, max_length=1200)

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        try:
            return str(uuid.UUID(value))
        except ValueError as exc:
            raise ValueError("session_id must be a UUID") from exc


class CreateSessionRequest(StrictModel):
    input_type: InputType
    text: str = Field(min_length=1, max_length=4000)
    context: str | None = Field(default=None, max_length=120)
    style: str | None = Field(default=None, max_length=120)
    current_level: str | None = Field(
        default=None,
        max_length=40,
        validation_alias=AliasChoices("current_level", "level"),
        serialization_alias="level",
    )
    needs_practice: bool = Field(
        default=True,
        validation_alias=AliasChoices("needs_practice", "include_practice"),
        serialization_alias="include_practice",
    )
    source_signal_id: uuid.UUID | None = None


class CreateSessionResponse(StrictModel):
    session_id: uuid.UUID
    status: Literal["generating"] = "generating"


class RegenerateSessionRequest(StrictModel):
    instruction: str | None = Field(default=None, max_length=1000)


class RegenerateBlockRequest(StrictModel):
    instruction: str | None = Field(default=None, max_length=1000)


class AttemptRequest(StrictModel):
    block_id: str = Field(min_length=1, max_length=120)
    question_id: str = Field(min_length=1, max_length=120)
    answer: str | dict[str, Any]
    response_time_ms: int | None = Field(default=None, ge=0, le=3_600_000)


class AttemptResponse(StrictModel):
    attempt_id: uuid.UUID
    score: float = Field(ge=0, le=100)
    is_correct: bool
    feedback: dict[str, Any]
    next_recommendations: list[dict[str, Any]]


class ActionRequest(StrictModel):
    confirmed: bool = False
    edits: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("edits", "payload_overrides"),
        serialization_alias="payload_overrides",
    )


class ActionResponse(StrictModel):
    action_id: uuid.UUID
    status: str
    applied_target: dict[str, str] | None = None
    applied_target_type: str | None = None
    applied_target_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class EventRequest(StrictModel):
    event_type: Literal["block_viewed", "source_opened", "sandbox_interaction"]
    payload: dict[str, Any] = Field(default_factory=dict)


class SessionSummary(StrictModel):
    session_id: uuid.UUID
    status: str
    input_type: str
    input_text: str
    context: str | None
    style_goal: str | None
    source_type: str
    source_ref: str | None
    source: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class SessionDetail(SessionSummary):
    level: str | None = None
    current_level: str | None = None
    include_practice: bool = True
    needs_practice: bool = True
    ui_spec: dict[str, Any] | None
    actions: list[dict[str, Any]]
    attempts: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    diagnostics: dict[str, Any]
    error_message: str | None = None


class SessionListResponse(StrictModel):
    sessions: list[SessionSummary] = Field(serialization_alias="items")
    pending_count: int = 0


EXPRESSION_UI_SCHEMA = ExpressionUiSpec.model_json_schema()


ALLOWED_BLOCK_TYPES = frozenset(
    {
        "expression_variants",
        "tone_spectrum",
        "sentence_diff",
        "pattern_diagram",
        "usage_comparison",
        "vocabulary_focus",
        "grammar_focus",
        "micro_practice",
        "transfer_builder",
        "sandbox_widget",
    }
)
ALLOWED_ACTION_TYPES = frozenset(
    {
        "save_writing_phrase",
        "save_vocabulary",
        "save_grammar_point",
        "create_practice",
        "copy_expression",
        "dismiss_suggestion",
        "mark_completed",
    }
)
SAVE_ACTION_TYPES = frozenset(
    {"save_writing_phrase", "save_vocabulary", "save_grammar_point"}
)
