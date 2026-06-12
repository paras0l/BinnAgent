from src.graph.state import LearningState


async def run_learning_task(state: LearningState) -> dict:
    """Execute the learning task based on active_skill.

    For reading: fetch a question from the question bank.
    For writing: provide a writing prompt.
    For vocabulary: provide a vocabulary list.
    """
    active_skill = state.get("active_skill", "reading")
    target_exam = state.get("target_exam", "CET6")

    if active_skill == "reading":
        from src.tools.question_bank import question_bank

        exam_map = {"CET4": "CET-4", "CET6": "CET-6"}
        exam = exam_map.get(target_exam, "CET-6")
        questions = question_bank.get_questions(
            exam_type=exam, section="reading comprehension", limit=1
        )
        materials = []
        for q in questions:
            materials.append(
                {
                    "type": "reading_question",
                    "question_id": q.question_id,
                    "passage": q.passage or "",
                    "stem": q.stem,
                    "options": q.options,
                }
            )
        return {"input_materials": materials}

    elif active_skill == "writing":
        return {
            "input_materials": [
                {
                    "type": "writing_prompt",
                    "content": "Write an essay on the importance of environmental protection.",
                    "criteria": ["structure", "vocabulary", "grammar"],
                }
            ]
        }

    elif active_skill == "vocabulary":
        return {
            "input_materials": [
                {
                    "type": "vocabulary_list",
                    "words": [
                        {"word": "sustainable", "definition": "able to be maintained over time"},
                        {"word": "significant", "definition": "sufficiently great or important"},
                    ],
                }
            ]
        }

    return {"input_materials": []}
