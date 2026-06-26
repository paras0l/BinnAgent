# 03. Memory System 技术方案

## 1. 模块目标

Memory System 是英语学习陪伴系统的核心壁垒。

它不是简单聊天历史，而是学习者的长期成长档案：

- 用户目标。
- 词汇掌握。
- 错题错因。
- 写作口语错误模式。
- 听力错听模式。
- 学习节奏和情绪。
- 复习计划。

## 2. 当前落地状态

截至 2026-06-26，Memory 已从“局部统计 + chat 摘要”升级为统一学习记忆底座的第一版：

- 新增 `learning_memory_events` 统一事件流，镜像 chat、词汇 attempt、知识练习、写作句式保存/练习等关键行为。
- 新增 `memory_operations`，记录用户编辑、删除、禁用、纠正、标记已改善、导出等治理操作。
- 新增 `MemoryWriter`、`MemoryRetriever`、`MemoryCurator`、`MemoryExplainer`、`MemoryManager`。
- `ErrorPattern` 增强为带 `confidence`、`status`、`subskill`、`first_seen_at`、干预记录和 evidence 的可治理长期记忆。
- 新增 `WritingPhraseMastery`，把写作句式资源和掌握状态分离。
- 新增 `MemoryContextLog`，记录每次 retriever 加载和排除的记忆项。
- 新增 `LearnerMemorySettings`，把情绪/节奏记忆、推断偏好、低置信记忆入上下文做成用户可控开关。
- `/api/learners/{learner_id}/memory/center` 提供“我的学习记忆”页面数据；支持整理、导出、编辑、删除、禁用、我已改善、重置学习计划。
- Chat、daily lesson、vocabulary practice、writing phrasebook、LangGraph review scheduling 已接入 `MemoryRetriever`。

## 3. Memory 分层

| 层级 | 范围 | 内容 | 技术 |
|---|---|---|---|
| L0 Working Context | 单次 LLM 调用 | 当前任务所需最小上下文、Top-K 弱点和 episode | `MemoryRetriever` + prompt context |
| L1 Thread / Session Episode | 一段对话或课程 | 对话摘要、session summary、反馈和下一步 | `AgentThread`、`LearningSession` |
| L2 Raw Learning Event | 跨模块学习行为 | 统一事件流、source/evidence、confidence | `learning_memory_events` |
| L3 Skill State Memory | 技能掌握状态 | 词汇 mastery、知识点 state、句式 mastery | 局部 state 表 + curator |
| L4 Semantic Learner Profile | 稳定画像 | 目标、时间预算、兴趣、弱项 | `LearnerProfile` |
| L5 Pattern & Strategy Memory | 错误模式和教学策略 | error pattern、recommended drill、干预效果 | `ErrorPattern` |
| L6 Resource / Knowledge Vault | 学习资产 | 教材、词卡、句式、题目、RAG chunks | resource tables |
| L7 Curator & Governance | 治理 | 合并、降噪、用户删除/纠正、导出 | `MemoryCurator` + operations |

## 4. Memory 类型

### 3.1 Learner Profile Memory

存储：

- 目标考试。
- 考试日期。
- 目标分。
- 当前水平。
- 每日时间预算。
- 兴趣主题。
- 学习偏好。

用途：

- 个性化计划。
- 材料难度选择。
- 反馈语气控制。

### 3.2 Vocabulary Memory

存储：

- 生词。
- 错词。
- 熟词僻义。
- 搭配。
- 发音问题。
- 复习次数。
- 掌握度。
- 下次复习时间。

示例：

```json
{
  "word": "sustain",
  "level": "CET6",
  "meaning": ["维持", "支撑", "遭受"],
  "collocations": ["sustain growth", "sustain an injury"],
  "status": "weak",
  "mistake_types": ["meaning_confusion", "collocation"],
  "review_count": 3,
  "next_review_at": "2026-06-13T20:30:00+08:00",
  "confidence": 0.58
}
```

### 3.3 Error Pattern Memory

存储可迁移错误，而非孤立错误：

- 写作漏冠词。
- 主谓一致错误。
- 阅读忽略转折。
- 听力听不出弱读。
- 口语总用中文语序。

示例：

```json
{
  "skill": "writing",
  "pattern": "missing_articles",
  "description": "用户经常漏掉 a/an/the。",
  "frequency": 7,
  "severity": "medium",
  "evidence_refs": ["writing_submission_001", "writing_submission_008"],
  "recommended_drill": "article_fill_in_blank"
}
```

### 3.4 Material Memory

存储：

- 学过的文章、音频、题目。
- 材料难度。
- 用户兴趣反馈。
- 生词密度。
- 完成情况。

用途：

- 避免重复推荐。
- 根据兴趣推荐泛读泛听。
- 根据难度调节材料。

