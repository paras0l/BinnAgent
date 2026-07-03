# Learner Scope Audit

Audit date: 2026-07-03

Scope: phase 1 of issue #25. This audit covers learner-scoped isolation only. It does not introduce SaaS tenancy or a repository-wide `tenant_id` migration.

## Phase 1 Boundary

The backend now has a dev/mock-compatible current-user shape and scoped resource helpers:

- `get_current_user()` reads `X-User-Id` or `X-Dev-User-Id` and falls back to a local-dev user for legacy unowned MVP data.
- `require_learner_access()` and `get_current_learner()` require the path learner to be accessible by the current user.
- `Learner.tenant_id` is used only as a temporary owner marker while there is no real `User` model. Unowned legacy learners remain accessible only through the local-dev fallback.
- Debug access is still a separate gate. A valid debug token does not grant access to learners owned by another user.

## Learner-Scoped Resources

Primary learner resources:

- `Learner`, `LearnerProfile`
- `AgentEpisode`, `LearningEvent`, `LearningGraphCheckpoint`; `ToolCallRecord` is episode-scoped and must be reached through a scoped episode
- `AgentThread`, `ConversationMessage`
- `LearningMemoryEvent`, `LearningEpisode`, `LearnerModelMemory`, `TeachingStrategyMemory`, `MemoryOperation`, `MemoryContextLog`, `LearnerMemorySettings`
- `ErrorPattern`, `WritingPhraseMastery`
- `ExerciseAttempt`, `KnowledgeLearningEvent`, `LearnerKnowledgeState`
- `LearningSession`, `LearningTask`, `LearningProgressItem`
- `VocabularyItem`, `VocabularyItemSource`, `VocabularyUserOverride`, `VocabularyMasteryVector`, `VocabularyMistake`, `VocabularyPracticeSession`, `VocabularyAttempt`, `ReviewSchedule`
- `ExploreFeaturePreference`
- `ReadingMaterialHistory`
- learner-owned private knowledge sources through `KnowledgeSource.owner_learner_id`

## Endpoint Safety Status

| Area | Current status | Notes |
| --- | --- | --- |
| `/api/runtime/episodes` | Hardened in phase 1 | Requires `learner_id`, validates current user access, and lists only that learner's episodes. |
| `/api/runtime/episodes/{episode_id}` | Hardened in phase 1 | Fetches the episode, validates `episode.learner_id`, then returns trace. |
| `/api/runtime/episodes/{episode_id}/verification` | Hardened in phase 1 | Same episode ownership pre-check before verification. |
| `/api/learners/{learner_id}/daily-lessons/start` | Hardened in phase 1 | Path learner is current-user scoped. |
| `/api/learners/{learner_id}/daily-lessons/{episode_id}` | Hardened in phase 1 | Path learner is current-user scoped; episode lookup uses `get_episode_for_learner()`. |
| `/api/learners/{learner_id}/daily-lessons/{episode_id}/answer` | Hardened in phase 1 | Path learner is current-user scoped; answer submission uses scoped episode and active checkpoint lookup by learner + episode. |
| `/api/learners/{learner_id}/memory/summary` | Hardened in phase 1 | Current-user scoped learner before reading summary data. |
| `/api/learners/{learner_id}/memory/center`, `curate`, `settings`, `reset-plan`, `export` | Hardened in phase 1 | Debug token is still required where it existed, then learner access is checked. |
| `/api/learners/{learner_id}/memory/items/{target_type}/{target_id}` | Hardened in phase 1 | Current-user scoped learner; memory event target uses `get_memory_item_for_learner()`. Other target types still query by learner + id locally. |
| `/api/learners/{learner_id}/explore/preferences` | Hardened in phase 1 | Current-user scoped learner before list/update. |
| `/api/explore/capabilities/{capability_id}/start` | Hardened in phase 1 | Body `learner_id` is current-user scoped before episode creation. |
| `/api/learners/{learner_id}/explore/recommendations` | Hardened in phase 1 | Current-user scoped learner; optional `episode_id` is scoped to learner. |
| `/api/learners/{learner_id}/explore/capabilities/{capability_id}/events` | Hardened in phase 1 | Current-user scoped learner; optional `episode_id` is checked before appending runtime events. |
| `/api/learners/{learner_id}/exercise-attempts` | Hardened in phase 1 | Current-user scoped learner; service queries already filter by learner. |
| `/api/debug/learners` | Partially hardened | Results are limited to current user's owned learners, current user's own learner id, and unowned legacy learners in local-dev fallback. |
| `/api/debug/rag/search` | Partially hardened | Optional `learner_id` is validated, but `source_id` / `node_id` still need private-source scope checks. |

