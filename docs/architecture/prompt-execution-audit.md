# Prompt Execution Audit

Status: first-phase audit for issue #29.

## PromptRegistry inventory

| prompt_id | version | output_schema | model_policy | Current usage |
| --- | --- | --- | --- | --- |
| `tutor.chat` | `v1` | None | `default_model=ollama_chat`, `temperature=0.7` | Rendered once in `src/api/chat.py` as the base tutor system prompt. Chat still calls `ModelRouter` directly. |
| `vocabulary.agent.extract` | `v1` | `VocabularyExtractOutput` | `default_model=ollama_utility`, `temperature=0.1`, `max_tokens=1200` | Rendered in `src/agents/vocabulary_agent.py`; direct router call with `response_schema`, no `PromptExecutor` record yet. |
| `grammar.micro_lesson.structured` | `v1` | `GrammarMicroLessonOutput` | `default_model=external`, `temperature=0.2`, `max_tokens=1800` | Registered and available through debug prompt rendering; no runtime caller found in current code. |
| `writing_phrase.import` | `v1` | `WritingPhraseImportOutput` | `default_model=external`, `temperature=0.2`, `max_tokens=1800` | Migrated in first phase through `PromptExecutor.execute_with_raw_output()` from `/api/learners/{learner_id}/writing-phrases/import`. |

## Direct model/router callers

| Module | Call path | PromptRegistry? | Structured validation state |
| --- | --- | --- | --- |
| `src/api/chat.py` | `model_router.chat()` and `model_router.stream_chat()` for tutor replies and summary generation | `tutor.chat` only for base prompt | Main chat is text-only. Conversation summary is text-only. No local prompt execution record. |
| `src/agents/vocabulary_agent.py` | `self.model_router.chat()` with `VOCABULARY_CARD_SCHEMA` | Yes | Uses Ollama JSON format and `ModelRouter` repair retry, then `json.loads` fallback. Not yet unified through `PromptExecutor` or local schema validation record. |
| `src/api/exercises.py` | `model_router.chat()` with `GENERATED_EXERCISE_SCHEMA` | No | Uses router structured response; business normalization checks required fields, but no unified schema validation record. |
| `src/graph/llm.py` | `router.chat()` for graph nodes | No | Text-only helper. `generate_feedback` asks for JSON and falls back to text summary on JSON parse failure. |
| `src/tools/essay_scoring.py` | `router.chat()` | No | Prompts for JSON, parses with `json.loads`, falls back to heuristic scoring on errors. No schema registry entry. |
| `src/tools/dictionary.py` | `router.chat()` | No | Prompts for JSON, parses with `json.loads`, falls back to empty/local response on errors. No schema registry entry. |
| `src/tools/vocabulary_enrichment.py` | `router.chat()` with `LOCAL_VOCABULARY_SCHEMA` | No | Uses response schema and `json.loads` fallback, then parser normalization. No local prompt execution record. |
| `src/tools/vocabulary_detail_html.py` | `router.chat()` with `DETAIL_HTML_SCHEMA` | No | Uses response schema and `json.loads` fallback, then parser normalization. No local prompt execution record. |
| `src/knowledge/rag.py` | `model_router.embed()` | Not prompt-based | Embedding path observed through Langfuse; not part of structured prompt output migration. |

## Structured outputs without unified schema validation

- `vocabulary.agent.extract`: schema exists, but validation is currently delegated to Ollama JSON format and ad hoc parse/normalization.
- `exercise_generate`: schema exists locally in API module, but not registered in PromptRegistry and not recorded by `PromptExecutionRecord`.
- `graph.generate_feedback`: JSON is requested in prompt text but has no schema and falls back to text summary.
- `essay_scoring`: JSON is requested in prompt text but has no registered schema.
- `dictionary_lookup`: JSON is requested in prompt text but has no registered schema.
- `vocabulary_local_enrichment`: schema exists in tool module, but not PromptRegistry-backed.
- `vocabulary_detail_html_extract`: schema exists in tool module, but not PromptRegistry-backed.

## JSON repair / fallback today

- `src/providers/router.py`: when `ChatRequest.response_schema` is set and Ollama did not parse structured output, retries once with a JSON repair prompt.
- `src/prompts/repair.py`: shared first-phase helper for fence extraction, JSON object slicing, model-explanation stripping, and JSON object parsing.
- `src/extraction/writing_phrase.py`: now uses shared repair and schema validation; regex fallback remains local to writing phrase import.
- `src/tools/essay_scoring.py`: catches parse/model errors and falls back to heuristic score.
- `src/tools/dictionary.py`: catches parse/model errors and falls back to a sparse dictionary response.
- `src/graph/nodes/generate_feedback.py`: catches JSON parse failure and uses the raw text as a summary.

## Langfuse entry points

- `src/observability.py::observe()` wraps low-level Ollama chat/stream/embed calls and now `PromptExecutor` business observations.
- `src/observability.py::observe_langgraph_run()` sets Langfuse LangChain callback metadata for session graph execution.
- `src/providers/ollama.py` records raw model input/output, usage details, and provider/model metadata in Langfuse when enabled.
- `src/prompts/executor.py` adds prompt business metadata (`prompt_id`, version, hashes, schemas, source module, learner/episode/task references) and stores only available Langfuse trace/observation identifiers in `PromptExecutionRecord`.

## PromptExecutor migration priority

1. `writing_phrase.import`: completed in first phase because it already had JSON-first repair and regex fallback.
2. `vocabulary.agent.extract`: high priority because it writes learner-owned vocabulary cards and already has PromptRegistry metadata and schema.
3. `exercise_generate`: high priority because it creates learner-facing generated exercises from structured output.
4. `vocabulary_local_enrichment` and `vocabulary_detail_html_extract`: medium priority; both have schemas and write normalized vocabulary detail data.
5. `graph.generate_feedback`: medium priority; add schema before allowing output to affect memory/mastery.
6. `essay_scoring` and `dictionary_lookup`: medium priority; define schemas and keep existing heuristic/local fallback as review-required/fallback decisions.
7. Chat tutor replies and summaries: lower priority for schema-first migration unless their outputs begin writing structured memory directly.
