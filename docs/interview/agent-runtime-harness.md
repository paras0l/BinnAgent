# Agent Runtime Harness Interview Script

> 目标：把 BinnAgent 讲成一个可维护、可调试、可回归的学习型 Agent Runtime，而不是一个普通 Chatbot 或教材解析 demo。

## 1. 项目一句话介绍

BinnAgent 是面向英语学习场景的个性化 Agent 系统：它把学习任务编排、用户作答、练习评分、掌握度更新、长期记忆、复习安排、下一步推荐和调试验证串成可追踪、可恢复、可回归的学习闭环。

## 2. 为什么不是普通 Chatbot

普通 Chatbot 的核心是“用户问一句，模型答一句”。BinnAgent 的核心是“围绕学习证据推进状态”：

- 每次学习任务会先形成 `TaskSpec`，明确目标、允许工具、成功标准和验证策略。
- 运行时创建 `AgentEpisode`，把 graph 节点、工具调用、学习事件、证据和验证结果串起来。
- 用户答案会生成 `ExerciseAttempt`，再驱动 `Mastery`、`Memory`、`ReviewSchedule` 和 `Recommendation`。
- Dev Console 和 simulation 可以回放“为什么推荐、用了什么证据、写了什么记忆、哪里失败”。

所以它的卖点不是更会聊天，而是学习过程可解释、可验证、可持续个性化。

## 3. LangGraph 为什么需要 checkpoint / interrupt

学习 Agent 不能在没有用户答案时把后续步骤全跑完。Daily Lesson 当前链路大致是：

```text
load_profile -> detect_intent -> select_learning_goal -> route_skill_agent
-> run_learning_task -> wait_for_answer -> grade_attempt -> update_mastery
-> generate_feedback -> update_memory -> schedule_review
-> recommend_learning_action -> verify_episode -> summarize_session
```

当 graph 运行到 `wait_for_answer` 且缺少 `learner_answer` 时，episode 进入 `waiting_user`，业务 checkpoint 保存题面、`thread_id`、`resume_from=grade_attempt`、required input schema 和 state snapshot。

用户提交答案后，系统从 `grade_attempt` 恢复，继续评分、掌握度、Memory、Review、Recommendation 和 Verification。这个设计解决三个问题：

- 页面刷新或服务重启后，仍能恢复当前题面和恢复点。
- 没有答案时不会误写 Memory、Mastery 或 Review。
- Dev Console 可以看到 graph 是在哪里暂停、如何恢复、最终哪些 checks 通过。

当前边界：主要支持单题单 active checkpoint；生产 PostgresSaver 和 LangGraph 官方 `interrupt()/Command(resume=...)` 的深度集成仍是 roadmap。

## 4. 为什么 Memory 不能随便写

英语学习里的 Memory 会影响后续推荐、提示、练习难度和学习策略。如果把闲聊摘要、未验证模型输出或缺少证据的判断直接写进去，会污染 learner model。

BinnAgent 的原则是：

- Memory 写入必须来自学习事件或明确证据，例如 `ExerciseAttempt`、episode、knowledge target、review result。
- Memory 使用 Retain / Recall / Reflect 分层：先记录事件，再按场景召回，最后沉淀 learner model 或 teaching strategy。
- 用户可解释、可删除、可禁用部分 memory，避免长期个性化变成不可控黑盒。
- 不允许绕过 schema validation 或 evidence 直接写关键业务表。

面试时可以强调：Memory 不是“越多越好”，而是必须有 provenance、scope 和治理边界。

## 5. Mastery 如何驱动个性化学习

Mastery 是把学习行为变成个性化动作的中间层。系统不会只根据用户自述“我不会”，而是综合：

- 正确率和分数。
- 提示次数、重试次数、错误类型。
- 当前知识点、词汇、句式或练习 target。
- 上一次掌握度、置信度和遗忘风险。

这些信号会生成 `MasteryUpdateResult`，再影响 ReviewSchedule 和 RecommendationEngine。比如同一单词如果拼写错但释义会，系统可以推荐 spelling practice；如果语法点连续错，系统可以推荐 grammar micro lesson。

面试讲法：个性化不是“换一个 prompt 口吻”，而是用学习证据驱动掌握度、复习和下一步行动。

## 6. PromptExecutor 和 Langfuse 的边界

PromptExecutor 负责“这个结构化 LLM 输出能不能进入业务流程”，Langfuse 负责“原始模型调用如何观测”。

本地 `PromptExecutionRecord` 记录：

- `prompt_id`、version、prompt_hash、input_hash。
- output_schema、model_policy。
- schema validation status、repair_used、fallback_used。
- decision、confidence、source module。
- Langfuse trace reference。

它不记录 raw prompt、raw output、token、cost、latency，因为这些属于 Langfuse 观测边界。这样做有两个好处：

