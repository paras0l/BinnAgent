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

## 2. Memory 分层

| 层级 | 范围 | 内容 | 技术 |
|---|---|---|---|
| Working Context | 单次 LLM 调用 | 当前任务所需最小上下文 | prompt context |
| Session Memory | 单次课程 | 当前材料、答案、反馈、中间状态 | LangGraph state |
| Thread Memory | 一段对话 | 多轮对话和课程连续状态 | checkpointer |
| Long-term Memory | 跨会话 | 学习画像、错词错因、复习计划 | store + DB + vector |

## 3. Memory 类型

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

## 4. Namespace 设计

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

## 5. Memory 写入策略

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

## 6. Memory Curator

Memory Curator 是后台 Agent 或任务，负责维护记忆质量。

职责：

- 去重：合并同义错词、重复错误模式。
- 降噪：偶发错误不升级为长期弱点。
- 合并：多个孤立错误归并为错误模式。
- 冲突处理：用户已掌握后降低旧弱点权重。
- 遗忘：过期、无用或用户要求删除的记忆清理。

## 7. 复习调度

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

## 8. Memory 读取策略

每次 session 只读取必要 Memory：

- 今日计划。
- 到期复习。
- 最近 3-5 个高频错误。
- 当前技能相关弱点。
- 用户偏好。

避免把所有历史塞进 prompt。

## 9. 隐私和可控性

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
