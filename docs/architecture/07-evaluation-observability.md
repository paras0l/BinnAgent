# 07. Evaluation 与 Observability 方案

## 1. 模块目标

评估体系要同时回答两类问题：

1. 学习者有没有进步？
2. Agent 有没有用正确方式教学？

不能只看模型回答是否流畅。

## 2. 学习效果指标

### 2.1 词汇

- 到期复习完成率。
- 词汇掌握率。
- 错词复错率。
- 平均记忆间隔。
- 高频词覆盖率。

### 2.2 阅读

- 阅读题正确率。
- 单题平均耗时。
- 主旨题正确率。
- 细节定位正确率。
- 推断题正确率。
- 错因重复率。

### 2.3 听力

- 听力题正确率。
- 转写准确率。
- 关键词漏听率。
- 连读弱读相关错误数。
- 复述完成率。

### 2.4 写作

- 作文评分趋势。
- 二次修改提升幅度。
- 高频语法错误下降率。
- 结构完整性评分。
- 表达复用次数。

### 2.5 口语

- 口语任务完成率。
- 平均回答长度。
- 停顿/卡壳点数量。
- 高频错误下降率。
- 场景表达覆盖率。

### 2.6 执行和陪伴

- 连续学习天数。
- 任务完成率。
- 计划调整次数。
- 用户主动开始课程比例。
- 中断恢复率。

## 3. Agent 质量指标

| 指标 | 含义 |
|---|---|
| Feedback Precision | 反馈是否抓住关键问题 |
| Feedback Actionability | 反馈是否可执行 |
| Overcorrection Rate | 是否一次纠错过多 |
| Memory Write Precision | 写入 Memory 的内容是否有价值 |
| Plan Fit Rate | 计划是否匹配时间和水平 |
| Tool Selection Accuracy | 工具选择是否正确 |
| User Output Ratio | 用户输出占比是否足够 |

## 4. Eval 集设计

### 4.1 Vocabulary Eval

测试：

- 是否识别用户真正不熟的词。
- 是否能生成合适复习间隔。
- 是否能区分释义错误、搭配错误、发音问题。

### 4.2 Reading Tutor Eval

测试：

- 是否避免直接全文翻译。
- 是否先引导用户理解主旨。
- 是否能准确解释题目错因。
- 是否能提取可复用表达。

### 4.3 Listening Tutor Eval

测试：

- 是否能从转写错误推断错听原因。
- 是否能区分生词问题和发音问题。
- 是否能设计逐句精听任务。

### 4.4 Writing Feedback Eval

测试：

- 是否先让用户自己写。
- 是否指出最关键的 1-3 个问题。
- 是否给二次修改任务。
- 是否避免直接代写。

### 4.5 Speaking Feedback Eval

测试：

- 是否少打断。
- 是否关注清晰度和自然度。
- 是否记录可迁移错误。

### 4.6 Plan Generation Eval

测试：

- 是否符合用户时间预算。
- 是否符合考试日期。
- 是否包含主动输出。
- 是否在连续失败后降级。

### 4.7 Emotional Safety Eval

测试：

- 是否避免羞辱和施压。
- 是否在用户疲惫时降低任务。
- 是否提供具体恢复动作。

## 5. Tracing

当前实现接入 Langfuse Python SDK v4，并保留本地业务事件表。未配置密钥时 tracing
自动关闭，不影响 Ollama、本地教材解析和练习流程。

每次 run 记录：

- graph name。
- node 输入输出摘要。
- prompt version。
- model。
- token。
- latency。
- tool calls。
- memory reads/writes。
- feedback result。

已覆盖的 observation：

- `ollama-chat` / `ollama-chat-stream`
- `ollama-embed`
- `textbook-rag-index`
- `textbook-rag-retrieval`
- `daily-lesson-graph`，并通过 Langfuse `CallbackHandler` 展开 LangGraph 节点调用。

Graph trace 传播 `learner_id`、学习 `session_id` 和 LangGraph `thread_id`，并带有
`langgraph`、`ollama`、`local-model` 标签。

## 6. 事件埋点

前端事件：

```text
lesson_started
task_viewed
answer_submitted
feedback_viewed
revision_submitted
review_completed
lesson_completed
lesson_abandoned
```

后端事件：

```text
graph_started
node_completed
tool_called
memory_written
review_scheduled
eval_completed
```

## 7. 周报指标

给用户看的指标：

- 本周完成天数。
- 完成任务数。
- 新增掌握词汇。
- 高频错误 Top 3。
- 最有进步的技能。
- 下周一个重点。

给系统看的指标：

- 用户留存。
- 任务完成率。
- Agent 反馈采纳率。
- Memory 命中率。
- 复习准时率。
- 模型成本。
- Ollama 本地模型可用率。
- 本地模型平均延迟。
- 模型 fallback 次数。
- 结构化输出解析失败率。

## 8. 回归测试

每次改 prompt、Agent 或工具后运行：

- 10 个词汇用例。
- 10 个阅读讲解用例。
- 10 个写作反馈用例。
- 5 个计划生成用例。
- 5 个情绪安全用例。

通过标准：

- 不降低关键指标。
- 不增加代写倾向。
- 不增加过度纠错。
- 不破坏 Memory 写入格式。

## 9. 本地模型专项评估

因为项目默认使用 Ollama 本地模型，需要单独评估本地模型是否满足教学任务。

评估维度：

- JSON schema 通过率。
- 中文教学解释清晰度。
- 英文例句自然度。
- 写作反馈是否过度纠错。
- 阅读讲解是否直接翻译全文。
- Memory candidate 提取准确率。
- 平均延迟和 P95 延迟。

最低上线门槛：

- 路由和意图识别 JSON 通过率 >= 98%。
- Memory candidate schema 通过率 >= 95%。
- 写作反馈不得直接代写最终作文。
- 本地模型不可用时，系统能给出清晰错误或进入已授权 fallback。
