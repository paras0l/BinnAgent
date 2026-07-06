import asyncio
import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.ocr import OcrResult, run_pdf_ocr, should_ocr_artifact
from src.documents.parser_router import ParserRouter, ParserRouterResult
from src.knowledge.parser_profiles import profile_for_source
from src.knowledge.parser_report import build_parser_report
from src.knowledge.quality import quality_summary, score_textbook_quality
from src.knowledge.rag import build_chunks, split_text
from src.knowledge.review_queue import queue_summary, replace_parser_review_items
from src.knowledge.textbook_extractor import extract_textbook_candidates
from src.models.knowledge import (
    CurriculumNode,
    KnowledgeChunk,
    KnowledgePoint,
    KnowledgeSource,
    ParserRun,
)
from src.providers.router import router as model_router

UNIT_PATTERN = re.compile(r"(?im)^\s*((?:Starter\s+)?Unit\s+\d+)\s*$\s*^\s*([^\n]{3,80})\s*$")


@dataclass(frozen=True)
class ParsedUnit:
    title: str
    subtitle: str
    page_number: int


@dataclass(frozen=True)
class ParsedTextbook:
    page_count: int
    units: tuple[ParsedUnit, ...]
    text_char_count: int


@dataclass(frozen=True)
class ParsedVocabularyEntry:
    unit_title: str
    expression: str
    canonical_expression: str
    unit_order: int
    raw_line: str
    confidence: float
    warnings: tuple[str, ...] = ()


VOCABULARY_HEADING = "Words and Expressions in Each Unit"
VOCABULARY_HEADINGS = (
    "Words and Expressions in Each Unit",
    "Words and Expressions",
)
VOCABULARY_INDEX_HEADING = "Vocabulary Index"
VOCABULARY_UNIT_PATTERN = re.compile(r"^(Starter\s+Unit|Unit)\s+(\d+)\s*$", re.IGNORECASE)
VOCABULARY_PAGE_REF_PATTERN = re.compile(r"\s+p\.(S?\d+(?:[–-]S?\d+)?)\s*$", re.IGNORECASE)
PHONETIC_PATTERN = re.compile(
    r"^(?P<expression>.+?)\s+(?P<phonetic>/[^/]+/(?:\s*,\s*/[^/]+/)?)\s*(?P<rest>.*)$"
)
PART_OF_SPEECH_PATTERN = re.compile(
    r"\b(?:adj|adv|art|conj|interj|modal\s+v|n|num|prep|pron|v)\.(?:\s*&\s*(?:adj|adv|n|pron|v)\.)?",
    re.IGNORECASE,
)

STALE_INGEST_METADATA_KEYS = {
    "blocking_reasons",
    "document_quality",
    "error",
    "parser_report",
    "parser_report_summary",
    "parse_quality_status",
    "quality_score",
    "quality_status",
    "warning",
}


def _clear_stale_ingest_metadata(metadata: dict) -> dict:
    cleaned = dict(metadata)
    for key in STALE_INGEST_METADATA_KEYS:
        cleaned.pop(key, None)
    return cleaned


def _parse_pdf(path: Path) -> ParsedTextbook:
    reader = PdfReader(path)
    units: list[ParsedUnit] = []
    seen: set[str] = set()
    text_char_count = 0
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text_char_count += len(text)
        for match in UNIT_PATTERN.finditer(text):
            title = " ".join(match.group(1).split())
            subtitle = " ".join(match.group(2).split()).strip(" ·—-")
            key = title.casefold()
            if key in seen or subtitle.lower() in {"contents", "topics", "functions"}:
                continue
            seen.add(key)
            units.append(ParsedUnit(title=title, subtitle=subtitle, page_number=page_number))
    units.sort(
        key=lambda unit: (0 if unit.title.lower().startswith("starter") else 1, unit.page_number)
    )
    return ParsedTextbook(
        page_count=len(reader.pages),
        units=tuple(units[:20]),
        text_char_count=text_char_count,
    )


