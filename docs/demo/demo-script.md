# Demo Script

> 目标时长：5–8 分钟
> 目标观众：面试官或技术评审
> 演示重点：Agent Runtime 学习闭环、可观测性、可回归安全网。

## 准备

启动服务：

```bash
./scripts/dev.sh
```

打开：

- Learner App: http://localhost:5175
- Dev Console: http://localhost:5176
- Debug token: `dev`

如果只演示后端闭环，可使用 Swagger 或 API client；前端 UI polish 仍属于 roadmap。

## 讲解开场 30 秒

BinnAgent 是英语学习场景的个性化 Agent 系统。它不是让 LLM 直接聊天，而是把学习任务变成可暂停、可恢复、可验证的 runtime：用户作答后生成 ExerciseAttempt，更新 Mastery，写入 Memory，安排 Review，再推荐下一步学习动作。

## 演示步骤

### 1. 创建 learner

在 Learner App 或 API 创建一个 learner。讲解点：

- learner 是所有学习数据的 owner。
- 后续 Memory、Episode、ExerciseAttempt、Recommendation 都必须 learner-scoped。

### 2. 开始 Daily Lesson

进入学习中心或调用 Daily Lesson start。预期状态：

- 返回 `episode_id`。
- 返回题面、`thread_id`、`checkpoint_id`、`answer_required=true`。
- episode 进入 `waiting_user`。

讲解点：

- LangGraph 不会一次性跑完整条链路。
- 学习任务必须等待真实用户作答，不能提前生成反馈或写 Memory。

### 3. Graph 等待用户作答

在 Dev Console 打开 Recent Episodes / Graph Runs，找到刚才的 episode。预期可见：

- `graph_interrupted`
- checkpoint status 为 `waiting_user`
- `resume_from=grade_attempt`

讲解点：

- checkpoint 保存题面和恢复点，刷新页面或服务重启后仍能恢复。
- 这是学习 Agent 与普通 Chatbot 的核心差异之一。

### 4. 提交答案

回到 Learner App 提交答案，例如 `Good morning!`。预期：

- checkpoint 变为 completed。
- graph 从 `grade_attempt` 恢复。
- 生成反馈。

讲解点：

- 用户答案是后续评分、掌握度、记忆和推荐的证据来源。

### 5. 生成 ExerciseAttempt

在 Dev Console 查看 EpisodeTrace 或 API 返回。预期：

- 有 `exercise_attempt_id`。
- 有 `exercise_graded` event。
- ToolCall 中可看到 `exercise.grade`。

讲解点：

- ExerciseAttempt 是学习闭环的事实记录，不是只给用户一句反馈。

### 6. 更新 Mastery

查看 answer payload 或 EpisodeTrace。预期：

- 有 `mastery_update`。
- 有 `mastery_updated` event。
- ToolCall 中可看到 `mastery.update`。

讲解点：

- 个性化学习不是 prompt 文案，而是基于作答证据更新掌握度。
- 正确/错误答案会驱动 mastery delta 上下行。

### 7. 写入 Memory

查看 Memory 或 EpisodeTrace。预期：

- 有 `memory_updates`。
- 有 `memory_written` event。
- Memory evidence 指向本次 episode / exercise。

讲解点：

- Memory 不能随便写闲聊摘要，必须带 evidence。
- 后续 Recall 会按 chat、daily plan、vocabulary practice、knowledge exercise 等场景读取。

### 8. 生成 ReviewSchedule

查看 answer payload。预期：

- 有 `review_schedule_result`。
- 有 `review_scheduled` event。

讲解点：

- 错词错因和掌握度会进入复习调度，而不是只停留在当次反馈。

### 9. 推荐下一步学习动作

如果答案暴露语法或词汇弱项，查看 `next_capability_recommendations`。预期：

- 可能推荐 grammar explain、word parts、vocabulary practice 等 capability。
- 点击推荐会写入 capability event 和 Memory。

讲解点：

- RecommendationEngine 用 mastery、memory、review due 和任务上下文生成下一步行动。

### 10. 打开 Dev Console 排查 Agent 行为

在 Dev Console 依次查看：

- EpisodeTrace：episode、events、checkpoint。
- ToolCall：exercise.grade、mastery.update、memory.write、verification.verify_episode。
- PromptExecution：prompt hash、schema status、decision、Langfuse trace reference。
- VerificationReport：required checks 是否通过。
- Simulation Report：对应场景是否回归。

讲解点：

- Dev Console 是 Agent 行为的黑盒拆解工具。
- Graph Run Debug 不保存 raw prompt/raw output；原始模型观测交给 Langfuse。

## 最后 60 秒总结

这套项目的主线是 Agent Runtime，而不是教材解析。教材解析只是冷启动知识来源；真正的工程价值在于：

- 学习任务可暂停、可恢复。
- 学习证据可追踪。
- Memory 和 Mastery 可解释。
- Prompt 输出可约束。
- Agent 行为可用 simulation 回归。
- Dev Console 能排查每一次运行为什么成功或失败。

## Roadmap 说明

未完成或不建议夸大的能力：

- 多步骤 lesson 和生产 PostgresSaver 仍是 roadmap。
- 前端 UI polish 和 demo 数据还需要继续打磨。
- e2e simulation 目前是手动入口，不是默认 CI。
- 教材 OCR/layout-aware extractor 不再作为核心路线重投入。
