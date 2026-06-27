# Memory Architecture v2

> 更新时间：2026-06-27

## 目标

Memory v2 把 BinnAgent 的记忆从局部统计升级为学习中枢。正式口径采用 **4 层学习记忆架构 + Retain / Recall / Reflect / Explain / Control 操作模型**。设计借鉴 HindSight 的动作思想，但不依赖 HindSight 服务或外部数据库。

```text
Retain 学习证据 -> Reflect 学习过程 -> Recall 教学状态 -> Explain 推荐原因 -> Control 用户治理
```

核心判断：

```text
Chat history 是短期上下文；Learning memory 是长期教学状态。
Memory 的目标不是回忆过去，而是指导下一步教学。
```

## 已落地模块

| 模块 | 文件 | 说明 |
|---|---|---|
| 统一事件表 | `src/models/memory.py` | `LearningMemoryEvent` 记录跨模块学习行为 |
| 学习经历 | `src/models/memory.py` | `LearningEpisode` 把一段 session 或一组同类事件整理为可追溯 episode |
| 学习者模型 | `src/models/memory.py` | `LearnerModelMemory` 保存 active / improving / resolved / dismissed 的长期学习判断 |
| 教学策略记忆 | `src/models/memory.py` | `TeachingStrategyMemory` 记录哪些反馈方式对该学习者有效 |
| 操作审计 | `src/models/memory.py` | `MemoryOperation` 记录用户编辑、删除、禁用、纠正 |
| 写作句式掌握 | `src/models/memory.py` | `WritingPhraseMastery` 分离资源和掌握状态 |
| 上下文日志 | `src/models/memory.py` | `MemoryContextLog` 记录 retriever 加载/排除项 |
| 记忆设置 | `src/models/memory.py` | `LearnerMemorySettings` 管理情绪节奏、偏好推断和低置信上下文开关 |
| 层级常量 | `src/memory/layers.py` | 统一 `L1_context`、`L2_evidence`、`L3_learner_model`、`L4_governance_reflection` |
| Retain 写入器 | `src/memory/writer.py` | 热路径结构化写入 event/operation，并自动补充 `evidence_ref` 和 `memory_layer=L2_evidence` |
| Recall 检索器 | `src/memory/retriever.py` | 按 chat、daily plan、vocabulary、knowledge、essay、phrasebook 等场景读取最小必要记忆；每个 item 标注来源 layer |
| Reflect 整理器 | `src/memory/curator.py` | 由 L4 执行，聚合 active weaknesses，生成 episode、learner model、teaching strategy，并更新 error pattern 和 phrase mastery |
| 解释器 | `src/memory/explainer.py` | 生成 recommendation reason |
| 治理 API | `src/api/memory.py` | memory center、curate、control、export |

## 4 层学习记忆架构

| 层级 | 含义 | 当前实现 |
|---|---|---|
| L1 Context Memory | 当前上下文层，服务一次对话、一次练习、一次模型调用 | thread summary、recent messages、current task、skill_focus、retrieved memory context |
| L2 Evidence Memory | 证据与经历层，保存可追溯学习证据 | `learning_memory_events`、`learning_episodes`、attempts、essay feedback events、`memory_operations`、`evidence_ref` |
| L3 Learner Model Memory | 学习者模型层，保存系统对学习者的稳定理解 | mastery vectors、knowledge states、`WritingPhraseMastery`、`ErrorPattern`、`LearnerProfile`、`LearnerModelMemory`、`TeachingStrategyMemory` |
| L4 Governance & Reflection Memory | 治理与反思层，负责整理、反思、解释和用户控制 | `MemoryCurator`、`MemoryPolicy`、`MemoryExplainer`、`MemoryOperation`、audit logs、user controls、reflection jobs |

此前 issue 中提到的 Learning Resources / Learning Episodes / Learner Models 不再作为正式层级：

- Learning Resources 是业务资源数据，例如教材、词汇卡、写作好句、语法微课、练习题；它们不作为 Memory 层，只被 Memory 引用。
- Learning Episodes 归入 L2 Evidence Memory。
- Learner Models 归入 L3 Learner Model Memory。

资源和掌握状态必须分离：例如一个写作句式是业务资源，是否会用属于 L3 Learner Model Memory，什么时候用错属于 L2 Evidence Memory。

