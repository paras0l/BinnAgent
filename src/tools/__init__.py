# BinnAgent Learning Tools
# Exposes singleton instances for easy import

from src.tools.dictionary import (
    dictionary,
    DictionaryTool,
    DictionaryLookupRequest,
    DictionaryLookupResponse,
)
from src.tools.srs import srs_scheduler, SRSScheduler, SRSCard
from src.tools.question_bank import question_bank, QuestionBank, Question
from src.tools.essay_scoring import essay_scorer, EssayScoringTool, EssayScoringResult

__all__ = [
    "dictionary",
    "DictionaryTool",
    "DictionaryLookupRequest",
    "DictionaryLookupResponse",
    "srs_scheduler",
    "SRSScheduler",
    "SRSCard",
    "question_bank",
    "QuestionBank",
    "Question",
    "essay_scorer",
    "EssayScoringTool",
    "EssayScoringResult",
]
