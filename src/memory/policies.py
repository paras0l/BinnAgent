from __future__ import annotations

from typing import Any


EVENT_TYPES = {
    "chat_learning_turn",
    "chat_error_observed",
    "vocabulary_attempted",
    "vocabulary_mistake_recorded",
    "knowledge_exercise_answered",
    "knowledge_point_practiced",
    "writing_phrase_saved",
    "writing_phrase_updated",
    "writing_phrase_deleted",
    "writing_phrase_attempted",
    "essay_submitted",
    "essay_feedback_received",
    "grammar_topic_opened",
    "chat_tutoring_completed",
    "user_corrected_memory",
    "user_deleted_memory",
    "user_disabled_memory",
    "user_marked_mastered",
    "user_marked_memory_improved",
    "user_reset_learning_plan",
}

USER_OPERATION_TYPES = {"edit", "delete", "correct", "disable", "mark_improved", "export", "reset_plan"}

SKILL_ALIASES = {
    "essay": "writing",
    "phrase": "writing",
    "knowledge_point": "knowledge",
    "textbook": "knowledge",
    "word": "vocabulary",
}


def normalize_skill(value: str | None) -> str:
    if not value:
        return "general"
    normalized = value.strip().lower().replace(" ", "_")
    return SKILL_ALIASES.get(normalized, normalized or "general")


def clamp_confidence(value: float | int | None) -> float:
    if value is None:
        return 1.0
    return min(1.0, max(0.0, float(value)))


def clean_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        cleaned[str(key)] = value
    return cleaned


def is_user_dismissed(status: str | None) -> bool:
    return status in {"dismissed", "deleted", "disabled"}
