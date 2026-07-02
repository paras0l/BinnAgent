from src.simulation.scenario import SimulationReport, SimulationStepResult


class SimulationEvaluator:
    def build_report(
        self,
        *,
        persona_id: str,
        scenario_id: str,
        steps: list[SimulationStepResult],
        api_calls: int,
        api_successes: int,
        agent_triggers: int,
        memory_writes: int,
        runtime_metrics: dict[str, float | int] | None = None,
    ) -> SimulationReport:
        failures = [failure for step in steps for failure in step.failures]
        assertion_total = sum(1 for step in steps for _ in step.failures) + len(
            [step for step in steps if step.status == "passed"]
        )
        assertion_passes = len([step for step in steps if step.status == "passed"])
        return SimulationReport(
            persona=persona_id,
            scenario=scenario_id,
            status="passed" if not failures and all(step.status != "failed" for step in steps) else "failed",
            steps=steps,
            metrics={
                "api_success_rate": api_successes / api_calls if api_calls else 1.0,
                "agent_trigger_count": agent_triggers,
                "memory_write_count": memory_writes,
                "assertion_pass_rate": assertion_passes / assertion_total if assertion_total else 1.0,
            },
            runtime_metrics=runtime_metrics or {},
            failures=failures,
        )
