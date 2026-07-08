# Prompt Execution Governance

Status: issue #29 PromptExecutor migration closure.

## Mandatory PromptExecutor Boundary

All new prompt-like model calls must go through `PromptExecutor`.

Do not call `ModelRouter.chat()` or `ModelRouter.stream_chat()` directly from API, graph, agent, tool, memory, mastery, knowledge, or provider-adjacent business modules. The only prompt gateway allowed to call model chat/stream directly is `src/prompts/executor.py`.

Required workflow for a new prompt:

1. Add a versioned template under `src/prompts/versions/`.
2. Register `PromptMetadata` in `src/prompts/registry.py` with owner, purpose, template path and `model_policy`.
3. For structured output, add the JSON schema to `src/prompts/schemas.py`, bind `output_schema`, and add an eval set under `evals/prompts/`.
4. Call the prompt through `PromptExecutor.execute()`, `execute_messages()`, `stream_messages()`, or `execute_with_raw_output()` depending on runtime shape.
5. For learner-facing writes, use only `decision == accepted` and `validated_output`; fallback output defaults to review-required unless the business flow explicitly keeps it out of automatic writes.
6. Add or update regression tests and include the prompt in `scripts/evaluate_prompts.py --all` when it has structured output.

## Boundary between Langfuse and BinnAgent

Langfuse remains the source of truth for model-call observability:

- raw prompt and rendered messages
- raw model output
- latency
- token usage
- cost
- trace UI and provider/model-level inspection

BinnAgent stores only a lightweight business index in `prompt_execution_records`:

- learner / episode / task / source module references
- `prompt_id`, version, `prompt_hash`, and `input_hash`
- input/output schema names
- model policy snapshot
- Langfuse trace / observation references when available
- schema validation status and error summary
- repair/fallback flags and parse mode
- confidence and business decision
- optional target type/id

This avoids duplicating `ModelCallLog` while still making learner-facing writes auditable.

## Why not a complete local ModelCallLog

The repository already has historical runtime model-call concepts, but issue #29 keeps this PR intentionally smaller:

- Langfuse is better suited for raw prompt/output inspection and model metrics.
- Storing raw prompt/output locally increases privacy and data-retention surface area.
- Token, cost, and latency are provider observability concerns, not business write-governance fields.
- The local product needs to answer a narrower question: “Was this structured output validated, repaired, accepted, rejected, or sent to review?”

## Schema-first rule

Structured LLM output must pass schema validation before it can be accepted by business code that writes Memory, Mastery, KnowledgePoint, Vocabulary, generated exercises, dictionary fields, or WritingPhrase data.

First-phase statuses:

- `not_applicable`: prompt has no output schema.
- `passed`: parsed JSON object passed schema validation without repair.
- `repaired`: JSON object required fence/slice/explanation repair and then passed schema validation.
- `failed`: no valid schema-compliant output was produced.
- `fallback`: a module-specific fallback produced a schema-shaped payload, but it is not accepted automatically.

## Decision rule

- Schema-passing output can be `accepted`.
- Schema failure should be `rejected` or `review_required`.
- Regex or heuristic fallback output defaults to `review_required` or `fallback_used`; it must not be silently accepted.
- Business modules remain responsible for deciding whether and how to write their own tables from `PromptExecutionResult.validated_output`.

`PromptExecutor` does not write Memory, VocabularyItem, KnowledgePoint, WritingPhrase, or mastery tables. It only records prompt execution governance.

## Langfuse references

`PromptExecutor` reuses `src.observability.observe()` and attaches prompt metadata to the Langfuse observation. When the Langfuse SDK exposes trace or observation identifiers, BinnAgent stores them in:

- `langfuse_trace_id`
- `langfuse_observation_id`

If Langfuse is disabled or the SDK object does not expose one of those identifiers, the local record is still written with null reference fields. The business flow must not fail because Langfuse is unavailable.

