from typing import Any

WRITING_PHRASE_IMPORT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "chinese_meaning": {"type": ["string", "null"]},
                    "usage_scene": {"type": ["string", "null"]},
                    "usage_position": {"type": ["string", "null"]},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "examples": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sentence": {"type": "string"},
                                "translation": {"type": ["string", "null"]},
                            },
                            "required": ["sentence"],
                        },
                    },
                    "usage_notes": {"type": "array", "items": {"type": "string"}},
                    "mistakes": {"type": "array", "items": {"type": "string"}},
                    "quality_score": {"type": "number", "minimum": 0, "maximum": 1},
                    "warnings": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text"],
            },
        }
    },
    "required": ["candidates"],
}
