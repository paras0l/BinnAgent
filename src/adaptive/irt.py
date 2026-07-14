import math
from dataclasses import dataclass


@dataclass(frozen=True)
class IRTResult:
    predicted_success: float
    ability: float
    item_difficulty: float
    model_version: str = "irt-1pl-v1"


def _logit_probability(value: float) -> float:
    value = min(12.0, max(-12.0, value))
    return 1.0 / (1.0 + math.exp(-value))


def normalized_to_logit(value: float) -> float:
    bounded = min(0.999, max(0.001, float(value)))
    return math.log(bounded / (1.0 - bounded))


def predict_success(ability: float, item_difficulty: float) -> float:
    """Rasch/1PL probability for normalized 0..1 ability and difficulty."""
    return _logit_probability(normalized_to_logit(ability) - normalized_to_logit(item_difficulty))


def update_ability(
    ability: float,
    *,
    outcome_score: float,
    item_difficulty: float,
    independent: bool,
    hint_count: int = 0,
    retry_count: int = 0,
    learning_rate: float = 0.22,
) -> IRTResult:
    predicted = predict_success(ability, item_difficulty)
    reliability = 1.0 if independent else 0.55
    reliability *= max(0.25, 1.0 - min(hint_count, 4) * 0.12 - min(retry_count, 3) * 0.1)
    updated = min(
        1.0,
        max(0.0, ability + learning_rate * reliability * (float(outcome_score) - predicted)),
    )
    return IRTResult(
        predicted_success=predict_success(updated, item_difficulty),
        ability=updated,
        item_difficulty=item_difficulty,
    )