- 本地业务库只保留可索引、可审计的判定信息，降低隐私和重复存储成本。
- Prompt Debug 可以回答“哪个 prompt 版本、哪个 schema、哪个 decision 导致业务行为”，而不用重新实现一套 ModelCallLog。

当前边界：`writing_phrase.import` 等路径已接入 schema-first；vocabulary agent、exercise generation、essay scoring、dictionary lookup 等直接 model 调用仍需继续迁移。

## 7. Simulation 为什么是 Agent 应用的回归安全网

Agent 应用的风险在于：改 prompt、memory、graph、mastery 或 parser 时，单元测试通过也可能让整条学习链退化。Simulation 把关键用户旅程变成可重复检查的 scenario。

当前分三层：

- `contract`：使用 MockTransport，验证 API contract、scenario、assertion，适合作为默认 CI。
- `integration`：使用 ASGITransport、test DB 和 deterministic fake model provider，避免依赖真实 LLM 随机输出。
- `e2e`：指向真实 base_url，适合本地或发布前手动回归。

已覆盖的核心场景包括 Daily Lesson checkpoint resume、缺答案不得写 Memory、vocabulary practice adaptation、episode runtime knowledge practice、LLM JSON missing field repair 等。

面试讲法：simulation 是 Agent 产品的“行为回归测试”，检查的是跨模块学习链，而不是单个函数。

## 8. Dev Console 如何帮助排查 Agent 行为

Dev Console 是面向开发和调试的独立入口，普通 Learner App 不暴露这些内部页面。当前可查看：

- EpisodeTrace：episode 状态、events、checkpoint、node summaries。
- ToolCall：exercise grading、mastery update、memory write、verification 等工具调用。
- PromptExecution：prompt hash、schema status、repair/fallback、decision、Langfuse trace id。
- VerificationReport：deterministic / schema / business_rule / evidence checks。
- Memory / RAG / Parser Quality / Simulation Report。

一个典型排查路径是：

1. 从 Recent Episodes 找到 learner 的最新 episode。
2. 打开 Graph Runs 看 graph 是否停在 `waiting_user` 或是否完成。
3. 查看 ToolCall 确认评分、Mastery、Memory、Review 是否执行。
4. 查看 PromptExecution 确认结构化输出是否 schema valid，是否触发 repair 或 fallback。
5. 查看 VerificationReport 判断是否因为 critical check 失败进入 `verification_failed`。

Debug API 默认关闭并由 `require_debug_access` 保护；Graph Run Debug 不展示 raw prompt / raw output。

## 9. 三分钟讲稿

> BinnAgent 是一个英语学习 Agent Runtime，而不是普通聊天机器人。普通 Chatbot 主要是用户问、模型答，但学习系统真正重要的是长期状态：用户做了什么题、哪里错了、掌握度怎么变、记忆写了什么、下一步该练什么。
>
> 我把一次学习任务抽象成 TaskSpec，运行时创建 AgentEpisode。Daily Lesson 用 LangGraph 编排，但不会一次跑完；它会在需要用户作答时 checkpoint，等答案提交后再从评分节点恢复，继续生成 ExerciseAttempt、更新 Mastery、写 Memory、安排 Review、推荐下一步学习。
>
> 为了让 LLM 输出不污染业务数据，我做了 PromptExecutor 和 schema-first：结构化输出必须经过 JSON repair、schema validation 和 fallback decision，才允许进入 Memory、Mastery、KnowledgePoint 或 WritingPhrase 这些关键表。原始 prompt 和 output 交给 Langfuse，本地只记录业务判定和 trace reference。
>
> 复杂 Agent 很容易回归，所以我还做了 Simulation / Evaluation：contract mode 默认跑 API 行为，integration mode 用 deterministic fake model 跑更完整闭环，e2e 只做手动回归。最后 Dev Console 可以看到 EpisodeTrace、ToolCall、PromptExecution 和 VerificationReport，帮助解释每一次 Agent 行为为什么成功或失败。

## 10. 当前边界与 Roadmap

已完成的核心面试路线：

- Learner-scoped isolation 的高风险路径加固。
- LangGraph Daily Lesson 单题 checkpoint / interrupt / resume。
- ExerciseAttempt → Mastery → Memory → Review → Recommendation 闭环。
- Prompt Registry + PromptExecutor + Schema-first 第一阶段。
- Langfuse raw tracing 与本地业务记录边界。
- Simulation / Evaluation mode 分层和核心 regression scenarios。
- ParserRun / QualityGate / ReviewQueue 作为教材冷启动质量治理。
- Dev Console Debug 入口。

仍是 roadmap 的能力：

- 多步骤 Daily Lesson 和生产 PostgresSaver。
- 剩余直接 model 调用迁移到 PromptExecutor。
- 剩余旧 router 完整 learner-scoped isolation。
- 更多真实 DB integration/e2e simulation 和 dashboard。
- 前端 UI polish、演示数据、部署文档。
- 教材 OCR / layout-aware extractor 不再作为核心路线重投入。
