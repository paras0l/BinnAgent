# Issue Roadmap Status

> 更新时间：2026-07-04
> 结论：核心面试路线已基本完成。后续不建议继续重投入教材解析；优先做真实用户体验、UI polish、demo script 和部署文档。

| Issue | Title | 目标 | 已完成任务 | 未完成任务 | 当前优先级 | 是否适合继续投入 |
|---|---|---|---|---|---|---|
| #25 | Learner-scoped isolation | 防止多用户场景下跨 learner 读写学习数据 | 新增 current user/current learner dependency、scoped resource helper；加固 Runtime、Daily Lesson、Memory、Explore、ExerciseAttempt、Debug 高风险路径；补 learner isolation 文档和测试 | chat、knowledge、vocabulary、writing phrases、reading、dashboard 等剩余旧路由继续迁移 | 高 | 适合小步继续投入，属于上线前安全底座 |
| #26 | LangGraph Runtime | 让 Daily Lesson 从一次性调用升级为可暂停、可恢复、可验证的学习 runtime | Daily Lesson 支持 checkpoint / interrupt / resume；answer 后闭合 grade/mastery/memory/review/recommend/verify；VerificationReport 阻止 critical failure 静默 completed；Dev Console Graph Runs 可查 trace | 多步骤 lesson、生产 PostgresSaver、官方 `interrupt()/Command(resume=...)` 深度集成、幂等副作用 | 中高 | 适合继续小范围增强，但不建议再大改架构 |
| #27 | Parser Quality | 防止教材解析低质量结果静默进入学习闭环 | ParserRun、ParserQualityReport、TextbookQualityScore、ParserReviewItem、ReviewQueue API、Parser Evidence API、Dev Console Textbook Parsing、golden parser evaluation MVP | layout-aware extractor、OCR、多年级 golden profile、后台 ingest 队列、批量校对审计 | 低到中 | 不建议继续重投入；保留为知识冷启动和质量治理即可 |
| #28 | Simulation / Evaluation | 把 smoke runner 收口成日常开发可用的回归安全网 | scenario contract、assertion engine、metric_groups、baseline/threshold gate、contract/integration/e2e mode、deterministic fake model、impacted simulation 推导、核心 runtime/prompt/memory/mastery scenarios | 独立 test DB integration、真实 e2e、frontend dashboard、更多 long-run persona | 中 | 适合围绕核心路径继续补少量 regression |
| #29 | Prompt Registry + Schema-first | 让结构化 LLM 调用可调试、可评估、可约束 | PromptMetadata、PromptExecutor、PromptExecutionRecord、schema validation/JSON repair/fallback decision、Prompt Debug API、prompt eval CLI、eval_set 和 regression tests | 迁移 vocabulary agent、exercise generation、vocabulary enrichment/detail HTML、graph feedback、essay scoring、dictionary lookup 等直接 model 调用 | 中高 | 适合继续按路径迁移，但不需要新架构 |

## 总体结论

- **核心面试路线已基本完成**：Agent Runtime、Memory/Mastery、PromptExecutor、Simulation、Learner Isolation、Parser Quality 和 Dev Console 已形成完整工程故事。
- **教材解析不再作为主线投入**：它已经能作为冷启动知识来源，并有质量门禁和人工校对闭环；继续深挖 OCR/layout extractor 的收益低于产品体验。
- **下一阶段优先级**：真实用户体验、UI polish、稳定 demo script、部署文档、演示数据、少量关键路径 e2e。
- **推荐讲法**：BinnAgent 的亮点不是“英语教材解析”，而是“学习型 Agent Runtime 如何做到可追踪、可验证、可个性化、可回归”。
