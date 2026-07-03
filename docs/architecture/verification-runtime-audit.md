# Verification Runtime Audit

> Updated: 2026-07-03

## Current VerificationReport

`VerificationReport` is a deterministic runtime report, not an LLM judge. It is built from `AgentEpisode`, `LearningEvent`, `ToolCallRecord`, `LearningGraphCheckpoint`, and `PromptExecutionRecord` data.

Current schema:

- `status`: `passed`, `warning`, or `failed`.
- `episode_id`, `task_id`, `required_checks`, `generated_at`.
- `checks[]`: each check has `name`, `check_type`, `passed`, `severity`, `expected`, `actual`, `source_node`, `source_event_type`, `source_tool_name`, `evidence_refs`, and `message`.
- Counters: `passed_count`, `failed_count`, `warning_count`, `critical_failed_count`, `evidence_ref_count`.
- `failed_reason` remains for older API consumers.
- `metadata` includes task/runtime summary fields.

Status rules:

- Any failed `critical` check makes the report `failed`.
- Failed `warning` checks make the report `warning` when no critical check failed.
- Failed `info` checks do not block `passed`.

## Current verify_episode Checks

`src/graph/nodes/verify_episode.py` emits a graph-level report from graph state. `src/verification/runner.py` emits persisted runtime reports from episode trace data.

Supported `TaskSpec.verification_policy.required_checks`:

- `task_prepared`
- `learner_answer_received`
- `exercise_attempt_created`
- `exercise_graded`
- `mastery_updated`
- `memory_event_written`
- `review_scheduled`
- `next_action_recommended`
- `episode_completed`
- `tool_calls_successful`
- `evidence_refs_present`
- `prompt_schema_valid`

Compatibility aliases are still accepted, including `exercise_attempt_saved`, `grading_result_exists`, `memory_written`, `evidence_non_empty`, and `mastery_update_valid`.

## TaskSpec Verification Policy

`TaskSpec.verification_policy.required_checks` drives the checks. If the list is empty, the runtime uses conservative default checks: `episode_started`, `exercise_answered`, and `exercise_graded`.

If `require_evidence=true`, `evidence_refs_present` is appended unless an equivalent evidence check is already present.

## Episode Status Coupling

Episode completion now depends on the generated `VerificationReport`:

- `passed` -> `episode.status="completed"`.
- `warning` -> `episode.status="completed_with_warnings"`.
- `failed` -> `episode.status="verification_failed"` with `failure_type="verification_failed"`.

Critical check failures cannot silently leave an episode as plain `completed`.

## Current EpisodeTraceView

`EpisodeTraceView` keeps the original fields:

- `episode`
- `events`
- `tool_calls`
- `checkpoint`

It now also returns:

- `verification_report`
- `graph_run`
- `prompt_executions`
- `evidence_refs`
- `node_summaries`

Checkpoint data includes status, `resume_from`, `answer_required`, `current_task_id`, `required_input_schema`, and summaries for `prompt_payload` / `state_snapshot`. Raw prompt/output is not exposed; raw LLM trace belongs in Langfuse.

## Dev Console Runtime Visibility

Dev Console can now inspect:

- Episode summary and task spec.
- Graph run identifiers: `thread_id`, `graph_run_id`, `session_id`.
- Checkpoint state and required input schema.
- Event timeline with evidence counts.
- Tool calls with hashes, latency, status, and error.
- Prompt execution summaries without raw prompt/output.
- Verification checks with severity, expected/actual, and evidence counts.
- Aggregated evidence refs.
- Node summaries.

Debug API paths:

- `GET /api/runtime/episodes/{episode_id}/trace`
- `GET /api/debug/graph-runs/{episode_id}`
- `GET /api/debug/graph-runs?learner_id=...`

Debug graph-run endpoints require `require_debug_access` and still validate learner ownership. Passing `learner_id` does not bypass episode scope checks.

## Remaining Gaps

- `node_summaries` are derived from existing event/source names, not yet from first-class node result records.
- Tool calls are episode-level `ToolCallRecord`s; broader graph tool event correlation remains future work.
- Prompt execution records are safe business summaries. Full prompt/output replay should stay in Langfuse.
- Production PostgresSaver and official LangGraph `interrupt()/Command(resume=...)` integration remain follow-up work.