## Migrated prompt paths

Current migrated paths include:

- `tutor.chat` via chat send and stream.
- `conversation.summary`.
- `graph.node`.
- `graph.feedback`.
- `writing_phrase.import`.
- `vocabulary.agent.extract`.
- `exercise.generate`.
- `group_learning.signal_extract`.
- `essay.scoring`.
- `dictionary.lookup`.
- `vocabulary.local_enrichment`.
- `vocabulary.detail_html_extract`.

Valid JSON with a registered output schema is accepted. Markdown-fenced JSON and explain-then-JSON output are repaired and revalidated. Fallback parsers may produce schema-shaped payloads, but they record `schema_validation_status=fallback` and default to `decision=review_required`.

The API response shape remains unchanged; prompt execution records are available only through debug endpoints.

## Debug API

Prompt Debug 后端接口都挂在 `require_debug_access` 保护下：

- `GET /api/debug/prompts/registry`
- `GET /api/debug/prompts/executions`
- `GET /api/debug/prompts/executions/{execution_id}`

`/api/debug/prompts/registry` 返回 PromptMetadata 的业务字段：`prompt_id`、`version`、`owner`、`purpose`、`template_path`、`input_schema`、`output_schema`、`model_policy`、`eval_set` 和 `status`。它不返回渲染后的 prompt。

`/api/debug/prompts/executions` 支持筛选：

- `prompt_id`
- `learner_id`
- `episode_id`
- `source_module`
- `decision`
- `schema_validation_status`
- `repair_used`
- `fallback_used`

Execution 响应只返回业务索引和 Langfuse reference：`prompt_hash`、`input_hash`、`output_schema`、`model_policy`、`schema_validation_status`、`decision`、`confidence`、`langfuse_trace_id` 等。它不返回 raw prompt 或 raw output。

## Prompt Evaluation

`scripts/evaluate_prompts.py` 读取 `PromptMetadata.eval_set` 指向的 JSONL fixture。每条 case 提供 `input` 和离线 `raw_output`，脚本通过 `PromptExecutor.execute_with_raw_output()` 复用真实 schema validation / JSON repair / fallback / decision 逻辑，不调用真实模型。

用法：

```bash
python scripts/evaluate_prompts.py --prompt-id writing_phrase.import --json
python scripts/evaluate_prompts.py --prompt-id writing_phrase.import --version v1 --json
python scripts/evaluate_prompts.py --all --json
python scripts/evaluate_prompts.py --all --min-schema-pass-rate 0.8
```

输出指标：

- `schema_pass_rate`
- `repair_rate`
- `fallback_rate`
- `accepted_rate`
- `review_required_rate`
- `confidence_avg`

当 `schema_pass_rate` 低于 `--min-schema-pass-rate` 时脚本返回非 0。当前 structured eval sets include:

- `evals/prompts/dictionary_lookup_v1.jsonl`
- `evals/prompts/essay_scoring_v1.jsonl`
- `evals/prompts/exercise_generate_v1.jsonl`
- `evals/prompts/graph_feedback_v1.jsonl`
- `evals/prompts/vocabulary_agent_extract_v1.jsonl`
- `evals/prompts/grammar_micro_lesson_v1.jsonl`
- `evals/prompts/group_learning_signal_extract_v1.jsonl`
- `evals/prompts/vocabulary_detail_html_extract_v1.jsonl`
- `evals/prompts/vocabulary_local_enrichment_v1.jsonl`
- `evals/prompts/writing_phrase_import_v1.jsonl`

这些 eval set 覆盖 schema valid、schema invalid、JSON repair、fallback 和非 accepted decision。

## Remaining Direct Prompt Paths

None. `ModelRouter.chat()` and `ModelRouter.stream_chat()` should only appear in `src/prompts/executor.py`.

`model_router.embed()` remains outside the prompt governance boundary because it is an embedding operation rather than a prompt output decision.