## ID-Only Lookup Risks

Known code paths that still use direct id lookup internally and must remain behind scoped callers:

- `EpisodeRuntime.get_episode_trace()` and `EpisodeRuntime._get_episode()` still fetch by `episode_id`; public runtime endpoints now pre-check ownership.
- `LearningOrchestrator._get_episode()` still exists for internal flows such as `resume_task()` / `complete_task()`; any future public endpoint must prefer `get_episode_for_learner()`.
- `GraphCheckpointStore.mark_resumed()`, `mark_completed()`, and `mark_failed()` fetch by `checkpoint_id`; current daily lesson answer flow obtains the checkpoint through `get_active_checkpoint(episode_id, learner_id)` first.
- `GraphCheckpointStore.list_checkpoints_for_episode()` lists by `episode_id`; current public status flow first scopes the episode.
- Knowledge, vocabulary-learning, reading, writing phrase, grammar cache, dashboard, conversation, chat, session, learner profile, and learning progress APIs often check only that `learner_id` exists. Many downstream queries filter by learner, but the API boundary still needs `get_current_learner()`.
- `KnowledgeSource`, `CurriculumNode`, `KnowledgePoint`, and `ExerciseQuestion` are often fetched by id. Private textbook resources must be checked through `KnowledgeSource.owner_learner_id` before exposing derived nodes, chunks, questions, or attempts.
- `VocabularyPracticeSession`, `VocabularyItem`, and `VocabularyAttempt` paths mostly query by learner, but any future endpoint accepting `vocabulary_item_id`, `attempt_id`, or `review_schedule_id` directly should use a scoped helper.

## Recommended Scoped Helper Follow-Up

Already added:

- `get_learner_for_user(db, user_id, learner_id)`
- `get_episode_for_learner(db, learner_id, episode_id)`
- `get_checkpoint_for_learner(db, learner_id, checkpoint_id)`
- `get_attempt_for_learner(db, learner_id, attempt_id)`
- `get_memory_item_for_learner(db, learner_id, memory_id)`

Recommended next helpers:

- `get_thread_for_learner(db, learner_id, thread_id)`
- `get_vocabulary_item_for_learner(db, learner_id, vocabulary_item_id)`
- `get_vocabulary_session_for_learner(db, learner_id, session_id)`
- `get_review_schedule_for_learner(db, learner_id, review_schedule_id)`
- `get_knowledge_source_for_learner(db, learner_id, source_id)`
- `get_curriculum_node_for_learner(db, learner_id, node_id)` through source ownership
- `get_learning_session_for_learner(db, learner_id, session_id)`
- `get_writing_phrase_for_learner(db, learner_id, phrase_id)`

## Dev Console / Debug API

Debug access can still execute operational actions, but it no longer bypasses learner scope for phase-1 high-risk resources:

- Runtime trace and verification by `episode_id` require episode owner access.
- Runtime episode list requires a scoped `learner_id`.
- Debug memory endpoints require both debug token and learner owner access.
- Debug learner list is scoped to the current user boundary.

Remaining debug risks:

- RAG debug search can still use `source_id` / `node_id` without proving the source belongs to the current learner.
- Simulation report endpoints read local report files and are not learner scoped; they should avoid embedding private learner payloads or add report-level filtering before broader use.