## Retain / Recall / Reflect

Retain / Recall / Reflect / Explain / Control 是操作模型，不是层级模型。

### Retain

`MemoryWriter.record_event()` 是统一 Retain 入口。关键事件包括：

- `vocabulary_attempted`
- `vocabulary_mistake_recorded`
- `knowledge_exercise_answered`
- `writing_phrase_attempted`
- `essay_feedback_received`
- `grammar_topic_opened`
- `chat_tutoring_completed`
- `user_corrected_memory`
- `user_deleted_memory`
- `user_marked_mastered`

每条事件必须有 `learner_id`、`skill`、`source_type/source_id` 和可追溯 `evidence_ref`。低置信推断先作为 evidence，不直接写成长期事实。

对应层级：写入 L2 Evidence Memory，必要时生成或更新 L2 episode。

### Recall

`MemoryRetriever` 提供场景化入口：

- `for_chat()`
- `for_daily_plan()`
- `for_vocabulary_practice()`
- `for_knowledge_exercise()`
- `for_essay_review()`
- `for_writing_phrasebook()`
- `for_memory_explanation()`

Recall 只返回当前任务相关的少量记忆，优先读取 active / improving 的 learner model、teaching strategy、episode，再补充 error pattern、词汇/知识/句式掌握状态和最近事件。

对应层级：从 L2 Evidence Memory 和 L3 Learner Model Memory 召回当前任务相关信息，注入 L1 Context Memory。

### Reflect

`MemoryCurator.reflect()` 在 session 结束、练习完成、用户手动整理时运行：

- 把 events 汇总为 `LearningEpisode`。
- 从 event/episode 生成 `LearnerModelMemory`。
- 根据 hint、retry、feedback strategy 等证据生成 `TeachingStrategyMemory`。
- 合并重复错因，更新 active / improving / resolved / dismissed 状态。
- 更新 `LearnerProfile.weak_skills`。

对应层级：由 L4 Governance & Reflection Memory 执行，基于 L2 证据更新 L3 Learner Model Memory。

## 接入点

- Chat：模型调用前读取 memory context，并把 loaded/excluded items 写入消息 metadata 和 `memory_context_logs`。
- Vocabulary：attempt 和 mistake 镜像写入 `learning_memory_events`。
- Knowledge：知识点练习和题目 attempt 镜像写入统一事件。
- Writing Phrasebook：句式保存、更新、删除、attempt 写入事件；attempt 后触发 curator。
- Essay Review：批改前读取 writing memory，返回历史弱点和改善提示，并写入 `essay_submitted` / `essay_feedback_received` / `chat_error_observed` 事件。
- LangGraph：`update_memory` 写事件，`schedule_review` 通过 retriever 生成 review items。
- Frontend：`MemoryCenterPage` 支持查看、编辑、删除、禁用、标记已改善、导出、手动整理。

## 用户治理规则

- 用户删除/禁用会写入 `memory_operations`，retriever 后续排除对应目标。
- 用户删除或否认 `LearnerModelMemory` 后，后续推荐不再使用该模型。
- 用户编辑/纠正会把相关 memory confidence 提升为用户确认优先。
- “我已改善”会降低 error pattern 严重度，或把句式 mastery 标为 mastered。
- 低置信 memory 只作为候选上下文，不作为事实性长期画像。
- 情绪/节奏记忆默认关闭；用户开启后才允许长期保存这类推断。
- 学习计划重置会把未完成 task/session 标记为 `reset`，并写入 `reset_plan` operation。

## 可观测指标

Memory Center 当前返回：

- `memory_write_count`
- `memory_retrieval_count`
- `memory_hit_rate`
- `memory_used_in_prompt_count`
- `memory_operation_count`
- `memory_user_deleted_count`
- `memory_stale_count`
- `learning_episode_count`
- `learner_model_memory_count`
- `teaching_strategy_memory_count`

Recall 日志中的 `loaded_items` 使用 JSONB 对象保存 `id`、`type`、`layer`、`skill`，用于验证 L2/L3 记忆如何注入 L1 Context Memory。

## 后续增强

- 增强 memory debug dashboard 的可视化图表。
- 继续扩展作文批改的复发/改善判定规则。
- 增加更多 memory regression eval，包括删除后不可再用、弱点改善后降权、掌握词不再反复低级题。
