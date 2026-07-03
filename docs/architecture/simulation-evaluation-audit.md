# Simulation / Evaluation Audit

Status: issue #28 simulation mode layering + evaluator baseline gate.

## Runner Modes

`scripts/run_learner_simulation.py` now has three explicit modes:

| Mode | Transport | Model | Default use |
| --- | --- | --- | --- |
| `contract` | `httpx.MockTransport` via `src/simulation/mock_transport.py` | No real model calls; deterministic graph stub for direct graph steps | Default CI / Codex regression safety net |
| `integration` | `httpx.ASGITransport(app=app)` | `DeterministicFakeModelRouter` dependency override | Manual or nightly backend regression with FastAPI wiring |
| `e2e` | Real `--base-url` | Whatever the target environment provides | Local/manual full-stack regression only |

Contract mode validates API contract shape, scenario ordering, assertion semantics, scenario contract fields and evaluator metrics without requiring PostgreSQL, Redis, Ollama, or a running server. Integration mode exercises FastAPI routing and dependency injection while avoiding real LLM randomness through the deterministic fake model provider.

## Built-in Personas

| Persona | Level | Target | Main weak signals |
| --- | --- | --- | --- |
| `grade7_low_vocab` | beginner | `grade7_textbook` | weak vocabulary, word order, missing `be` |
| `grade7_recognition_only` | beginner | `grade7_textbook` | recognition-heavy, weak production |
| `cet_transition_weak` | intermediate | `CET6` | weak transition phrases, writing overuses simple sequencing |
| `vocabulary_deposit_user` | intermediate | `CET6` | vocabulary deposit workflow |
| `frustrated_retry_light` | beginner | `grade7_textbook` | low patience, retry/skip behavior |

## Built-in Scenarios

| Scenario | Entrypoints | Module tags |
| --- | --- | --- |
| `smoke_learning_journey` | learner creation, `/api/chat/send`, memory summary, `daily_lesson_graph` | `chat`, `memory`, `daily_graph`, `runtime` |
| `vocabulary_agent_deposit` | `/api/chat/send`, vocabulary list API | `vocabulary`, `memory`, `chat` |
| `vocabulary_practice_adaptation` | vocabulary add/session/attempt APIs | `vocabulary`, `mastery`, `review`, `mistake` |
| `episode_runtime_knowledge_practice` | daily plan, daily lesson start/answer, runtime trace, verification report | `runtime`, `exercise`, `mastery`, `memory`, `verification` |
| `daily_lesson_capability_recommendation` | daily lesson answer, Explore capability event, runtime trace | `daily_lesson`, `recommendation`, `explore`, `memory`, `verification` |
| `daily_lesson_checkpoint_resume` | daily lesson start/answer, runtime trace | `langgraph`, `checkpoint`, `daily_lesson`, `exercise`, `mastery`, `memory`, `verification` |
| `daily_lesson_missing_answer_must_not_write_memory` | daily lesson start, runtime trace | `langgraph`, `checkpoint`, `daily_lesson`, `memory` |
| `llm_json_missing_field_triggers_repair` | exercise generation | `prompt_schema`, `exercise`, `integration`, `model_provider` |

Every built-in scenario now declares a contract:

- `module_tags`
- `entrypoints`
- `expected_events`
- `expected_tool_calls`
- `expected_state_changes`
- `required_metrics`
- `owner_module`
- `change_triggers`

`SimulationReport.to_dict()` includes `scenario_contract` while keeping the original top-level `scenario`, `steps`, `metrics`, `runtime_metrics`, and `failures` fields.

## SimulationReport Fields

Current report fields:

- `run_id`
- `mode`
- `persona`
- `scenario`
- `scenario_contract`
- `status`
- `steps[]`: each step has `name`, `status`, `evidence`, public `output`, and `failures[]`
- `metrics`: backward-compatible flat summary metrics
- `runtime_metrics`: raw runner-collected runtime signals
- `metric_groups`: grouped evaluator metrics
- `baseline_comparison`: baseline diff result or `baseline_found=false`
- `regressions[]`: metrics that moved in the wrong direction against baseline
- `threshold_failures[]`: metrics that violated configured thresholds
- `failures[]`: flattened assertion/runtime failures from failed steps

