import httpx
import pytest

from src.simulation.fixtures import BUILTIN_PERSONAS, BUILTIN_SCENARIOS
from src.simulation.mock_transport import build_contract_transport
from src.simulation.runner import ScenarioRunner


@pytest.mark.asyncio
async def test_reading_workshop_completion_evidence_retry_and_dashboard_score() -> None:
    scenario = BUILTIN_SCENARIOS["reading_workshop_completion_evidence_idempotency"]

    async with httpx.AsyncClient(
        transport=build_contract_transport(scenario),
        base_url="http://test",
    ) as client:
        report = await ScenarioRunner(client).run(
            scenario=scenario,
            persona=BUILTIN_PERSONAS["grade7_low_vocab"],
        )

    assert report.status == "passed"
    assert report.metrics["api_success_rate"] == 1.0

    missing_evidence, unknown_sentence, completed, retried, dashboard = report.steps[-5:]
    assert missing_evidence.output["status_code"] == 422
    assert unknown_sentence.output["status_code"] == 422
    assert completed.output["completion"]["attempt_id"] == retried.output["completion"]["attempt_id"]
    assert retried.output["idempotent_replay"] is True
    assert dashboard.output["reading_ability"] == {
        "label": "阅读",
        "value": 78,
        "evidence_count": 1,
    }
