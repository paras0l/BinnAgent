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
                "exercises": {
                    "type": "array",
                    "minItems": 2,
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["grammar_fill_blank", "single_choice", "fill_blank"],
                            },
                            "prompt": {"type": "string"},
                            "answer": {"type": "string"},
                            "accepted_answers": {"type": "array", "items": {"type": "string"}},
                            "explanation": {"type": "string"},
                        },
                        "required": ["type", "prompt", "answer", "explanation"],
                        "additionalProperties": True,
                    },
                },
            },
            "required": ["topic", "core_rules", "examples", "mistakes", "exercises"],
        },
        "display_html": {"type": "string"},
    },
    "required": ["machine_data", "display_html"],
}

GROUP_LEARNING_SIGNAL_EXTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "signals": {
            "type": "array",
            "maxItems": 12,
            "items": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                    "signal_type": {"type": "string"},
                    "target_type": {"type": "string"},
                    "target_label": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence_text": {"type": "string"},
                    "normalized_note": {"type": "string"},
                    "recommendation_reason": {"type": "string"},
                },
                "required": [
                    "message_id",
                    "signal_type",
                    "target_type",
                    "target_label",
                    "confidence",
                    "evidence_text",
                    "recommendation_reason",
                ],
            },
        }
    },
    "required": ["signals"],
}

GRAPH_FEEDBACK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "improvements": {"type": "array", "items": {"type": "string"}},
        "drill": {"type": ["string", "null"]},
    },
    "required": ["summary", "strengths", "improvements", "drill"],
    "additionalProperties": True,
}

GENERATED_EXERCISE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "skill": {"type": "string", "enum": ["grammar", "vocabulary", "reading"]},
                    "type": {
                        "type": "string",
                        "enum": ["single_choice", "fill_blank", "grammar_fill_blank"],
                    },
                    "prompt": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "correctAnswer": {"type": "string"},
                    "acceptedAnswers": {"type": "array", "items": {"type": "string"}},
                    "explanation": {"type": "string"},
                    "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
                    "metadata": {"type": "object"},
                },
                "required": [
                    "skill",
                    "type",
                    "prompt",
                    "correctAnswer",
                    "explanation",
                    "difficulty",
                ],
                "additionalProperties": True,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

UNIT_EXERCISE_CANDIDATES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "minItems": 8,
            "maxItems": 20,
            "items": {
                "type": "object",
                "properties": {
                    "knowledgePointId": {"type": "string"},
                    "questionType": {
                        "type": "string",
                        "enum": [
                            "choice_context",
                            "fill_blank",
                            "dialogue_complete",
                            "error_fix",
                            "grammar_fill_blank",
                        ],
                    },
                    "cognitiveLevel": {
                        "type": "string",
                        "enum": ["recognition", "understanding", "production", "transfer"],
                    },
                    "scenario": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "setting": {"type": "string"},
                            "zh": {"type": "string"},
                        },
                        "required": ["name", "setting", "zh"],
                        "additionalProperties": False,
                    },
                    "stem": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                    "answer": {"type": "string"},
                    "acceptableAnswers": {"type": "array", "items": {"type": "string"}},
                    "explanation": {"type": "string"},
                    "difficulty": {"type": "number", "minimum": 0.1, "maximum": 1.0},
                    "targetExpression": {"type": "string"},
                    "errorTypes": {"type": "array", "items": {"type": "string"}},
                    "hint": {"type": "string"},
                },
                "required": [
                    "knowledgePointId",
                    "questionType",
                    "cognitiveLevel",
                    "scenario",
                    "stem",
                    "options",
                    "answer",
                    "acceptableAnswers",
                    "explanation",
                    "difficulty",
                    "targetExpression",
                    "errorTypes",
                    "hint",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

UNIT_EXERCISE_REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reviews": {
            "type": "array",
            "minItems": 1,
            "maxItems": 20,
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer", "minimum": 0, "maximum": 19},
                    "decision": {"type": "string", "enum": ["accept", "reject"]},
                    "reasons": {"type": "array", "items": {"type": "string"}},
                    "scores": {
                        "type": "object",
                        "properties": {
                            "knowledgeAlignment": {"type": "number", "minimum": 0, "maximum": 1},
                            "answerability": {"type": "number", "minimum": 0, "maximum": 1},
                            "naturalness": {"type": "number", "minimum": 0, "maximum": 1},
                            "distractorQuality": {"type": "number", "minimum": 0, "maximum": 1},
                            "explanationQuality": {"type": "number", "minimum": 0, "maximum": 1},
                            "novelty": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                        "required": [
                            "knowledgeAlignment",
                            "answerability",
                            "naturalness",
                            "distractorQuality",
                            "explanationQuality",
                            "novelty",
                        ],
                        "additionalProperties": False,
                    },
                },
                "required": ["index", "decision", "reasons", "scores"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["reviews"],
    "additionalProperties": False,
}

ESSAY_SCORING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "score": {"type": "number", "minimum": 0, "maximum": 25},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "key_issues": {"type": "array", "items": {"type": "string"}},
        "sentence_feedback": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sentence": {"type": "string"},
                    "feedback": {"type": "string"},
                },
                "required": ["sentence", "feedback"],
                "additionalProperties": True,
            },
        },
    },
    "required": ["score", "strengths", "key_issues", "sentence_feedback"],
    "additionalProperties": True,
}

