from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.runtime.episode import EpisodeRuntime
from src.runtime.schemas import EpisodeTraceView
from src.verification.checks import collect_trace_evidence
from src.verification.runner import checks_from_policy, run_required_checks, verification_status
from src.verification.types import VerificationCheck, VerificationReport


class VerificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def verify_episode(self, episode_id: str) -> VerificationReport:
        trace = await EpisodeRuntime(self.db).get_episode_trace(episode_id)
        return build_verification_report(trace)


def build_verification_report(trace: EpisodeTraceView) -> VerificationReport:
    task_spec = trace.episode.task_spec or {}
    required_checks = checks_from_policy(task_spec)
    checks = run_required_checks(trace, required_checks)
    failed = [check for check in checks if not check.passed]
    status = verification_status(checks)
    evidence_refs = collect_trace_evidence(trace)
    return VerificationReport(
        episode_id=trace.episode.id,
        task_id=task_spec.get("task_id"),
        status=status,
        required_checks=required_checks,
        checks=checks,
        passed_count=sum(1 for check in checks if check.passed),
        failed_count=len(failed),
        warning_count=sum(
            1 for check in checks if not check.passed and check.severity == "warning"
        ),
        critical_failed_count=sum(
            1 for check in checks if not check.passed and check.severity == "critical"
        ),
        evidence_ref_count=len(evidence_refs),
        failed_reason="; ".join(check.message for check in failed) or None,
        generated_at=datetime.now(timezone.utc),
        metadata={
            "required_checks": required_checks,
            "source": task_spec.get("source"),
            "task_type": task_spec.get("task_type"),
            "trace_event_count": len(trace.events),
            "tool_call_count": len(trace.tool_calls),
        },
    )


async def verify_knowledge_exercise_episode(
    db: AsyncSession,
    episode_id: str,
    trace: EpisodeTraceView | None = None,
) -> dict[str, Any]:
    report = (
        build_verification_report(trace)
        if trace is not None
        else await VerificationService(db).verify_episode(episode_id)
    )
    return report.model_dump(mode="json")


def _run_check(name: str, trace: EpisodeTraceView) -> VerificationCheck:
    return run_required_checks(trace, [name])[0]