def _normalize_unit_title(value: str) -> str:
    match = VOCABULARY_UNIT_PATTERN.fullmatch(" ".join(value.split()))
    if not match:
        return " ".join(value.split())
    prefix = "Starter Unit" if match.group(1).lower().startswith("starter") else "Unit"
    return f"{prefix} {int(match.group(2))}"


def _normalize_expression(value: str) -> str:
    expression = " ".join(value.split()).strip(" ·—-")
    replacements = {
        "a/f_ternoon": "afternoon",
        "a/f_ter": "after",
        "twel/f_th": "twelfth",
        "/T_hursday": "Thursday",
        "P .E.": "P.E.",
        "P. M .": "P.M.",
        "To m": "Tom",
        "burg er": "burger",
    }
    for source, target in replacements.items():
        expression = expression.replace(source, target)
    expression = re.sub(r"\bY\s+ou", "You", expression)
    expression = expression.replace("_", "")
    return expression.rstrip(" （").strip()


def _canonical_expression(value: str) -> str:
    value = value.casefold().replace("’", "'")
    value = re.sub(r"[^a-z0-9'./ -]+", "", value)
    return re.sub(r"\s+", " ", value).strip(" .-/")


def _parse_vocabulary_chunk(
    unit_title: str,
    chunk: str,
    unit_order: int,
) -> ParsedVocabularyEntry | None:
    normalized = " ".join(chunk.split())
    phonetic_match = PHONETIC_PATTERN.match(normalized)
    if phonetic_match:
        expression = _normalize_expression(phonetic_match.group("expression"))
    else:
        pos_match = PART_OF_SPEECH_PATTERN.search(normalized)
        cjk_match = re.search(r"[\u3400-\u9fff]", normalized)
        split_at = (
            pos_match.start() if pos_match else cjk_match.start() if cjk_match else len(normalized)
        )
        expression = _normalize_expression(normalized[:split_at])
    canonical = _canonical_expression(expression)
    if not canonical or not re.search(r"[a-z]", canonical) or len(expression) > 100:
        return None
    warnings: list[str] = []
    confidence = 0.92
    if not phonetic_match:
        confidence -= 0.12
        warnings.append("missing_phonetic")
    if re.search(r"\b(?:Page PB|9594|101100)\b", normalized):
        confidence -= 0.35
        warnings.append("dirty_pdf_token")
    return ParsedVocabularyEntry(
        unit_title=unit_title,
        expression=expression,
        canonical_expression=canonical,
        unit_order=unit_order,
        raw_line=normalized,
        confidence=max(0, confidence),
        warnings=tuple(warnings),
    )


def _parse_unit_vocabulary(reader: PdfReader) -> tuple[ParsedVocabularyEntry, ...]:
    start_threshold = int(len(reader.pages) * 0.55)
    in_vocabulary_section = False
    current_unit: str | None = None
    buffer: list[str] = []
    entries: list[ParsedVocabularyEntry] = []
    unit_orders: dict[str, int] = {}
    ignored_lines = {"Page PB", *VOCABULARY_HEADINGS, "9594", "9796", "9998", "101100", "103102"}

    for pdf_page, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if not in_vocabulary_section:
            if pdf_page < start_threshold or not any(heading in text for heading in VOCABULARY_HEADINGS):
                continue
            in_vocabulary_section = True
        if VOCABULARY_INDEX_HEADING in text:
            break

        for raw_line in text.splitlines():
            line = " ".join(raw_line.split())
            if (
                not line
                or line in ignored_lines
                or line.isdigit()
                or line.startswith("（注：")
                or line.startswith("在英式发音")
                or any(line.startswith(heading) for heading in VOCABULARY_HEADINGS)
            ):
                continue
            unit_match = VOCABULARY_UNIT_PATTERN.fullmatch(line)
            if unit_match:
                buffer.clear()
                current_unit = _normalize_unit_title(line)
                unit_orders.setdefault(current_unit, 0)
                continue
            if current_unit is None:
                continue
            buffer.append(line)
            combined = " ".join(buffer)
            page_ref_match = VOCABULARY_PAGE_REF_PATTERN.search(combined)
            if not page_ref_match:
                continue
            next_order = unit_orders[current_unit] + 1
            entry = _parse_vocabulary_chunk(
                current_unit, combined[: page_ref_match.start()], next_order
            )
            if entry is not None:
                entries.append(entry)
                unit_orders[current_unit] = next_order
            buffer.clear()
    return tuple(entries)


