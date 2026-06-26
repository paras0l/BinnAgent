from typing import Any

from src.extraction.schemas import WRITING_PHRASE_IMPORT_SCHEMA

VOCABULARY_CARD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "phonetic": {"type": "string"},
                    "definition_zh": {"type": "string"},
                    "definition_en": {"type": "string"},
                    "collocations": {"type": "array", "items": {"type": "object"}},
                    "examples": {"type": "array", "items": {"type": "object"}},
                    "memory_tip": {"type": "string"},
                    "exam_level": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": [
                    "word",
                    "phonetic",
                    "definition_zh",
                    "definition_en",
                    "examples",
                    "confidence",
                ],
            },
        }
    },
    "required": ["cards"],
}

GRAMMAR_MICRO_LESSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "machine_data": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "core_rules": {"type": "array", "items": {"type": "string"}},
                "examples": {"type": "array", "items": {"type": "object"}},
                "mistakes": {"type": "array", "items": {"type": "string"}},
                "exercises": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["topic", "core_rules", "examples", "mistakes", "exercises"],
        },
        "display_html": {"type": "string"},
    },
    "required": ["machine_data", "display_html"],
}

SCHEMA_REGISTRY: dict[str, dict[str, Any]] = {
    "VocabularyExtractOutput": VOCABULARY_CARD_SCHEMA,
    "WritingPhraseImportOutput": WRITING_PHRASE_IMPORT_SCHEMA,
    "GrammarMicroLessonOutput": GRAMMAR_MICRO_LESSON_SCHEMA,
}
