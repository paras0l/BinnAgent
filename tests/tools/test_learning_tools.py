import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.models.adaptive import LearningEvidenceEvent
from src.models.knowledge import GrammarCanDoProfile, KnowledgePoint
from src.tools.catalog import ToolCatalogManager
from src.tools.learning_tools import (
    AnalyzeLearnerResponseInput,
    LearningObservationInput,
    RecordLearningEvidenceInput,
    _score_candidate,
    analyze_learner_response,
    record_learning_evidence,
)
from src.tools.types import ToolExecutionInput


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


def _reported_question_candidate() -> tuple[GrammarCanDoProfile, KnowledgePoint]:
    point = KnowledgePoint(
        canonical_key="grammar.egp.1147",
        type="grammar_can_do",
        title="wonder reported thought",
        summary="reported thought",
        source_page="catalog:egp",
        difficulty=0.5,
        status="published",
        content={},
    )
    point.id = uuid.uuid4()
    profile = GrammarCanDoProfile(
        knowledge_point_id=point.id,
        external_id=1147,
        category="REPORTED SPEECH",
        subcategory="reported speech",
        cefr_level="B1",
        construct_type="FORM/USE",
        can_do_statement=(
            "Can report thought using 'wonder' + 'wh-'word + clause, "
            "with a tense shift where relevant."
        ),
        success_criteria=[],
        failure_criteria=[],
        positive_examples=["I wondered what she had written."],
        negative_examples=[],
        prerequisites=[],
        detection_hints={},
        catalog_version="egp-v1",
    )
    return profile, point


def _analysis(learner_answer: str):
    return analyze_learner_response(
        AnalyzeLearnerResponseInput(
            question_id="q-1",
            question="Correct the sentence.",
            expected_answer="They wondered whether the train would arrive on time.",
            learner_answer=learner_answer,
            linked_can_do_ids=["egp:1147"],
        )
    )


def test_can_do_ranking_preserves_whether_wh_terminology_mismatch() -> None:
    profile, point = _reported_question_candidate()

    candidate = _score_candidate(
        "They wondered whether the train would arrive on time.", profile, point
    )

    assert candidate.score >= 0.65
    assert "terminology mismatch" in candidate.reason


def test_response_analysis_separates_atomic_errors() -> None:
    result = _analysis("They wondered whether will the train arrive on time.")

    assert result["overall_outcome"] == "UNSUCCESSFUL"
    assert {item["id"] for item in result["atomic_kcs"]} == {
        "grammar.reported_question.word_order",
        "grammar.reported_speech.backshift",
    }
    assert result["observations"][0]["evidence"]["spans"]


@pytest.mark.parametrize(
    ("answer", "outcome"),
    [
        ("They wondered whether the train would arrive on time.", "SUCCESS"),
        ("I don't know", "NO_ATTEMPT"),
        ("They wondered whether the train would arrive in time.", "UNRELATED_ERROR"),
    ],
)
def test_response_analysis_uses_four_way_outcomes(answer: str, outcome: str) -> None:
    assert _analysis(answer)["overall_outcome"] == outcome


@pytest.mark.asyncio
async def test_catalog_exposes_five_learning_tools_and_injects_learner_context() -> None:
    manager = ToolCatalogManager()
    view = await manager.refresh()
    by_name = {tool.name: tool for tool in view.tools}

    expected = {
        "find_can_do_for_item",
        "find_can_do_for_query",
        "analyze_learner_response",
        "get_learner_knowledge_state",
        "record_learning_evidence",
    }
    assert expected <= by_name.keys()
    assert "learner_id" not in by_name["record_learning_evidence"].input_schema["properties"]
    assert by_name["record_learning_evidence"].injected_fields == ["db", "learner_id"]
    assert by_name["record_learning_evidence"].idempotency == "keyed"

    result = await manager.execute(
        ToolExecutionInput(
            tool_name="analyze_learner_response",
            allowed_tools=["analyze_learner_response"],
            payload={
                "question_id": "q-1",
                "question": "Correct it",
                "expected_answer": "They wondered whether the train would arrive.",
                "learner_answer": "They wondered whether will the train arrive.",
                "linked_can_do_ids": ["egp:1147"],
            },
        )
    )

    assert result.status == "success"
    assert result.output["overall_outcome"] == "UNSUCCESSFUL"


@pytest.mark.asyncio
async def test_record_learning_evidence_replay_does_not_update_state_twice() -> None:
    learner_id = uuid.uuid4()
    event = LearningEvidenceEvent(
        learner_id=learner_id,
        event_id="event-1",
        source="dialogue",
        observations=[],
        raw_evidence={},
        matcher_model_version="can-do-hybrid-rules-v1",
        status="applied",
        result={"event_id": "event-1", "status": "applied", "observation_results": []},
    )
    event.id = uuid.uuid4()
    event.created_at = datetime.now(timezone.utc)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=FakeResult(event))
    payload = RecordLearningEvidenceInput(
        source="dialogue",
        event_id="event-1",
        observations=[
            LearningObservationInput(
                knowledge_id="grammar.reported_question.word_order",
                outcome="UNSUCCESSFUL",
                confidence=0.97,
            )
        ],
    )

    result = await record_learning_evidence(db, learner_id, payload)

    assert result["idempotent_replay"] is True
    db.add.assert_not_called()
    db.flush.assert_not_awaited()
