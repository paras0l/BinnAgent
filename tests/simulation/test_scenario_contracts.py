from src.simulation.fixtures import BUILTIN_SCENARIOS


def test_builtin_scenarios_declare_contract_tags_and_triggers() -> None:
    for scenario in BUILTIN_SCENARIOS.values():
        assert scenario.module_tags, scenario.id
        assert scenario.entrypoints, scenario.id
        assert scenario.required_metrics, scenario.id
        assert scenario.change_triggers, scenario.id


def test_scenario_contract_dict_is_report_safe() -> None:
    scenario = BUILTIN_SCENARIOS["daily_lesson_checkpoint_resume"]

    contract = scenario.contract_dict()

    assert contract["id"] == "daily_lesson_checkpoint_resume"
    assert "langgraph" in contract["module_tags"]
    assert "exercise.grade" in contract["expected_tool_calls"]


def test_daily_lesson_runtime_closure_scenarios_exist() -> None:
    required = {
        "daily_lesson_checkpoint_resume_after_restart",
        "daily_lesson_missing_answer_must_not_write_memory",
        "daily_lesson_wrong_answer_updates_mastery_down",
        "daily_lesson_correct_answer_updates_mastery_up",
        "daily_lesson_checkpoint_resume",
        "vocabulary_practice_adaptation",
        "episode_runtime_knowledge_practice",
        "llm_json_missing_field_triggers_repair",
    }

    assert required <= set(BUILTIN_SCENARIOS)


def test_reading_workshop_completion_scenario_exists() -> None:
    scenario = BUILTIN_SCENARIOS["reading_workshop_completion_evidence_idempotency"]

    assert scenario.owner_module == "reading"
    assert "idempotency" in scenario.module_tags
    assert "src/api/reading.py" in scenario.change_triggers
    assert any(step.action == "analyze_reading_sentence" for step in scenario.steps)
