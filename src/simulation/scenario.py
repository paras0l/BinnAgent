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
    module_tags: list[str] = field(default_factory=list)
    entrypoints: list[str] = field(default_factory=list)
    expected_events: list[str] = field(default_factory=list)
    expected_tool_calls: list[str] = field(default_factory=list)
    expected_state_changes: list[str] = field(default_factory=list)
    required_metrics: list[str] = field(default_factory=list)
    owner_module: str | None = None
    change_triggers: list[str] = field(default_factory=list)

    def contract_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "module_tags": self.module_tags,
            "entrypoints": self.entrypoints,
            "expected_events": self.expected_events,
            "expected_tool_calls": self.expected_tool_calls,
            "expected_state_changes": self.expected_state_changes,
            "required_metrics": self.required_metrics,
            "owner_module": self.owner_module,
            "change_triggers": self.change_triggers,
        }


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
    scenario_contract: dict[str, Any] | None = None
    run_id: str = field(default_factory=lambda: f"sim_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "persona": self.persona,
            "scenario": self.scenario,
            "scenario_contract": _json_safe(self.scenario_contract) if self.scenario_contract else None,
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
