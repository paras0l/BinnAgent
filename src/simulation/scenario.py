from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
import uuid


StepStatus = Literal["passed", "failed", "skipped"]


@dataclass(frozen=True)
class SimulationStep:
    name: str
    action: str
    payload: dict[str, Any] = field(default_factory=dict)
    assertions: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class SimulationScenario:
    id: str
    name: str
    persona_id: str
    steps: list[SimulationStep]


@dataclass
class SimulationStepResult:
    name: str
    status: StepStatus
    evidence: list[str] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)


@dataclass
class SimulationReport:
    persona: str
    scenario: str
    status: StepStatus
    steps: list[SimulationStepResult]
    metrics: dict[str, float | int]
    failures: list[str]
    runtime_metrics: dict[str, float | int] = field(default_factory=dict)
    run_id: str = field(default_factory=lambda: f"sim_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "persona": self.persona,
            "scenario": self.scenario,
            "status": self.status,
            "steps": [
                {
                    "name": step.name,
                    "status": step.status,
                    "evidence": step.evidence,
                    "output": _json_safe(step.output),
                    "failures": step.failures,
                }
                for step in self.steps
            ],
            "metrics": self.metrics,
            "runtime_metrics": self.runtime_metrics,
            "failures": self.failures,
        }


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_safe(item) for item in value]

    content = getattr(value, "content", None)
    if content is not None:
        return {
            "type": value.__class__.__name__,
            "content": _json_safe(content),
        }

    return str(value)
