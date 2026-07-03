# Simulation / Evaluation Audit

Status: first-phase enhancement for issue #28.

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

Current `SimulationEvaluator` emits:

- `api_success_rate`
- `agent_trigger_count`
- `memory_write_count`
- `assertion_pass_rate`

Runtime metrics currently collected by `ScenarioRunner`:

- `episode_count`
- `completed_episode_count`
- `failed_episode_count`
- `verification_pass_count`
- `verification_fail_count`
- `avg_tool_latency_ms`

Scenario contracts can list `required_metrics`, but this phase does not yet enforce metric gates.

## Contract Simulation vs Integration/E2E

Current tests under `tests/simulation/` are contract simulations. They use `httpx.MockTransport` or deterministic graph stubs to verify scenario orchestration, assertion semantics, report shape, and expected runtime trace contracts.

They are not yet full integration or E2E runs against live PostgreSQL, Redis, Ollama, LangGraph checkpointing, and frontend flows.

Paths that still need integration/E2E coverage:

- live daily lesson checkpoint interrupt/resume with real database state
- live LearningOrchestrator trace with `ToolCallRecord`, `LearningEvent`, and verification report persistence
- vocabulary practice mastery/review/mistake updates against real DB migrations
- Vocabulary Agent deposit through real chat, model output, memory write, and vocabulary store
- Explore capability recommendation click-through from frontend to API to memory/event trace
- parser/RAG ingestion flows for textbook uploads and retrieval quality
- prompt/schema migrations through PromptExecutor and PromptExecutionRecord

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
- Changes under `src/prompts/**` may currently return no scenarios; prompt/schema simulation scenarios should be added in a later phase.
- Changes under `src/knowledge/processor.py` or parser/RAG code may currently return no parser/RAG scenarios; parser/RAG contract and E2E scenarios remain follow-up work.
