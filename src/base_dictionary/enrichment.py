from __future__ import annotations

from typing import Any


def vocabulary_enrichment(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    pronunciations = payload.get("pronunciations") or []
    phonetic = next(
        (
            str(sound["ipa"]).strip()
            for sound in pronunciations
            if isinstance(sound, dict) and str(sound.get("ipa") or "").strip()
        ),
        None,
    )
    senses = [
        {
            **sense,
            "definition": sense.get("definition_zh") or sense.get("definition_en"),
            "source": "base_dictionary",
        }
        for sense in payload.get("senses") or []
        if isinstance(sense, dict) and sense.get("definition_en")
    ]
    relations = payload.get("relations") or []
    collocations = [
        relation["target"]
        for relation in relations
        if isinstance(relation, dict)
        and relation.get("type") in {"collocation", "related"}
        and relation.get("target")
    ]
    forms = [str(value) for value in payload.get("forms") or [] if str(value).strip()]
    return {
        "phonetic": phonetic,
        "meanings": senses,
        "dictionary_senses": senses,
        "word_forms": {"forms": forms} if forms else {},
        "dictionary_tags": payload.get("parts_of_speech") or [],
        "collocations": collocations,
        "examples": payload.get("examples") or [],
        "entry_kind": payload.get("entry_kind") or "word",
        "dictionary_provider": "base_dictionary",
        "build_version": payload.get("build_version"),
    }


def reading_translation(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    sense = next(
        (
            item
            for item in payload.get("senses") or []
            if isinstance(item, dict) and str(item.get("definition_zh") or "").strip()
        ),
        None,
    )
    if sense is None:
        return None
    definition_en = str(sense.get("definition_en") or "").strip()
    part_of_speech = str(sense.get("part_of_speech") or "").strip()
    note_parts = [value for value in (part_of_speech, definition_en) if value]
    return {
        "translation": str(sense["definition_zh"]).strip(),
        "context_note": " · ".join(note_parts) or "基础词库中的常用义项",
        "confidence": float(sense.get("confidence") or 0.9),
        "source": "base_dictionary",
        "build_version": payload.get("build_version"),
    }
