import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.evidence.resolver import EvidenceResolver, evidence_from_knowledge_point
from src.evidence.types import EvidenceRef
from src.models.knowledge import KnowledgePoint
from src.runtime.events import LearningEventCreate


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


def _knowledge_point() -> KnowledgePoint:
    point = KnowledgePoint(
        source_id=uuid.uuid4(),
        curriculum_node_id=uuid.uuid4(),
        canonical_key=f"kp:{uuid.uuid4()}",
        type="grammar",
        title="Present simple",
        summary="Use present simple for routines.",
        source_page="12",
        difficulty=0.2,
        status="published",
        content={},
    )
    point.id = uuid.uuid4()
    point.created_at = datetime.now(timezone.utc)
    point.updated_at = datetime.now(timezone.utc)
    return point


def test_evidence_ref_pydantic_validation():
    ref = EvidenceRef(evidence_type="knowledge_point", evidence_id=str(uuid.uuid4()))

    assert ref.confidence == 1.0
    assert ref.metadata == {}


@pytest.mark.asyncio
async def test_knowledge_point_evidence_can_resolve():
    point = _knowledge_point()
    db = AsyncMock()
    db.execute = AsyncMock(return_value=FakeResult(point))

    resolution = await EvidenceResolver(db).resolve_ref(evidence_from_knowledge_point(point))

    assert resolution.found is True
    assert resolution.title == "Present simple"
    assert resolution.content == "Use present simple for routines."


@pytest.mark.asyncio
async def test_missing_evidence_returns_not_found():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=FakeResult(None))

    resolution = await EvidenceResolver(db).resolve_ref(
        EvidenceRef(evidence_type="exercise_attempt", evidence_id=str(uuid.uuid4()))
    )

    assert resolution.found is False


def test_learning_event_payload_can_include_evidence_refs():
    ref = EvidenceRef(evidence_type="knowledge_point", evidence_id=str(uuid.uuid4()))

    event = LearningEventCreate(
        episode_id=str(uuid.uuid4()),
        learner_id=str(uuid.uuid4()),
        event_type="exercise_graded",
        source_module="knowledge",
        payload={"evidence_refs": [ref.model_dump(mode="json")]},
    )

    assert event.payload["evidence_refs"][0]["evidence_type"] == "knowledge_point"
