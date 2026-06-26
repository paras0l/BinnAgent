import random

from src.knowledge.exercise_blueprints import ExerciseBlueprint
from src.models.knowledge import ExerciseQuestion, KnowledgePoint

GENERATOR_VERSION = "exercise-blueprint-v2"


def _clean(text: str) -> str:
    return " ".join(text.strip().split())


def _target_expression(point: KnowledgePoint) -> str:
    content = point.content or {}
    examples = content.get("examples") if isinstance(content, dict) else None
    if isinstance(examples, list) and examples:
        first = str(examples[0]).strip()
        if first:
            return first
    return _clean(point.title)


def _distractors(point: KnowledgePoint, peers: list[KnowledgePoint]) -> list[str]:
    peer_titles = [
        _clean(peer.title)
        for peer in peers
        if peer.id != point.id and _clean(peer.title) != _clean(point.title)
    ]
    teaching_errors = [
        "I name Linda.",
        "Good night.",
        "Name I am Linda.",
        "I am fine name.",
    ]
    values = [*peer_titles, *teaching_errors]
    unique: list[str] = []
    for value in values:
        if value and value not in unique and value != point.title:
            unique.append(value)
    return unique[:3]


def _metadata(blueprint: ExerciseBlueprint, *, rubric: dict) -> dict:
    point = blueprint.knowledge_point
    return {
        "generator": GENERATOR_VERSION,
        "generator_version": GENERATOR_VERSION,
        "cognitive_level": blueprint.cognitive_level,
        "interaction": {
            "type": blueprint.question_type,
            "input_mode": "choice" if blueprint.question_type == "choice_context" else "text",
            "allow_retry": True,
            "hint_levels": 2,
        },
        "scenario": blueprint.scenario,
        "rubric": rubric,
        "source": {
            "knowledge_point_id": str(point.id),
            "page_number": point.source_page,
            "evidence": point.summary,
        },
        "estimated_seconds": blueprint.estimated_seconds,
    }


def build_question(
    blueprint: ExerciseBlueprint,
    *,
    source_id,
    curriculum_node_id,
    peers: list[KnowledgePoint],
) -> ExerciseQuestion:
    point = blueprint.knowledge_point
    target = _target_expression(point)
    scenario = blueprint.scenario

    if blueprint.question_type == "choice_context":
        distractors = _distractors(point, peers)
        options = [target, *distractors]
        random.Random(f"{point.id}:{blueprint.ordinal}").shuffle(options)
        stem = (
            f"场景：{scenario['zh']}。{scenario['setting']}。\n"
            f"你想表达「{point.summary}」时，哪一句最自然？"
        )
        answer = target
        explanation = f"在这个场景里，{target} 能自然表达：{point.summary}"
        rubric = {
            "target_expression": target,
            "acceptable_answers": [target],
            "error_types": ["meaning_confusion", "unnatural_expression"],
            "hint": f"先想这个场景需要表达的是：{point.summary}",
        }
    elif blueprint.question_type == "fill_blank":
        stem = (
            f"场景：{scenario['zh']}。补全句子，让它适合这个情境。\n"
            f"A: Hello! I am Jack.\nB: Hi, Jack. ______\n目标：使用「{point.title}」相关表达。"
        )
        answer = target
        explanation = f"填空题重点是主动使用「{point.title}」。可接受表达包括：{target}。"
        rubric = {
            "target_expression": target,
            "acceptable_answers": [target, target.replace("I'm", "I am")],
            "error_types": ["missing_target_expression", "grammar"],
            "hint": f"注意把「{point.title}」放进完整句子里。",
        }
        options = []
    elif blueprint.question_type == "dialogue_complete":
        stem = (
            f"场景：{scenario['zh']}。\n"
            "补全对话，只写 B 的回答。\n"
            "A: Good morning!\n"
            "B: ______\n"
            f"目标：练习「{point.title}」在真实对话中的使用。"
        )
        answer = target
        explanation = f"对话补全要看上文语境，并用自然、简短的回应承接「{point.title}」。"
        rubric = {
            "target_expression": target,
            "acceptable_answers": [target, f"{target}."],
            "error_types": ["context_mismatch", "missing_target_expression"],
            "hint": "先回应对方，再使用目标表达。",
        }
        options = []
    else:
        wrong_sentence = f"I name {target.strip('.!')}"
        stem = (
            f"场景：{scenario['zh']}。下面这句话不自然，请改成更自然的一句。\n"
            f"{wrong_sentence}\n"
            f"目标：修正后要能表达「{point.summary}」。"
        )
        answer = target
        explanation = f"这类错误通常是语序或 be 动词问题。更自然的表达是：{target}"
        rubric = {
            "target_expression": target,
            "acceptable_answers": [target, target.replace("I'm", "I am")],
            "error_types": ["word_order", "missing_be"],
            "hint": "英文自我介绍常用 I'm... 或 My name is...，不要直译中文语序。",
        }
        options = []

    base_difficulty = point.difficulty if point.difficulty is not None else 0.3
    return ExerciseQuestion(
        source_id=source_id,
        curriculum_node_id=curriculum_node_id,
        knowledge_point_id=point.id,
        question_type=blueprint.question_type,
        stem=stem,
        options=options,
        answer=answer,
        explanation=explanation,
        difficulty=min(1.0, max(0.1, base_difficulty + blueprint.ordinal * 0.02)),
        status="published",
        metadata_=_metadata(blueprint, rubric=rubric),
    )
