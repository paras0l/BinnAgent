# Prompt Execution Governance

Status: first-phase implementation for issue #29.

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
