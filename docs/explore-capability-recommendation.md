# ExploreCapability Recommendation

## Why Not Skill

Explore Tab entries are learner-facing learning capabilities, not Agent Skills.

- Tool: backend or agent callable primitives such as `memory.write`, `exercise.grade`, `rag.retrieve`, `mastery.update`, or `verification.verify_episode`.
- Agent Skill: an internal agent strategy or workflow package used to complete complex tasks.
- ExploreCapability: a user-visible learning entry such as grammar micro lessons, vocabulary detail, word roots and affixes, writing phrasebook, essay review, reading practice, pronunciation practice, or daily lesson.

The Explore Tab uses `ExploreCapability` naming so learner-facing entries do not collide with internal Agent Skill naming. English-learning dimensions such as grammar, vocabulary, writing, reading, speaking, and listening are stored as `learning_skill`.

## Registry

`src/explore/capabilities.py` is the backend authority for Explore entries. Each `ExploreCapabilitySpec` includes:

- Identity: `capability_id`, `feature_id`, `title`, `description`, `category`, `status`.
- User entry behavior: `action`, `tool_target`, `route_hint`.
- Learning semantics: `learning_skill`, `supported_target_types`, `supported_error_types`, `recommended_when`, `not_recommended_when`, `expected_learning_outcome`.
- Runtime semantics: `task_type`, `target_type`, `default_difficulty`, `estimated_minutes`, `allowed_tools`, `produces`.
- Recommendation semantics: `priority_weight`, `requires_user_input`, `metadata`.

Only `status=ready` capabilities participate in recommendation. TODO capabilities can remain in the registry for visibility, but the start API rejects them and the recommender filters them out.

## APIs

- `GET /api/explore/capabilities`: list capabilities, with optional `status`, `category`, and `ready_only=true`.
- `POST /api/explore/capabilities/{capability_id}/start`: create a standard `TaskSpec` and `AgentEpisode` with `source="explore"`.
- `POST /api/learners/{learner_id}/explore/recommendations`: return 1-3 learner-facing capability recommendations.
- `POST /api/learners/{learner_id}/explore/capabilities/{capability_id}/events`: record `shown`, `clicked`, `dismissed`, or `completed` recommendation behavior.

The old `/api/explore/skills` endpoints are intentionally removed.

## Recommendation Flow

Daily Lesson calls `ExploreCapabilityRecommender` after grading, mastery update, memory write, and verification. The answer response includes `next_capability_recommendations`.

The recommender first builds candidates from registry-ready capabilities. It scores target match, error type match, mastery need, memory relevance, user preference, and novelty. If there is not enough context, it returns at most one generic ready capability such as `daily-lesson` or `vocab-review`.

LLM rerank is disabled by default. When enabled, the LLM can only reorder the rule-generated Top 5 candidates and explain why now; it cannot invent `capability_id`, route, action, or `tool_target`. Invalid LLM IDs are discarded, and any failure falls back to rule ordering.

## Memory And Trace

Recommendation events are observable in two places:

- `LearningMemoryEvent`: click/dismiss/show/complete events use `source_type="explore_capability"`, `source_id=capability_id`, `skill=capability.learning_skill`, and payload fields such as `recommendation_id`, `episode_id`, `feature_id`, `title`, `reason`, and `evidence_refs`.
- `AgentEpisode` trace: Daily Lesson appends `explore_capability_recommended`; explicit user events with an `episode_id` are appended under the Explore source module.

Dev Console Episode Trace can inspect `explore_capability_recommended`, `explore_capability_clicked`, `explore_capability_dismissed`, and `explore_capability_completed` events.

## Current Boundaries

- Only ready capabilities are recommended.
- Recommendations are suggestions; the user must click before any Explore entry opens.
- Routes, actions, and tool targets come from the registry or fixed frontend mapping, not from LLM output.
- TODO capabilities are visible in Explore but cannot start runtime and are never recommended.
- Recommendation failure never fails the Daily Lesson answer flow.
