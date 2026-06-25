import re
import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.knowledge import CurriculumNode, KnowledgeChunk, KnowledgeSource
from src.observability import observe
from src.providers.base import EmbedRequest
from src.providers.router import ModelRouter


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    curriculum_node_id: uuid.UUID | None
    page_number: int
    content: str
    score: float


def split_text(text: str, *, size: int | None = None, overlap: int | None = None) -> list[str]:
    chunk_size = size or settings.knowledge_chunk_size
    chunk_overlap = overlap if overlap is not None else settings.knowledge_chunk_overlap
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        if end < len(normalized):
            boundary = max(normalized.rfind("。", start, end), normalized.rfind(".", start, end))
            if boundary > start + chunk_size // 2:
                end = boundary + 1
        chunks.append(normalized[start:end].strip())
        if end >= len(normalized):
            break
        start = max(start + 1, end - chunk_overlap)
    return chunks


async def build_chunks(
    db: AsyncSession,
    source: KnowledgeSource,
    pages: list[str],
    nodes: list[CurriculumNode],
    model_router: ModelRouter,
) -> int:
    page_starts = sorted(
        (
            (int(node.start_page), node)
            for node in nodes
            if node.start_page and str(node.start_page).isdigit()
        ),
        key=lambda item: item[0],
    )

    def node_for_page(page_number: int) -> CurriculumNode | None:
        selected = None
        for start_page, node in page_starts:
            if start_page > page_number:
                break
            selected = node
        return selected

    pending: list[KnowledgeChunk] = []
    for page_number, page_text in enumerate(pages, start=1):
        for content in split_text(page_text):
            node = node_for_page(page_number)
            pending.append(
                KnowledgeChunk(
                    source_id=source.id,
                    curriculum_node_id=node.id if node else None,
                    page_number=page_number,
                    chunk_index=len(pending),
                    content=content,
                    char_count=len(content),
                    metadata_={"origin": "pdf_text_layer"},
                )
            )

    batch_size = 24
    with observe(
        "textbook-rag-index",
        input={"source_id": str(source.id), "chunks": len(pending)},
        metadata={"embedding_model": settings.ollama_embedding_model},
    ) as span:
        embedded_count = 0
        for offset in range(0, len(pending), batch_size):
            batch = pending[offset : offset + batch_size]
            try:
                response = await model_router.embed(
                    EmbedRequest(texts=[chunk.content for chunk in batch])
                )
            except Exception:
                response = None
            for index, chunk in enumerate(batch):
                if response is not None:
                    vector = response.embeddings[index]
                    if len(vector) == settings.knowledge_embedding_dimensions:
                        chunk.embedding = vector
                        chunk.embedding_model = response.model
                        embedded_count += 1
                db.add(chunk)
        if span is not None:
            span.update(output={"chunks": len(pending), "embedded": embedded_count})
    return len(pending)


async def retrieve_chunks(
    db: AsyncSession,
    model_router: ModelRouter,
    *,
    query: str,
    source_id: uuid.UUID | None = None,
    curriculum_node_id: uuid.UUID | None = None,
    limit: int = 5,
) -> list[RetrievedChunk]:
    filters = []
    if source_id:
        filters.append(KnowledgeChunk.source_id == source_id)
    if curriculum_node_id:
        filters.append(KnowledgeChunk.curriculum_node_id == curriculum_node_id)

    query_vector: list[float] | None = None
    try:
        response = await model_router.embed(EmbedRequest(texts=[query]))
        if len(response.embeddings[0]) == settings.knowledge_embedding_dimensions:
            query_vector = response.embeddings[0]
    except Exception:
        query_vector = None

    with observe(
        "textbook-rag-retrieval",
        input={"query": query, "source_id": str(source_id) if source_id else None},
    ) as span:
        if query_vector is not None:
            distance = KnowledgeChunk.embedding.cosine_distance(query_vector)
            statement = (
                select(KnowledgeChunk, distance.label("distance"))
                .where(*filters, KnowledgeChunk.embedding.is_not(None))
                .order_by(distance)
                .limit(limit)
            )
            result = await db.execute(statement)
            rows = list(result.all())
            chunks = [
                RetrievedChunk(
                    chunk_id=chunk.id,
                    source_id=chunk.source_id,
                    curriculum_node_id=chunk.curriculum_node_id,
                    page_number=chunk.page_number,
                    content=chunk.content,
                    score=max(0.0, 1.0 - float(distance_value)),
                )
                for chunk, distance_value in rows
            ]
            if not chunks:
                query_vector = None
        if query_vector is None:
            terms = [term for term in re.findall(r"[\w\u4e00-\u9fff]+", query) if len(term) > 1]
            lexical = [KnowledgeChunk.content.ilike(f"%{term}%") for term in terms[:6]]
            statement = select(KnowledgeChunk).where(*filters)
            if lexical:
                statement = statement.where(or_(*lexical))
            result = await db.execute(statement.order_by(KnowledgeChunk.page_number).limit(limit))
            chunks = [
                RetrievedChunk(
                    chunk_id=chunk.id,
                    source_id=chunk.source_id,
                    curriculum_node_id=chunk.curriculum_node_id,
                    page_number=chunk.page_number,
                    content=chunk.content,
                    score=0.5,
                )
                for chunk in result.scalars().all()
            ]
        if span is not None:
            span.update(
                output={"matches": len(chunks), "mode": "vector" if query_vector else "text"}
            )
    return chunks
