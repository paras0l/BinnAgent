import uuid
from datetime import datetime, timezone

from src.evidence.types import EvidenceRef
from src.verification.types import VerificationCheck, VerificationReport


def test_verification_report_schema_counts_and_evidence_refs() -> None:
    now = datetime.now(timezone.utc)
    evidence = EvidenceRef(evidence_type="exercise_attempt", evidence_id=str(uuid.uuid4()))
    checks = [
        VerificationCheck(
            name="exercise_graded",
            check_type="event",
            passed=True,
            severity="critical",
            evidence_refs=[evidence],
            message="Found exercise_graded event.",
        ),
        VerificationCheck(
            name="memory_event_written",
            check_type="event",
            passed=False,
            severity="warning",
            expected="event:memory_written",
            actual=[],
            message="Missing event memory_written.",
        ),
    ]

    report = VerificationReport(
        episode_id=str(uuid.uuid4()),
        task_id="task-1",
        status="warning",
        required_checks=["exercise_graded", "memory_event_written"],
        checks=checks,
        passed_count=1,
        failed_count=1,
        warning_count=1,
        critical_failed_count=0,
        evidence_ref_count=1,
        generated_at=now,
    )

    payload = report.model_dump(mode="json")
    assert payload["status"] == "warning"
    assert payload["required_checks"] == ["exercise_graded", "memory_event_written"]
    assert payload["checks"][0]["severity"] == "critical"
    assert payload["checks"][0]["message"] == "Found exercise_graded event."
    assert payload["evidence_ref_count"] == 1