### 3.5 Plan Memory

存储：

- 当前阶段。
- 本周目标。
- 每日任务。
- 完成情况。
- 调整原因。

用途：

- 滚动计划。
- 周报。
- 任务恢复。

### 3.6 Emotion & Rhythm Memory

存储：

- 用户常用学习时间。
- 连续完成/中断情况。
- 疲惫、焦虑、拖延信号。
- 用户喜欢或讨厌的反馈方式。

注意：

- 不做医学判断。
- 不贴人格标签。
- 只用于调整学习任务难度和语气。

## 5. 统一事件层

`learning_memory_events` 是所有学习行为的统一索引层。第一版不搬迁旧表，而是把关键行为镜像进事件流：

- `chat_learning_turn`
- `chat_error_observed`
- `vocabulary_attempted`
- `vocabulary_mistake_recorded`
- `knowledge_point_practiced`
- `knowledge_exercise_answered`
- `writing_phrase_saved`
- `writing_phrase_attempted`
- `user_corrected_memory`
- `user_deleted_memory`
- `user_disabled_memory`
- `user_marked_memory_improved`

每条事件至少包含 learner、event_type、skill、source_type/source_id、payload、confidence、visibility、created_by、occurred_at。

## 6. Namespace 设计

```text
("learner", user_id, "profile")
("learner", user_id, "vocabulary")
("learner", user_id, "error_patterns")
("learner", user_id, "materials")
("learner", user_id, "plans")
("learner", user_id, "emotion_rhythm")
("learner", user_id, "exam_performance")
```

如果支持班级或机构：

```text
("tenant", tenant_id, "learner", user_id, "vocabulary")
```

## 7. Memory 写入策略

### 5.1 Hot Path 写入

立即写入：

- 用户目标变化。
- 今日错词。
- 今日错题错因。
- 作文关键错误。
- 今日完成状态。
- 下次复习时间。

### 5.2 Background 写入

异步处理：

- session 总结。
- 错误模式归并。
- 周学习画像更新。
- 材料兴趣建模。
- 复习效果统计。

### 5.3 写入过滤

Memory candidate 必须满足：

- 对未来学习有用。
- 有明确证据。
- 能结构化。
- 不只是闲聊。
- 不包含不应长期存储的隐私。

## 8. Memory Curator

Memory Curator 是后台 Agent 或任务，负责维护记忆质量。

职责：

- 去重：合并同义错词、重复错误模式。
- 降噪：偶发错误不升级为长期弱点。
- 合并：多个孤立错误归并为错误模式。
- 冲突处理：用户已掌握后降低旧弱点权重。
- 遗忘：过期、无用或用户要求删除的记忆清理。

## 9. 复习调度

### 7.1 默认周期

参考艾宾浩斯记忆曲线：

- 5 分钟。
- 30 分钟。
- 12 小时。
- 1 天。
- 2 天。
- 4 天。
- 7 天。
- 15 天。

### 7.2 动态调整

可使用 SM-2 或 FSRS 类算法：

- 答对且快：延长间隔。
- 答对但犹豫：轻微延长。
- 答错：缩短间隔。
- 高频考试词：保留周期抽查。
- 多次错误：换训练形式。

## 10. Memory 读取策略

每次 session 只读取必要 Memory：

- 今日计划。
- 到期复习。
- 最近 3-5 个高频错误。
- 当前技能相关弱点。
- 用户偏好。

避免把所有历史塞进 prompt。

已接入场景：

- Chat：读取 thread summary、相关弱点、最近事件，并记录 memory_context。
- 今日学习路径：读取知识点状态和活跃弱点生成推荐理由。
- 词汇练习：读取 vocabulary mastery/mistake，解释为什么安排当前任务。
- 写作好句：读取 writing error pattern 和 phrase mastery，生成推荐理由。
- LangGraph schedule_review：从 retriever 生成 review_items。

## 11. 隐私和可控性

用户应能：

- 查看系统记住了什么。
- 删除某条记忆。
- 关闭情绪节奏记忆。
- 重置学习计划。
- 导出词汇和错题。

系统应避免：

- 长期保存无关聊天。
- 使用羞辱性标签。
- 把低置信推断当事实。

当前前端已有“我的学习记忆”页面，支持查看 evidence、置信度、影响范围，并执行编辑、删除、不再使用、我已改善、导出和手动整理。

同时提供：

- 情绪 / 节奏记忆开关，默认关闭。
- 推断偏好记忆开关。
- 低置信记忆入上下文开关，默认关闭。
- 学习计划重置入口，重置未完成 task/session 并写入 operation audit。
- memory metrics：write count、retrieval count、hit rate、used-in-prompt count、user deleted count、stale count。
