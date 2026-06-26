from dataclasses import dataclass

from src.models.knowledge import KnowledgePoint


SCENARIOS = [
    {
        "name": "Meet a new friend",
        "setting": "first day at school",
        "zh": "校园见面",
    },
    {
        "name": "Classroom answer",
        "setting": "answering the teacher in class",
        "zh": "课堂问答",
    },
    {
        "name": "Introduce a classmate",
        "setting": "telling someone about your friend",
        "zh": "介绍朋友",
    },
    {
        "name": "Find something",
        "setting": "asking about an object on the desk",
        "zh": "找物品",
    },
    {
        "name": "Group task",
        "setting": "working with classmates",
        "zh": "小组任务",
    },
]


@dataclass(frozen=True)
class ExerciseBlueprint:
    knowledge_point: KnowledgePoint
    question_type: str
    cognitive_level: str
    scenario: dict[str, str]
    ordinal: int
    estimated_seconds: int


QUESTION_PLAN = [
    ("choice_context", "recognition", 35),
    ("fill_blank", "production", 45),
    ("dialogue_complete", "production", 55),
    ("error_fix", "production", 60),
    ("choice_context", "understanding", 40),
    ("fill_blank", "production", 45),
    ("dialogue_complete", "transfer", 65),
    ("error_fix", "transfer", 65),
]


def build_exercise_blueprints(points: list[KnowledgePoint], *, target_count: int = 8) -> list[ExerciseBlueprint]:
    if not points:
        return []

    blueprints: list[ExerciseBlueprint] = []
    for index in range(target_count):
        question_type, cognitive_level, estimated_seconds = QUESTION_PLAN[index % len(QUESTION_PLAN)]
        point = points[index % len(points)]
        scenario = SCENARIOS[index % len(SCENARIOS)]
        blueprints.append(
            ExerciseBlueprint(
                knowledge_point=point,
                question_type=question_type,
                cognitive_level=cognitive_level,
                scenario=scenario,
                ordinal=index + 1,
                estimated_seconds=estimated_seconds,
            )
        )
    return blueprints