def _node_for_candidate(
    candidate_title: str,
    page_number: int,
    nodes: list[CurriculumNode],
    nodes_by_title: dict[str, CurriculumNode],
    *,
    candidate_key: str | None = None,
) -> CurriculumNode | None:
    normalized_title = candidate_title.replace(" overview", "")
    node = nodes_by_title.get(_normalize_unit_title(normalized_title))
    if node is not None:
        return node
    unit_match = re.search(r"\b(?:Starter\s+Unit|Unit)\s+\d+\b", candidate_title, re.IGNORECASE)
    if unit_match:
        node = nodes_by_title.get(_normalize_unit_title(unit_match.group(0)))
        if node is not None:
            return node
    if candidate_key:
        key_match = re.search(r"\b(starter-unit|unit)-(\d+)\b", candidate_key, re.IGNORECASE)
        if key_match:
            prefix = "Starter Unit" if key_match.group(1).casefold().startswith("starter") else "Unit"
            node = nodes_by_title.get(f"{prefix} {int(key_match.group(2))}")
            if node is not None:
                return node
    if not nodes:
        return None
    ordered = sorted(
        nodes,
        key=lambda item: abs(_safe_int(item.start_page, default=page_number) - page_number),
    )
    return ordered[0]


def _merge_manifest_units(parsed_units: tuple[ParsedUnit, ...], manifest: object | None) -> tuple[ParsedUnit, ...]:
    manifest_units = tuple(getattr(manifest, "units", ()) or ())
    if not manifest_units:
        return parsed_units
    parsed_by_title = {_normalize_unit_title(unit.title): unit for unit in parsed_units}
    merged: list[ParsedUnit] = []
    for index, unit in enumerate(manifest_units, start=1):
        title = str(getattr(unit, "title", "") or "").strip()
        if not title:
            continue
        parsed = parsed_by_title.get(_normalize_unit_title(title))
        page_number = parsed.page_number if parsed else int(getattr(unit, "start_printed_page", None) or index)
        merged.append(
            ParsedUnit(
                title=title,
                subtitle=str(getattr(unit, "subtitle", "") or (parsed.subtitle if parsed else "")).strip(),
                page_number=page_number,
            )
        )
    return tuple(merged)


def _safe_int(value: str | None, *, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _parse_quality_status(document_quality: dict, parser_status: str) -> str:
    if parser_status == "failed":
        return "failed"
    if document_quality.get("needs_ocr"):
        return "needs_ocr"
    if document_quality.get("needs_review"):
        return "needs_review"
    return "good"


def _db_label(value: str | None, *, max_length: int) -> str:
    normalized = " ".join(str(value or "").split()).strip()
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1].rstrip() + "…"


def _knowledge_point_status(requires_review: bool) -> str:
    return "draft" if requires_review else "published"


def _vocabulary_entry_requires_review(entry: ParsedVocabularyEntry) -> bool:
    if entry.confidence < 0.75:
        return True
    warnings = set(entry.warnings)
    if not warnings:
        return False
    if warnings == {"missing_phonetic"}:
        return len(entry.canonical_expression.split()) <= 1
    return True


async def _parse_with_optional_ocr(
    path: Path,
    *,
    source_id: uuid.UUID,
) -> tuple[ParserRouterResult, OcrResult | None]:
    router_result = await asyncio.to_thread(
        lambda: ParserRouter().parse(
            path,
            {
                "source_id": str(source_id),
            },
        )
    )
    if not should_ocr_artifact(router_result.artifact):
        return router_result, None
    ocr_result = await asyncio.to_thread(lambda: run_pdf_ocr(path))
    if not ocr_result.used or ocr_result.output_path is None:
        return router_result, ocr_result
    ocr_router_result = await asyncio.to_thread(
        lambda: ParserRouter().parse(
            ocr_result.output_path,
            {
                "source_id": str(source_id),
            },
        )
    )
    return ocr_router_result, ocr_result


