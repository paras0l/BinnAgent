from src.simulation.behavior_policy import BehaviorPolicy
from src.simulation.persona import LearnerPersona


class SimulatedLearnerAgent:
    """A deterministic learner facade used by scenario steps."""

    def __init__(self, persona: LearnerPersona, seed: int = 42):
        self.persona = persona
        self.policy = BehaviorPolicy(persona=persona, seed=seed)

    def answer_vocabulary(self, word: str, prompt_type: str = "meaning") -> str:
        return self.policy.answer_vocabulary(word, prompt_type)

    def answer_spelling(self, word: str) -> str:
        return self.policy.answer_spelling(word)

    def answer_writing_phrase(self, phrase: str, exercise_type: str) -> str:
        return self.policy.answer_writing_phrase(phrase, exercise_type)

    def write_essay(self, topic: str) -> str:
        return self.policy.write_essay(topic)

    def decide_retry_or_skip(self, consecutive_errors: int) -> str:
        return self.policy.decide_retry_or_skip(consecutive_errors)