## AssertionEngine Support

Legacy assertion types:

- `status_code`
- `exists`
- `not_empty`
- `equals`
- `contains`
- `gte`

Agent Runtime assertion types added in this phase:

- `event_exists`
- `event_order`
- `tool_called`
- `tool_success_rate_gte`
- `value_between`
- `delta_gte`
- `evidence_ref_exists`
- `verification_check_passed`
- `memory_event_type_exists`
- `recommendation_contains_capability`
- `no_unexpected_error`

All assertion types use the existing dotted path lookup and return assertion failures instead of raising when a path points at an unexpected structure.

## Evaluator Metrics

Backward-compatible flat `metrics`:

- `api_success_rate`
- `agent_trigger_count`
- `memory_write_count`
- `assertion_pass_rate`

Raw `runtime_metrics` currently collected by `ScenarioRunner`:

- `episode_count`
- `completed_episode_count`
- `failed_episode_count`
- `verification_pass_count`
- `verification_fail_count`
- `avg_tool_latency_ms`
- `tool_statuses`
- `tool_latencies_ms`
- `event_types`
- `verification_statuses`
- `recommendation_generated_count`
- `recommendation_contains_expected_count`
- `capability_click_recorded_count`
- `memory_event_count`
- `memory_recall_count`
- `prompt_executions`

## Simulation Metrics Groups

`metric_groups` has six stable namespaces:

- `runtime`: episode counts/rates, verification pass rate, tool success rate, average and p95 tool latency.
- `learning`: exercise attempt count, grading success, mastery update count, mastery delta direction, review schedule count.
- `memory`: memory write/event count, expected memory event coverage, memory evidence ref coverage, recall count.
- `recommendation`: capability recommendation generation, expected recommendation coverage, relevance pass rate, click count.
- `parser_rag`: RAG retrieval result count, RAG evidence coverage, source page coverage, parser quality score.
- `prompt_schema`: prompt execution count, schema validation pass/fail rate, JSON repair/fallback counts, prompt hash/model policy coverage.

Current contract simulations can reliably infer runtime event/tool metrics, daily lesson recommendation counts, memory update counts, vocabulary attempt counts, and PromptExecutionRecord-shaped metrics when supplied in `runtime_metrics.prompt_executions`.

## Deterministic Fake Model Provider

`src/simulation/fake_model.py` provides `DeterministicFakeModelRouter` for integration simulations. It supports:

- structured JSON output for response-schema requests
- schema-invalid output via `metadata.simulation_fake_output=schema_invalid`
- repaired JSON output for `exercise_generate`, with `usage.retry_count=1`
- deterministic embeddings for RAG-facing integration paths

The fake provider is only installed through simulation dependency overrides. Production model routing remains unchanged.

Metrics that still need integration/E2E mode for reliable statistics:

- parser quality score and source page coverage from real textbook parsing
- RAG retrieval evidence quality from real embeddings/search
- prompt execution metrics from live `prompt_execution_records`
- memory recall hit quality from real retrieval contexts
- frontend click-through timing and full user journey latency
- long-run mastery delta quality across multiple sessions

## Baseline Comparison

Baseline files live under `var/simulation/baselines/{scenario_id}.json` and contain:

- `scenario_id`
- `version`
- backward-compatible `metrics`
- grouped `metric_groups`
- optional `thresholds`

`src/simulation/baseline.py` compares current report metrics against the baseline and writes:

- `baseline_comparison.baseline_found`
- `baseline_comparison.metric_diffs[]`
- `regressions[]`

Regression rules are directional:

- pass/success/count/rate metrics regress when current is lower than baseline
- latency metrics regress when current is higher than baseline

Missing baselines do not fail the run; the report records `baseline_found=false`.

## Threshold Gate

Thresholds support:

- `min`
- `max`
- `equals`

Nested metric paths are supported, for example:

```json
{
  "runtime.verification_pass_rate": { "min": 1.0 },
  "runtime.avg_tool_latency_ms": { "max": 1000 }
}
```

