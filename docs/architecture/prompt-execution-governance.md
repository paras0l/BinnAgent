# Prompt Execution Governance

Status: issue #29 debug / evaluation closure.

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

Structured LLM output must pass schema validation before it can be accepted by business code that writes Memory, Mastery, KnowledgePoint, Vocabulary, or WritingPhrase data.

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

## Writing phrase import

`writing_phrase.import` is the first migrated prompt path.

- Valid JSON with `WritingPhraseImportOutput` is accepted.
- Markdown-fenced JSON is extracted and validated.
- Explanation text around a JSON object is sliced, marked as repaired, and revalidated.
- Invalid JSON may use the writing-phrase-specific regex fallback.
- Regex fallback produces a `PromptExecutionRecord` with `schema_validation_status=fallback` and `decision=review_required`.

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

当 `schema_pass_rate` 低于 `--min-schema-pass-rate` 时脚本返回非 0。当前已有三个 eval set：

- `evals/prompts/vocabulary_agent_extract_v1.jsonl`
- `evals/prompts/grammar_micro_lesson_v1.jsonl`
- `evals/prompts/writing_phrase_import_v1.jsonl`

这些 eval set 覆盖 schema valid、schema invalid、JSON repair、fallback 和非 accepted decision。

## Remaining Direct Prompt Paths

仍需后续迁移到 `PromptExecutor` 的结构化/准结构化调用：

- `src/agents/vocabulary_agent.py`：仍直接使用 `ModelRouter.chat()` 和本地 `VOCABULARY_CARD_SCHEMA`。
- `src/api/exercises.py`：练习生成仍直接绑定 `GENERATED_EXERCISE_SCHEMA`。
- `src/tools/vocabulary_detail_html.py`：词汇详情 HTML 生成仍直接解析模型输出。
- `src/tools/vocabulary_enrichment.py`：词汇 enrichment 仍直接解析模型输出。
- chat、graph feedback、essay scoring、dictionary lookup 等路径仍需按结构化程度分批接入。
