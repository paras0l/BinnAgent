from src.simulation.persona import LearnerPersona
from src.simulation.scenario import SimulationScenario, SimulationStep


BUILTIN_PERSONAS: dict[str, LearnerPersona] = {
    "grade7_low_vocab": LearnerPersona(
        id="grade7_low_vocab",
        name="Grade 7 low vocabulary learner",
        level="beginner",
        target="grade7_textbook",
        known_words={"hello", "name", "morning"},
        weak_words={"telephone", "number", "friend"},
        weak_patterns={"word_order", "missing_be"},
        motivation=0.7,
        patience=0.6,
        carelessness=0.25,
        hint_acceptance=0.8,
    ),
    "grade7_recognition_only": LearnerPersona(
        id="grade7_recognition_only",
        name="Grade 7 recognition-heavy learner",
        level="beginner",
        target="grade7_textbook",
        known_words={"hello", "morning", "friend"},
        weak_words={"telephone", "number", "spell"},
        weak_patterns={"context_use", "production"},
        motivation=0.75,
        patience=0.7,
    ),
    "cet_transition_weak": LearnerPersona(
        id="cet_transition_weak",
        name="CET writing transition learner",
        level="intermediate",
        target="CET6",
        known_words={"important", "useful", "online"},
        weak_words={"significant", "sustainable", "evidence"},
        weak_patterns={"weak_transition"},
        writing_weaknesses={"overuse_first_second_third"},
        motivation=0.8,
        patience=0.75,
    ),
    "vocabulary_deposit_user": LearnerPersona(
        id="vocabulary_deposit_user",
        name="Vocabulary deposit learner",
        level="intermediate",
        target="CET6",
        known_words={"evidence"},
        weak_words={"significant", "sustainable"},
        weak_patterns=set(),
    ),
    "frustrated_retry_light": LearnerPersona(
        id="frustrated_retry_light",
        name="Easily frustrated learner",
        level="beginner",
        target="grade7_textbook",
        known_words={"hello"},
        weak_words={"telephone", "friend"},
        weak_patterns={"missing_be"},
        motivation=0.45,
        patience=0.35,
        hint_acceptance=0.9,
    ),
}


BUILTIN_SCENARIOS: dict[str, SimulationScenario] = {
    "smoke_learning_journey": SimulationScenario(
        id="smoke_learning_journey",
        name="Smoke learning journey",
        persona_id="grade7_low_vocab",
        steps=[
            SimulationStep(
                name="create_learner",
                action="create_learner",
                assertions=[{"type": "exists", "path": "json.id"}],
            ),
            SimulationStep(
                name="chat",
                action="chat",
                payload={"message": "I want to practice English vocabulary today."},
                assertions=[
                    {"type": "exists", "path": "json.thread_id"},
                    {"type": "exists", "path": "json.message_id"},
                ],
            ),
            SimulationStep(
                name="memory_summary",
                action="memory_summary",
                assertions=[{"type": "status_code", "path": "status_code", "equals": 200}],
            ),
            SimulationStep(
                name="daily_graph",
                action="daily_graph",
                assertions=[
                    {"type": "not_empty", "path": "graph.input_materials"},
                    {"type": "exists", "path": "graph.agent_feedback"},
                    {"type": "not_empty", "path": "graph.memory_candidates"},
                    {"type": "not_empty", "path": "graph.review_items"},
                ],
            ),
        ],
    ),
    "vocabulary_agent_deposit": SimulationScenario(
        id="vocabulary_agent_deposit",
        name="Vocabulary agent deposit loop",
        persona_id="vocabulary_deposit_user",
        steps=[
            SimulationStep(name="create_learner", action="create_learner"),
            SimulationStep(
                name="chat_with_vocabulary_skill",
                action="chat",
                payload={
                    "message": "Please explain significant, sustainable, evidence and add them to my vocabulary book.",
                    "skill_id": "vocabulary_deposit",
                },
                assertions=[
                    {"type": "equals", "path": "json.skill_id", "value": "vocabulary_deposit"},
                    {"type": "gte", "path": "vocabulary_agent.saved_count", "value": 1},
                ],
            ),
            SimulationStep(
                name="list_vocabulary",
                action="list_vocabulary",
                assertions=[
                    {"type": "not_empty", "path": "json"},
                    {"type": "gte", "path": "vocabulary.total", "value": 1},
                ],
            ),
        ],
    ),
    "vocabulary_practice_adaptation": SimulationScenario(
        id="vocabulary_practice_adaptation",
        name="Vocabulary practice adaptation",
        persona_id="grade7_low_vocab",
        steps=[
            SimulationStep(name="create_learner", action="create_learner"),
            SimulationStep(
                name="seed_vocabulary",
                action="add_vocabulary",
                payload={"words": ["morning", "telephone", "number", "friend", "significant"]},
                assertions=[{"type": "gte", "path": "vocabulary.total", "value": 5}],
            ),
            SimulationStep(
                name="new_practice_attempt",
                action="vocabulary_practice",
                payload={"mode": "new", "limit": 2},
                assertions=[
                    {"type": "exists", "path": "attempt.attempt_id"},
                    {"type": "exists", "path": "attempt.result"},
                    {"type": "exists", "path": "detail.mastery"},
                    {"type": "exists", "path": "summary.status"},
                ],
            ),
            SimulationStep(
                name="spelling_mistake_attempt",
                action="vocabulary_practice",
                payload={"mode": "spelling", "limit": 1},
                assertions=[
                    {"type": "equals", "path": "attempt.result", "value": "incorrect"},
                    {"type": "exists", "path": "attempt.error_type"},
                    {"type": "not_empty", "path": "detail.mistakes"},
                ],
            ),
        ],
    ),
}
