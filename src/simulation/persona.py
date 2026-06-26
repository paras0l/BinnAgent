from dataclasses import dataclass, field


@dataclass(frozen=True)
class LearnerPersona:
    """Long-lived profile used by deterministic simulation runs."""

    id: str
    name: str
    level: str
    target: str
    known_words: set[str] = field(default_factory=set)
    weak_words: set[str] = field(default_factory=set)
    weak_patterns: set[str] = field(default_factory=set)
    writing_weaknesses: set[str] = field(default_factory=set)
    motivation: float = 0.7
    patience: float = 0.7
    carelessness: float = 0.2
    hint_acceptance: float = 0.7
    review_compliance: float = 0.8
