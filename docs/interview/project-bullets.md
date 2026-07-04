# Project Bullets

## 精简版 3 条

- 构建面向英语学习场景的个性化 Agent 系统，将 LangGraph Runtime、ExerciseAttempt、Mastery、Memory、Review 和 Recommendation 串成可追踪学习闭环。
- 设计 Prompt Registry + PromptExecutor + Schema-first 机制，结构化 LLM 输出必须经过 schema validation / repair / fallback decision 后才能写入关键业务表。
- 建立 Dev Console 与 Simulation/Evaluation 回归安全网，可查看 EpisodeTrace、ToolCall、PromptExecution、VerificationReport，并用 contract/integration/e2e mode 防止 Agent 行为退化。

## 标准版 5 条

- 基于 FastAPI + LangGraph 实现英语学习 Agent Runtime，Daily Lesson 支持 checkpoint / interrupt / resume，等待用户作答后继续评分、反馈和推荐。
- 设计学习闭环数据流：ExerciseAttempt 记录作答证据，MasteryEngine 更新掌握度，MemoryWriter 写入学习记忆，ReviewSchedule 安排复习，RecommendationEngine 生成下一步学习动作。
- 落地 Prompt Registry、PromptExecutor 和 PromptExecutionRecord，统一管理 prompt metadata、schema、model policy、hash、schema status、repair/fallback 和业务 decision。
- 构建 Simulation / Evaluation 安全网，内置 learner persona、scenario contract、assertion engine、baseline/threshold gate 和 impacted simulation 推导脚本。
- 建设 Dev Console 调试面板，集中排查 EpisodeTrace、ToolCall、PromptExecution、VerificationReport、Memory/RAG evidence 和教材解析质量。

## 技术深入版 8 条

- 将学习任务抽象为 TaskSpec，并通过 AgentEpisode、LearningEvent、ToolCallRecord 和 EvidenceRef 串联任务目标、工具调用、证据和验证结果。
- 在 LangGraph Daily Lesson 中实现 answer_required checkpoint：无用户答案时 graph 停在 waiting_user，提交答案后从 `grade_attempt` 恢复，避免未作答就写 Memory 或安排复习。
- 构建 ExerciseAttempt → Mastery → Memory → Review → Recommendation 闭环，用作答结果、提示次数、错误类型和 mastery delta 驱动个性化复习与下一步学习。
- 实现 Memory v2 Retain / Recall / Reflect，区分 event、episode、learner model、teaching strategy，并提供可解释、可禁用、可删除的 learner memory control。
- 实现 PromptExecutor schema-first 治理：PromptMetadata 绑定 output_schema/model_policy，输出经过 JSON repair、schema validation、fallback decision 后记录 PromptExecutionRecord。
- 明确 Langfuse 与本地记录边界：Langfuse 保存 raw prompt/output/token/cost/latency，本地只保存 prompt_hash/input_hash/schema status/decision 和 trace reference，降低隐私与重复观测成本。
- 建立 Simulation / Evaluation 回归体系：contract mode 用 MockTransport 跑默认 CI，integration mode 用 ASGITransport + deterministic fake model，e2e mode 指向真实环境手动回归。
- 为教材 ingest 增加 ParserRun、ParserQualityReport、TextbookQualityScore、ParserReviewItem 和 golden parser evaluation，确保冷启动知识源不会低质量静默发布。
