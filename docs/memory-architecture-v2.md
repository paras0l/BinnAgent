# Memory Architecture v2

> 更新时间：2026-06-26

## 目标

Memory v2 把 BinnAgent 的记忆从局部统计升级为学习中枢：

```text
学习行为 -> 统一事件 -> 状态聚合 -> 弱点归因 -> 可解释推荐 -> 用户治理
```

## 已落地模块

| 模块 | 文件 | 说明 |
|---|---|---|
| 统一事件表 | `src/models/memory.py` | `LearningMemoryEvent` 记录跨模块学习行为 |
| 操作审计 | `src/models/memory.py` | `MemoryOperation` 记录用户编辑、删除、禁用、纠正 |
| 写作句式掌握 | `src/models/memory.py` | `WritingPhraseMastery` 分离资源和掌握状态 |
| 上下文日志 | `src/models/memory.py` | `MemoryContextLog` 记录 retriever 加载/排除项 |
| 记忆设置 | `src/models/memory.py` | `LearnerMemorySettings` 管理情绪节奏、偏好推断和低置信上下文开关 |
| 写入器 | `src/memory/writer.py` | 热路径结构化写入 event/operation |
| 检索器 | `src/memory/retriever.py` | 按任务读取最小必要记忆 |
| 整理器 | `src/memory/curator.py` | 聚合 active weaknesses、更新 error pattern 和 phrase mastery |
| 解释器 | `src/memory/explainer.py` | 生成 recommendation reason |
| 治理 API | `src/api/memory.py` | memory center、curate、control、export |

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

## 后续增强

- 增强 memory debug dashboard 的可视化图表。
- 继续扩展作文批改的复发/改善判定规则。
- 增加更多 memory regression eval，包括删除后不可再用、弱点改善后降权、掌握词不再反复低级题。
