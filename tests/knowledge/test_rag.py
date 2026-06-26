import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.knowledge.rag import build_chunks, retrieve_chunks, split_text
from src.models.knowledge import CurriculumNode, KnowledgeChunk, KnowledgeSource
from src.providers.base import EmbedResponse


def test_split_text_preserves_overlap_and_content() -> None:
    chunks = split_text("abcdefghij", size=6, overlap=2)

    assert chunks == ["abcdef", "efghij"]


@pytest.mark.asyncio
async def test_build_chunks_keeps_text_when_embedding_is_unavailable() -> None:
    source = KnowledgeSource(
        title="book",
        filename="七年级英语.pdf",
        grade="grade-7",
        sha256="a" * 64,
        file_size=10,
    )
    source.id = uuid.uuid4()
    node = CurriculumNode(
        source_id=source.id,
        node_type="unit",
        title="Unit 1",
        ordinal=1,
        start_page="1",
    )
    node.id = uuid.uuid4()
    db = AsyncMock()
    db.add = MagicMock()
    router = MagicMock()
    router.embed = AsyncMock(side_effect=RuntimeError("offline"))

    count = await build_chunks(db, source, ["page one text"], [node], router)

    assert count == 1
    chunk = db.add.call_args.args[0]
    assert isinstance(chunk, KnowledgeChunk)
    assert chunk.curriculum_node_id == node.id
    assert chunk.embedding is None
    assert source.metadata_["rag_embedding_total"] == 1
    assert source.metadata_["rag_embedding_failed"] == 1
    assert source.metadata_["rag_index_status"] == "index_failed"


@pytest.mark.asyncio
async def test_retrieve_chunks_uses_vector_similarity() -> None:
    chunk = KnowledgeChunk(
        source_id=uuid.uuid4(),
        page_number=3,
        chunk_index=0,
        content="Present progressive describes an action happening now.",
        char_count=55,
        embedding_model="nomic-embed-text:latest",
    )
    chunk.id = uuid.uuid4()
    source = KnowledgeSource(
        title="book",
        filename="七年级英语.pdf",
        grade="grade-7",
        sha256="b" * 64,
        file_size=10,
        metadata_={"chunk_version": "pypdf-page-v1", "source_version": "seed-v1"},
    )
    source.id = chunk.source_id
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = [(chunk, source, 0.2)]
    db.execute = AsyncMock(return_value=result)
    router = MagicMock()
    router.embed = AsyncMock(
        return_value=EmbedResponse(
            provider="ollama",
            model="nomic-embed-text:latest",
            embeddings=[[0.0] * 768],
        )
    )

    matches = await retrieve_chunks(db, router, query="现在进行时")

    assert matches[0].chunk_id == chunk.id
    assert matches[0].score == pytest.approx(0.8)
    assert matches[0].retrieval_mode == "vector"
    assert matches[0].embedding_model == "nomic-embed-text:latest"
    assert matches[0].chunk_version == "pypdf-page-v1"
