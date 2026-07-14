from src.adaptive.dkt import DKTShadowPredictor


class FailingProvider:
    def predict(self, *, current_mastery: float, outcome_score: float) -> float:
        raise TimeoutError("model timeout")


class FixedProvider:
    def predict(self, *, current_mastery: float, outcome_score: float) -> float:
        return 0.36


def test_dkt_shadow_accepts_versioned_provider_prediction() -> None:
    result = DKTShadowPredictor(FixedProvider()).predict(current_mastery=0.5, outcome_score=1)
    assert result.predicted_success == 0.36
    assert result.model_version == "dkt-shadow-v1"
    assert result.fallback_used is False


def test_dkt_failure_falls_back_without_breaking_learning() -> None:
    result = DKTShadowPredictor(FailingProvider()).predict(current_mastery=0.5, outcome_score=1)
    assert 0 <= result.predicted_success <= 1
    assert result.fallback_used is True
    assert "timeout" in (result.error or "")