async def _load_or_create_parser_run(
    db: AsyncSession,
    *,
    source: KnowledgeSource,
    parser_run_id: uuid.UUID | None,
    parser_profile_id: str | None,
    book_manifest_id: str | None,
    input_hash: str | None,
) -> ParserRun:
    if parser_run_id is not None:
        result = await db.execute(select(ParserRun).where(ParserRun.id == parser_run_id))
        parser_run = result.scalar_one_or_none()
        if parser_run is None:
            raise ValueError("ParserRun not found")
        parser_run.parser_id = "document-parser-router"
        parser_run.parser_version = "v1"
        parser_run.parser_profile_id = parser_profile_id
        parser_run.book_manifest_id = book_manifest_id
        parser_run.pdf_sha256 = source.sha256
        parser_run.input_hash = input_hash
        return parser_run
    parser_run = ParserRun(
        source_id=source.id,
        parser_id="document-parser-router",
        parser_version="v1",
        parser_profile_id=parser_profile_id,
        book_manifest_id=book_manifest_id,
        pdf_sha256=source.sha256,
        input_hash=input_hash,
        status="running",
        stage="queued",
        progress=0,
        started_at=datetime.now(timezone.utc),
        artifact_refs={},
    )
    db.add(parser_run)
    return parser_run


async def _set_parser_progress(
    db: AsyncSession,
    source: KnowledgeSource,
    parser_run: ParserRun,
    *,
    status: str | None = None,
    stage: str,
    progress: int,
) -> None:
    if status is not None:
        parser_run.status = status
    parser_run.stage = stage
    parser_run.progress = max(0, min(100, progress))
    if parser_run.status == "running":
        source.status = "processing"
    metadata = dict(source.metadata_ or {})
    metadata.update(
        {
            "latest_parser_run_id": str(parser_run.id),
            "processing_status": parser_run.status,
            "parser_status": parser_run.status,
            "parser_stage": parser_run.stage,
            "parser_progress": parser_run.progress,
        }
    )
    source.metadata_ = metadata
    await db.flush()


