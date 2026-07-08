# Prompt Execution Audit

Status: PromptExecutor migration closure for issue #29.

## PromptRegistry inventory

| prompt_id | version | output_schema | model_policy | Current usage |
| --- | --- | --- | --- | --- |
| `tutor.chat` | `v1` | None | `default_model=ollama_chat`, `temperature=0.7` | Migrated through `PromptExecutor.execute_messages()` / `stream_messages()` from chat send and stream paths. |
| `conversation.summary` | `v1` | None | `default_model=ollama_utility`, `temperature=0.2`, `max_tokens=512` | Migrated through `PromptExecutor.execute()` from chat thread summary updates. |
| `graph.node` | `v1` | None | `default_model=ollama_chat`, `temperature=0.7`, `max_tokens=1024` | Migrated through `PromptExecutor.execute_messages()` from `src/graph/llm.py`. |
| `graph.feedback` | `v1` | `GraphFeedbackOutput` | `default_model=ollama_utility`, `temperature=0.7`, `max_tokens=500` | Migrated through `PromptExecutor.execute()` from `src/graph/nodes/generate_feedback.py`; non-accepted output falls back to deterministic feedback. |
| `vocabulary.agent.extract` | `v1` | `VocabularyExtractOutput` | `default_model=ollama_utility`, `temperature=0.1`, `max_tokens=1200` | Migrated through `PromptExecutor.execute()` from `src/agents/vocabulary_agent.py`; only `decision=accepted` output can create learner vocabulary cards. |
| `grammar.micro_lesson.structured` | `v1` | `GrammarMicroLessonOutput` | `default_model=external`, `temperature=0.2`, `max_tokens=1800` | Registered and available through debug prompt rendering; no runtime caller found in current code. |
| `writing_phrase.import` | `v1` | `WritingPhraseImportOutput` | `default_model=external`, `temperature=0.2`, `max_tokens=1800` | Migrated in first phase through `PromptExecutor.execute_with_raw_output()` from `/api/learners/{learner_id}/writing-phrases/import`. |
| `exercise.generate` | `v1` | `GeneratedExerciseOutput` | `default_model=ollama_utility`, `temperature=0.2`, `max_tokens=1800` | Migrated through `PromptExecutor.execute()` from `/api/learners/{learner_id}/exercises/generate`; only accepted validated output is returned to the learner-facing exercise chain. |
| `essay.scoring` | `v1` | `EssayScoringOutput` | `default_model=ollama_utility`, `temperature=0.3`, `max_tokens=1024` | Migrated through `PromptExecutor.execute()` from essay scoring; non-accepted output falls back to heuristic scoring. |
| `dictionary.lookup` | `v1` | `DictionaryLookupOutput` | `default_model=ollama_utility`, `temperature=0.3`, `max_tokens=512` | Migrated through `PromptExecutor.execute()` from dictionary lookup; non-accepted output returns the existing sparse fallback response. |
| `vocabulary.local_enrichment` | `v1` | `LocalVocabularyOutput` | `default_model=ollama_utility`, `temperature=0.1`, `max_tokens=900` | Migrated through `PromptExecutor.execute()` from local vocabulary enrichment. |
| `vocabulary.detail_html_extract` | `v1` | `VocabularyDetailHtmlOutput` | `default_model=ollama_utility`, `temperature=0.0`, `max_tokens=1000` | Migrated through `PromptExecutor.execute()` from vocabulary detail HTML extraction; API calls pass DB so records are persisted. |
| `group_learning.signal_extract` | `v1` | `GroupLearningSignalExtractOutput` | `default_model=ollama_utility`, `temperature=0.1`, `max_tokens=1600` | Migrated through `PromptExecutor.execute()` from group learning LLM analysis; accepted signals remain candidates until user review/acceptance. |

## Direct model/router callers

| Module | Call path | PromptRegistry? | Structured validation state |
| --- | --- | --- | --- |
| `src/prompts/executor.py` | Central `model_router.chat()` / `stream_chat()` gateway | Yes | All prompt-like runtime calls route here. Structured outputs use schema validation, repair, fallback and decision. Text-only calls record `not_applicable` schema status when DB context is supplied. |
| `src/knowledge/rag.py` | `model_router.embed()` | Not prompt-based | Embedding path observed through Langfuse; not part of structured prompt output migration. |

## Structured outputs without unified schema validation

No remaining prompt-like structured output path is allowed to call `ModelRouter.chat()` directly. `rg "model_router\\.chat\\(|router\\.chat\\(|model_router\\.stream_chat\\(" src` should only report `src/prompts/executor.py` for prompt calls. Embeddings are explicitly outside this migration.

## Migrated issue #29 paths

- `vocabulary.agent.extract`: `VocabularyAgentService.capture_chat_turn()` now calls `PromptExecutor.execute()` with learner/source context. `PromptExecutionRecord` captures prompt hashes, schema status, repair/fallback flags, confidence and decision. The service raises before business normalization unless `decision == accepted` and `validated_output` is present.
- `exercise.generate`: `/api/learners/{learner_id}/exercises/generate` now calls `PromptExecutor.execute()` with `GeneratedExerciseOutput`, `exercise.generate.v1.md`, and `PromptMetadata.model_policy`. Rejected or review-required output returns a 502 and is not exposed as generated exercise items.
- Chat send/stream, conversation summary and graph helper text prompts now use `execute_messages()` or `stream_messages()`, producing prompt records when a DB context is available.
- `graph.feedback`, `essay.scoring`, `dictionary.lookup`, `vocabulary.local_enrichment` and `vocabulary.detail_html_extract` now have registered metadata, schemas, templates and eval sets.

## JSON repair / fallback today

- `src/providers/router.py`: when `ChatRequest.response_schema` is set and Ollama did not parse structured output, retries once with a JSON repair prompt.
- `src/prompts/repair.py`: shared first-phase helper for fence extraction, JSON object slicing, model-explanation stripping, and JSON object parsing.
- `src/extraction/writing_phrase.py`: now uses shared repair and schema validation; regex fallback remains local to writing phrase import.
- `src/tools/essay_scoring.py`: catches non-accepted/model errors and falls back to heuristic score.
- `src/tools/dictionary.py`: catches non-accepted/model errors and falls back to a sparse dictionary response.
- `src/graph/nodes/generate_feedback.py`: catches non-accepted/model errors and falls back to deterministic feedback from grading state.

## Langfuse entry points

- `src/observability.py::observe()` wraps low-level Ollama chat/stream/embed calls and now `PromptExecutor` business observations.
- `src/observability.py::observe_langgraph_run()` sets Langfuse LangChain callback metadata for session graph execution.
- `src/providers/ollama.py` records raw model input/output, usage details, and provider/model metadata in Langfuse when enabled.
- `src/prompts/executor.py` adds prompt business metadata (`prompt_id`, version, hashes, schemas, source module, learner/episode/task references) and stores only available Langfuse trace/observation identifiers in `PromptExecutionRecord`.

## PromptExecutor migration rule

New prompt-like model calls must not call `ModelRouter.chat()` or `ModelRouter.stream_chat()` outside `src/prompts/executor.py`.

- Text-only prompts: register `PromptMetadata`, add a versioned template, and call `PromptExecutor.execute()` / `execute_messages()` / `stream_messages()`.
- Structured prompts: additionally bind `output_schema`, add an eval set, and gate learner-facing writes on `decision == accepted`.
- Fallback output defaults to `review_required` unless an existing business flow explicitly keeps it out of automatic learner-facing writes.
