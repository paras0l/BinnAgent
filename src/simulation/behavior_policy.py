import random
from dataclasses import dataclass, field

from src.simulation.persona import LearnerPersona


SPELLING_MISTAKES = {
    "telephone": "telphone",
    "morning": "monring",
    "significant": "signifcant",
    "sustainable": "sustanable",
    "friend": "freind",
    "number": "nuber",
}


@dataclass
class BehaviorPolicy:
    """Rule-based behavior for CI-stable learner simulations."""

    persona: LearnerPersona
    seed: int = 42
    _rng: random.Random = field(init=False, repr=False)
    _success_by_skill: dict[str, int] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def answer_vocabulary(self, word: str, prompt_type: str = "meaning") -> str:
        normalized = word.casefold().strip()
        if normalized in self.persona.known_words:
            return word
        if normalized in self.persona.weak_words:
            probability = 0.6 if prompt_type in {"choice", "recognition"} else 0.35
            if self._rng.random() < probability:
                return word
            return self.plausible_wrong_answer(normalized)
        return "I don't know"

    def answer_spelling(self, word: str) -> str:
        normalized = word.casefold().strip()
        if normalized in self.persona.known_words and self._rng.random() > self.persona.carelessness:
            return word
        return SPELLING_MISTAKES.get(normalized, normalized[:-1] if len(normalized) > 3 else "")

    def answer_writing_phrase(self, phrase: str, exercise_type: str) -> str:
        if "overuse_first_second_third" in self.persona.writing_weaknesses:
            if self._success_by_skill.get("transition_phrases", 0) < 2:
                return "First, it is important."
        return phrase

    def write_essay(self, topic: str) -> str:
        if "overuse_first_second_third" in self.persona.writing_weaknesses:
            return (
                f"First, {topic} is important. "
                "Second, it saves time. "
                "Third, it is useful."
            )
        return (
            f"To begin with, {topic} is important. "
            "Furthermore, it saves time. "
            "What is more noteworthy is that it requires self-discipline."
        )

    def decide_retry_or_skip(self, consecutive_errors: int) -> str:
        if self.persona.patience < 0.5 and consecutive_errors >= 2:
            return "skip"
        return "retry"

    def record_success(self, skill: str) -> None:
        self._success_by_skill[skill] = self._success_by_skill.get(skill, 0) + 1

    @staticmethod
    def plausible_wrong_answer(word: str) -> str:
        if word in SPELLING_MISTAKES:
            return SPELLING_MISTAKES[word]
        if len(word) > 4:
            return word[:-1]
        return "not sure"
