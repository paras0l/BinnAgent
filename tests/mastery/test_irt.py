from src.adaptive.irt import predict_success, update_ability


def test_irt_probability_is_monotonic_in_ability_and_difficulty() -> None:
    assert predict_success(0.5, 0.8) < predict_success(0.5, 0.2)
    assert predict_success(0.8, 0.5) > predict_success(0.2, 0.5)


def test_hint_correct_has_smaller_ability_gain_than_independent_correct() -> None:
    independent = update_ability(
        0.4,
        outcome_score=1.0,
        item_difficulty=0.5,
        independent=True,
    )
    hinted = update_ability(
        0.4,
        outcome_score=1.0,
        item_difficulty=0.5,
        independent=False,
        hint_count=1,
    )
    assert independent.ability > hinted.ability > 0.4


def test_irt_result_is_explainable_and_versioned() -> None:
    result = update_ability(0.42, outcome_score=1.0, item_difficulty=0.61, independent=True)
    assert 0 <= result.predicted_success <= 1
    assert result.item_difficulty == 0.61
    assert result.model_version == "irt-1pl-v1"
