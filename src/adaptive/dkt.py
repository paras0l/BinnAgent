from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DKTShadowResult:
    predicted_success: float
    confidence: float
    model_version: str
    fallback_used: bool = False
    error: str | None = None


class DKTProvider(Protocol):
    def predict(self, *, current_mastery: float, outcome_score: float) -> float: ...


class DKTShadowPredictor:
    """Shadow-only adapter. The deterministic baseline keeps learning available on failure."""

    def __init__(self, provider: DKTProvider | None = None):
        self.provider = provider

    def predict(self, *, current_mastery: float, outcome_score: float) -> DKTShadowResult:
        if self.provider is not None:
            try:
                value = min(1.0, max(0.0, self.provider.predict(
                    current_mastery=current_mastery,
                    outcome_score=outcome_score,
                )))
                return DKTShadowResult(value, 0.72, "dkt-shadow-v1")
            except Exception as exc:
                error = str(exc)[:200]
            else:  # pragma: no cover
                error = None
        else:
            error = "provider_not_configured"
        baseline = min(1.0, max(0.0, current_mastery * 0.8 + outcome_score * 0.2))
        return DKTShadowResult(
            baseline,
            0.35,
            "dkt-shadow-baseline-v1",
            fallback_used=True,
            error=error,
        )
