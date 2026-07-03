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