async def process_uploaded_textbook(
    db: AsyncSession,
    source: KnowledgeSource,
    *,
    parser_run_id: uuid.UUID | None = None,
) -> ParsedTextbook:
    if not source.object_key:
        raise ValueError("Knowledge source has no stored PDF")
    path = Path(source.object_key)
    if not path.exists() and path.is_absolute() and path.parts[:2] == ("/", "app"):
        local_path = Path(*path.parts[2:])
        if local_path.exists():
            path = local_path
    manifest, parser_profile = profile_for_source(source.filename)
    parser_run = await _load_or_create_parser_run(
        db,
        source=source,
        parser_run_id=parser_run_id,
        parser_profile_id=parser_profile.id if parser_profile else None,
        book_manifest_id=manifest.id if manifest else None,
        input_hash=_file_sha256(path) if path.exists() else source.sha256,
    )
    await db.flush()
    parser_run_id_str = str(parser_run.id)
    await _set_parser_progress(
        db,
        source,
        parser_run,
        status="running",
        stage="parsing_document",
        progress=5,
    )
    source.metadata_ = {
        **(source.metadata_ or {}),
        "latest_parser_run_id": parser_run_id_str,
        "parser_status": "running",
        "processing_status": "running",
    }

    try:
        router_result, ocr_result = await _parse_with_optional_ocr(path, source_id=source.id)
        artifact = router_result.artifact
        document_quality = artifact.quality_dict()
        parser_run.parser_id = "document-parser-router"
        parser_run.parser_version = "v1"
        parser_run.artifact_refs = {
            "document_parse_artifact": artifact.to_dict(),
            "ocr": ocr_result.to_dict() if ocr_result else None,
            **router_result.metadata(),
        }
        await _set_parser_progress(db, source, parser_run, stage="normalizing_artifact", progress=20)
        extraction = await asyncio.to_thread(lambda: extract_textbook_candidates(artifact))
        await _set_parser_progress(
            db,
            source,
            parser_run,
            stage="extracting_textbook_structure",
            progress=35,
        )
        extracted_units = tuple(
            ParsedUnit(
                title=item.title,
                subtitle=item.subtitle,
                page_number=item.page_number,
            )
            for item in extraction.curriculum
        )
        parsed = ParsedTextbook(
            page_count=int(document_quality.get("page_count") or len(artifact.pages)),
            units=_merge_manifest_units(extracted_units, manifest)
            or (ParsedUnit(title="全册材料", subtitle=source.title, page_number=1),),
            text_char_count=int(document_quality.get("text_char_count") or len(artifact.markdown)),
        )
        vocabulary_entries = tuple(
            ParsedVocabularyEntry(
                unit_title=item.unit_title,
                expression=item.expression,
                canonical_expression=item.canonical_expression,
                unit_order=item.unit_order,
                raw_line=item.raw_line,
                confidence=item.confidence,
                warnings=item.warnings,
            )
            for item in extraction.vocabulary
        )
        vocabulary_evidence = {
            (item.unit_title, item.canonical_expression, item.unit_order): item.evidence.to_dict()
            for item in extraction.vocabulary
        }
        page_texts = [page.text for page in artifact.pages] or [artifact.markdown]
        used_toc_fallback = bool(extraction.warnings)

        await db.execute(delete(KnowledgePoint).where(KnowledgePoint.source_id == source.id))
        await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source_id == source.id))
        await db.execute(delete(CurriculumNode).where(CurriculumNode.source_id == source.id))
        await _set_parser_progress(db, source, parser_run, stage="building_chunks", progress=50)

        nodes: list[CurriculumNode] = []
        for ordinal, unit in enumerate(parsed.units, start=1):
            node = CurriculumNode(
                source_id=source.id,
                node_type="unit",
                title=_db_label(unit.title, max_length=255),
                subtitle=_db_label(unit.subtitle, max_length=255) or None,
                ordinal=ordinal,
                start_page=str(unit.page_number),
                end_page=str(unit.page_number),
                estimated_minutes=20,
                learning_objectives=[],
            )
            db.add(node)
            nodes.append(node)
        await db.flush()

        knowledge_points: list[KnowledgePoint] = []
        nodes_by_title = {_normalize_unit_title(node.title): node for node in nodes}
        for candidate in extraction.knowledge:
            node = _node_for_candidate(
                candidate.title,
                candidate.page_number,
                nodes,
                nodes_by_title,
                candidate_key=candidate.canonical_key,
            )
            if node is None:
                continue
            requires_review = candidate.confidence < 0.8 or bool(candidate.warnings)
            knowledge_points.append(
                KnowledgePoint(
                    source_id=source.id,
                    curriculum_node_id=node.id,
                    canonical_key=f"{candidate.canonical_key}.{str(source.id)[:8]}",
                    type=candidate.type,
                    title=candidate.title,
                    summary=candidate.summary,
                    source_page=str(candidate.page_number),
                    difficulty=0.3,
                    status=_knowledge_point_status(requires_review),
                    content={
                        "origin": "document_artifact_extractor",
                        "requires_review": requires_review,
                        "confidence": candidate.confidence,
                        "warnings": list(candidate.warnings),
                        "evidence": candidate.evidence.to_dict(),
                    },
                )
            )
        seen_vocabulary_keys: set[tuple[uuid.UUID, str]] = set()
        for entry in vocabulary_entries:
            node = nodes_by_title.get(entry.unit_title)
            if node is None:
                continue
            duplicate_key = (node.id, entry.canonical_expression)
            if duplicate_key in seen_vocabulary_keys:
                continue
            seen_vocabulary_keys.add(duplicate_key)
            slug = re.sub(r"[^a-z0-9]+", "-", entry.canonical_expression).strip("-")
            requires_review = _vocabulary_entry_requires_review(entry)
            knowledge_points.append(
                KnowledgePoint(
                    source_id=source.id,
                    curriculum_node_id=node.id,
                    canonical_key=f"vocabulary.{slug}.{str(source.id)[:8]}.{node.ordinal}",
                    type="vocabulary",
                    title=entry.expression,
                    summary=f"{entry.unit_title} 单元词表第 {entry.unit_order} 个词条。",
                    source_page="Words and Expressions",
                    difficulty=0.2,
                    status=_knowledge_point_status(requires_review),
                    content={
                        "origin": "document_artifact_extractor",
                        "role": "unit_wordlist",
                        "grade": source.grade,
                        "lemma": entry.canonical_expression,
                        "unit_order": entry.unit_order,
                        "raw_line": entry.raw_line,
                        "confidence": entry.confidence,
                        "warnings": list(entry.warnings),
                        "requires_review": requires_review,
                        "dictionary_status": "pending",
                        "evidence": vocabulary_evidence.get(
                            (entry.unit_title, entry.canonical_expression, entry.unit_order),
                            {},
                        ),
                    },
                )
            )
        for point in knowledge_points:
            content = dict(point.content or {})
            content["parser_run_id"] = parser_run_id_str
            content.setdefault("source_page", point.source_page)
            content.setdefault("confidence", content.get("confidence", 0.8))
            content.setdefault("warnings", content.get("warnings", []))
            point.content = content
            db.add(point)
        await db.flush()
        chunk_char_counts = [
            len(chunk)
            for page_text in page_texts
            for chunk in split_text(page_text)
        ]
        rag_covered_pages = {
            page_number
            for page_number, page_text in enumerate(page_texts, start=1)
            if split_text(page_text)
        }
        await _set_parser_progress(db, source, parser_run, stage="building_chunks", progress=70)
        chunk_count = await build_chunks(
            db,
            source,
            page_texts,
            nodes,
            model_router,
            parser_run_id=parser_run_id_str,
        )
        await _set_parser_progress(db, source, parser_run, stage="quality_checking", progress=85)
        rag_metadata = _clear_stale_ingest_metadata(source.metadata_ or {})
        section_count = len(extraction.knowledge)
        parser_report = build_parser_report(
            profile=parser_profile,
            unit_count=len(nodes),
            vocabulary_entries=vocabulary_entries,
            page_texts=page_texts,
            unit_titles=[node.title for node in nodes],
            knowledge_points=knowledge_points,
            section_count=section_count,
            rag_chunk_count=chunk_count,
            rag_covered_pages=rag_covered_pages,
            chunk_char_counts=chunk_char_counts,
        )
        report_dict = parser_report.to_dict()
        report_dict.update(
            {
                "document_quality": document_quality,
                "attempted_engines": router_result.attempted_engines,
                "selected_engine": router_result.selected_engine,
                "fallback_used": router_result.fallback_used,
                "ocr": ocr_result.to_dict() if ocr_result else None,
                "needs_ocr": bool(document_quality.get("needs_ocr")),
                "needs_review": bool(document_quality.get("needs_review")),
                "page_count": parsed.page_count,
                "text_char_count": parsed.text_char_count,
                "warnings": list(
                    dict.fromkeys(
                        [
                            *report_dict.get("warnings", []),
                            *artifact.warnings,
                            *extraction.warnings,
                        ]
                    )
                ),
            }
        )
        quality_score = score_textbook_quality(report_dict)
        review_items = await replace_parser_review_items(
            db,
            source=source,
            parser_run_id=parser_run.id,
            knowledge_points=knowledge_points,
            report=report_dict,
            quality_score=quality_score.to_dict(),
        )
        review_summary = queue_summary(review_items)
        report_dict.update(review_summary.to_report_patch())
        quality_score = score_textbook_quality(report_dict)

        source.page_count = parsed.page_count
        source.unit_count = len(nodes)
        source.knowledge_count = len(knowledge_points)
        source.status = quality_score.status
        parser_run.status = "completed"
        parser_run.stage = "completed"
        parser_run.progress = 100
        parser_run.completed_at = datetime.now(timezone.utc)
        parser_run.quality_report = report_dict
        parser_run.quality_score = quality_score.to_dict()
        parser_run.artifact_refs = {
            "curriculum_node_count": len(nodes),
            "knowledge_point_count": len(knowledge_points),
            "rag_chunk_count": chunk_count,
            "review_item_count": len(review_items),
            "document_parse_artifact": artifact.to_dict(),
            "ocr": ocr_result.to_dict() if ocr_result else None,
            **router_result.metadata(),
        }
        parse_quality_status = _parse_quality_status(document_quality, parser_run.status)
        availability_status = (
            "partially_available"
            if parse_quality_status in {"needs_review", "needs_ocr"}
            else quality_summary(quality_score, report_dict).get("availability_status", "available")
        )
        summary_payload = quality_summary(quality_score, report_dict)
        summary_payload.update(
            {
                "parse_quality_status": parse_quality_status,
                "availability_status": availability_status,
                "parser_report_summary": {
                    **summary_payload.get("parser_report_summary", {}),
                    "page_count": parsed.page_count,
                    "text_char_count": parsed.text_char_count,
                    "document_quality": document_quality,
                    "attempted_engines": router_result.attempted_engines,
                    "selected_engine": router_result.selected_engine,
                    "fallback_used": router_result.fallback_used,
                    "ocr": ocr_result.to_dict() if ocr_result else None,
                    "needs_ocr": bool(document_quality.get("needs_ocr")),
                    "warnings": report_dict.get("warnings", []),
                },
            }
        )
        source.metadata_ = {
            **rag_metadata,
            "stage": "validated",
            "latest_parser_run_id": parser_run_id_str,
            "parser_status": parser_run.status,
            "processing_status": parser_run.status,
            "text_char_count": parsed.text_char_count,
            "book_manifest_id": manifest.id if manifest else None,
            "parser_profile": parser_profile.id if parser_profile else None,
            "parser": f"{router_result.selected_engine}-{artifact.parser_version}",
            "selected_engine": router_result.selected_engine,
            "attempted_engines": router_result.attempted_engines,
            "fallback_used": router_result.fallback_used,
            "ocr": ocr_result.to_dict() if ocr_result else None,
            "ocr_object_key": (
                str(ocr_result.output_path)
                if ocr_result and ocr_result.used and ocr_result.output_path
                else None
            ),
            "document_quality": document_quality,
            "parse_quality_status": parse_quality_status,
            "vocabulary_parser": "document-artifact-v1",
            "dictionary_enrichment": "free_dictionary_api+mymemory",
            "vocabulary_entry_count": len(vocabulary_entries),
            "low_confidence_vocabulary_count": parser_report.low_confidence_entries,
            "notes_section_count": 0,
            "pronunciation_section_count": 0,
            "grammar_reference_count": 0,
            "rag_chunk_count": chunk_count,
            "toc_fallback": used_toc_fallback,
            "parser_report": report_dict,
            "warning": "; ".join(parser_report.warnings) if parser_report.warnings else None,
            **summary_payload,
        }
        await db.flush()
        return parsed
    except Exception as exc:
        parser_run.status = "failed"
        parser_run.stage = "failed"
        parser_run.progress = max(parser_run.progress or 0, 1)
        parser_run.completed_at = datetime.now(timezone.utc)
        parser_run.error_message = str(exc)[:500]
        failed_report = {
            "parser_profile": parser_profile.id if parser_profile else None,
            "unit_count": 0,
            "expected_unit_count": parser_profile.expected_unit_count if parser_profile else None,
            "vocabulary_entry_count": 0,
            "expected_min_vocabulary_count": parser_profile.min_vocabulary_count if parser_profile else None,
            "low_confidence_entries": 0,
            "dirty_tokens": [],
            "warnings": [str(exc)[:500]],
        }
        failed_score = score_textbook_quality(failed_report, parser_failed=True)
        parser_run.quality_report = failed_report
        parser_run.quality_score = failed_score.to_dict()
        source.status = "failed"
        source.metadata_ = {
            **(source.metadata_ or {}),
            "stage": "failed",
            "latest_parser_run_id": parser_run_id_str,
            "parser_status": "failed",
            "processing_status": "failed",
            "parse_quality_status": "failed",
            "error": str(exc)[:500],
            "parser_report": failed_report,
            **quality_summary(failed_score, failed_report),
        }
        await db.flush()
        raise


async def get_source(db: AsyncSession, source_id: uuid.UUID) -> KnowledgeSource | None:
    result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.id == source_id))
    return result.scalar_one_or_none()


def _file_sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None