DICTIONARY_LOOKUP_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "phonetic": {"type": "string"},
        "meanings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "part_of_speech": {"type": "string"},
                    "definition": {"type": "string"},
                },
                "required": ["part_of_speech", "definition"],
                "additionalProperties": True,
            },
        },
        "collocations": {"type": "array", "items": {"type": "string"}},
        "examples": {"type": "array", "items": {"type": "string"}},
        "confusing_words": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string"},
                    "difference": {"type": "string"},
                },
                "required": ["word", "difference"],
                "additionalProperties": True,
            },
        },
        "cet_relevance": {"type": "string"},
    },
    "required": ["phonetic", "meanings", "collocations", "examples", "confusing_words", "cet_relevance"],
    "additionalProperties": True,
}

LOCAL_VOCABULARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "meanings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "part_of_speech": {"type": "string"},
                    "definition": {"type": "string"},
                    "definition_zh": {"type": "string"},
                },
                "required": ["part_of_speech", "definition", "definition_zh"],
            },
        },
        "dictionary_senses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "part_of_speech": {"type": "string"},
                    "meanings_zh": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["part_of_speech", "meanings_zh"],
            },
        },
        "word_forms": {
            "type": "object",
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
        },
        "dictionary_tags": {"type": "array", "items": {"type": "string"}},
        "examples": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"en": {"type": "string"}, "zh": {"type": "string"}},
                "required": ["en", "zh"],
            },
        },
        "collocations": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "meanings",
        "dictionary_senses",
        "word_forms",
        "dictionary_tags",
        "examples",
        "collocations",
    ],
}

DETAIL_HTML_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "phonetic": {"type": ["string", "null"]},
        "meanings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "part_of_speech": {"type": "string"},
                    "definition": {"type": "string"},
                    "definition_zh": {"type": "string"},
                },
                "required": ["part_of_speech", "definition", "definition_zh"],
            },
        },
        "dictionary_senses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "part_of_speech": {"type": "string"},
                    "meanings_zh": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["part_of_speech", "meanings_zh"],
            },
        },
        "examples": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "en": {"type": "string"},
                    "zh": {"type": "string"},
                },
                "required": ["en", "zh"],
            },
        },
        "collocations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["phonetic", "meanings", "dictionary_senses", "examples", "collocations"],
}

EXPLORE_CAPABILITY_RERANK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "recommendations": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "capability_id": {"type": "string"},
                    "priority_score": {"type": "number", "minimum": 0, "maximum": 1},
                    "reason": {"type": "string"},
                },
                "required": ["capability_id", "priority_score", "reason"],
                "additionalProperties": True,
            },
        }
    },
    "required": ["recommendations"],
    "additionalProperties": False,
}

READING_MATERIAL_GENERATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "material_type": {"type": "string", "enum": ["dialogue", "passage"]},
        "text": {"type": "string", "minLength": 80},
        "theme": {"type": "string"},
        "grammar_focus": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
        "vocabulary_used": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
        "level_rationale": {"type": "string"},
        "comprehension_checks": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                },
                "required": ["question", "answer"],
                "additionalProperties": True,
            },
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "title",
        "material_type",
        "text",
        "theme",
        "grammar_focus",
        "vocabulary_used",
        "level_rationale",
        "comprehension_checks",
        "confidence",
    ],
    "additionalProperties": True,
}

SCHEMA_REGISTRY: dict[str, dict[str, Any]] = {
    "VocabularyExtractOutput": VOCABULARY_CARD_SCHEMA,
    "WritingPhraseImportOutput": WRITING_PHRASE_IMPORT_SCHEMA,
    "GrammarMicroLessonOutput": GRAMMAR_MICRO_LESSON_SCHEMA,
    "GroupLearningSignalExtractOutput": GROUP_LEARNING_SIGNAL_EXTRACT_SCHEMA,
    "GraphFeedbackOutput": GRAPH_FEEDBACK_SCHEMA,
    "GeneratedExerciseOutput": GENERATED_EXERCISE_SCHEMA,
    "UnitExerciseCandidatesOutput": UNIT_EXERCISE_CANDIDATES_SCHEMA,
    "UnitExerciseReviewOutput": UNIT_EXERCISE_REVIEW_SCHEMA,
    "EssayScoringOutput": ESSAY_SCORING_SCHEMA,
    "DictionaryLookupOutput": DICTIONARY_LOOKUP_SCHEMA,
    "LocalVocabularyOutput": LOCAL_VOCABULARY_SCHEMA,
    "VocabularyDetailHtmlOutput": DETAIL_HTML_SCHEMA,
    "ExploreCapabilityRerankOutput": EXPLORE_CAPABILITY_RERANK_SCHEMA,
    "ReadingMaterialGenerationOutput": READING_MATERIAL_GENERATION_SCHEMA,
}