`scripts/run_learner_simulation.py` supports:

```bash
python scripts/run_learner_simulation.py --mode contract --scenario episode_runtime_knowledge_practice
python scripts/run_learner_simulation.py --mode contract --all
python scripts/run_learner_simulation.py --mode contract --tag langgraph
python scripts/run_learner_simulation.py --mode integration --scenario llm_json_missing_field_triggers_repair
python scripts/run_learner_simulation.py --mode e2e --base-url http://localhost:8000 --scenario smoke_learning_journey
python scripts/run_learner_simulation.py --mode contract --all --report-dir var/simulation/reports
python scripts/run_learner_simulation.py --scenario episode_runtime_knowledge_practice --fail-on-threshold
python scripts/run_learner_simulation.py --scenario episode_runtime_knowledge_practice --fail-on-regression
python scripts/run_learner_simulation.py --scenario episode_runtime_knowledge_practice --update-baseline
```

`--update-baseline` should be used only after reviewing that behavior changes are intentional and healthy. If a core learning loop regresses, fix the product code or scenario contract instead of updating the baseline to accept the regression.

Do not update baselines when:

- assertion failures indicate the scenario no longer exercises the intended flow
- verification, tool success, or memory write rates dropped unexpectedly
- latency rose because of a bug or accidental blocking call
- prompt/schema validation failures increased without a planned prompt migration

Update baselines when:

- a scenario contract intentionally changes
- a metric becomes more accurate because the runner now collects better signals
- a product behavior improvement changes expected counts or latencies and the new value has been reviewed

## CI / Codex Workflow

Recommended workflow:

- Contract simulation is default CI: `python scripts/run_learner_simulation.py --mode contract --all`.
- Integration simulation is manual or nightly: run selected scenarios with `--mode integration`.
- E2E simulation is local/manual only and requires a real `--base-url`.
- For changes under `src/graph/**`, `src/memory/**`, `src/mastery/**`, `src/prompts/**`, or `src/knowledge/**`, run `scripts/list_impacted_simulations.py` and then run the returned scenarios.

Current tests under `tests/simulation/` remain contract-level unit tests. They use `httpx.MockTransport`, deterministic fake outputs, or graph stubs to verify scenario orchestration, assertion semantics, report shape, and expected runtime trace contracts.

Paths that still need integration/E2E coverage:

- live daily lesson checkpoint interrupt/resume with real database state
- live LearningOrchestrator trace with `ToolCallRecord`, `LearningEvent`, and verification report persistence
- vocabulary practice mastery/review/mistake updates against real DB migrations
- Vocabulary Agent deposit through real chat, model output, memory write, and vocabulary store
- Explore capability recommendation click-through from frontend to API to memory/event trace
- parser/RAG ingestion flows for textbook uploads and retrieval quality
- prompt/schema migrations through PromptExecutor and PromptExecutionRecord
- frontend Dev Console simulation dashboard interactions

## Impacted Simulation Script

Use `scripts/list_impacted_simulations.py` to derive which scenarios should run for a set of changed files:

```bash
python scripts/list_impacted_simulations.py --changed-files src/graph/main_graph.py src/learning/orchestrator.py
python scripts/list_impacted_simulations.py --changed-files-file changed_files.txt
python scripts/list_impacted_simulations.py --json --changed-files src/prompts/registry.py
```

Matching supports `src/graph/**`, concrete files such as `src/api/daily_lessons.py`, and directory prefixes.

Current guidance:

- Changes under `src/graph/**`: run `smoke_learning_journey` and `daily_lesson_checkpoint_resume`.
- Changes under `src/learning/**`, `src/mastery/**`, `src/memory/**`, or `src/verification/**`: run runtime/daily lesson scenarios returned by the script.
- Changes under vocabulary API/model/store code: run `vocabulary_agent_deposit` and/or `vocabulary_practice_adaptation`.
- Changes under `src/prompts/**`: run `llm_json_missing_field_triggers_repair` and prompt evals.
- Changes under `src/knowledge/**`: run impacted runtime/knowledge scenarios and parser evaluation where applicable.
