# 13. Current Scope and Status

> 更新时间：2026-07-02
> 目的：把当前实现、部分实现和仍处于设计中的内容显性化，避免把架构目标误读成已落地功能。

## 状态图例

| 标记 | 含义 |
|---|---|
| 已实现 | 有后端/API、前端入口或测试支撑，可运行验证 |
| 部分实现 | 已有骨架或单点能力，但学习闭环、可靠性或界面仍缺口 |
| 设计中 | 文档已有目标，代码尚未形成完整能力 |

## 当前产品线

| 产品线 | 状态 | 说明 |
|---|---|---|
| 教材线 | 部分实现 | 多教材 source 库、教材切换、七年级上/下册 profile、单元词汇、RAG chunk、场景化多题型练习和前端入口已存在；八/九年级可上传并走通用解析/校对 fallback |
| CET 备考线 | 设计中 | 7 天计划、阅读训练、写作二改和周报仍主要在架构文档中 |
| 通用英语陪伴 | 部分实现 | Chat、Memory 摘要、Dashboard 和词汇沉淀已有基础闭环 |

## 共享底座状态

| 模块 | 状态 | 当前能力 | 下一步 |
|---|---|---|---|
| FastAPI API | 已实现 | learners、chat、memory、dashboard、knowledge、vocabulary、grammar 等 routers | 统一 current learner 认证授权 |
| React 前端 | 部分实现 | 多页面学习入口、SSE chat、知识库和词汇练习；Issue #20 UI/UX 统一标准首轮落地，新增统一 Button/FormField/StatusBanner/ConfirmDialog/ReasonCard/EvidencePanel；普通学习端主导航保留 AI对话 / 探索 / 学习中心，Memory/Runtime/Trace/Prompt/Tool/Evidence 等内部页面移入独立 Dev Console；KnowledgeBase 已升级为教材结构 / 单元学习 / 练习任务 / 解析校对工作台；Explore 已接入“词根与词缀”工作区；Grammar/Vocabulary/WordParts/Reading 已接入知识点配套 ExerciseBlock、练习结果摘要、AI 生成练习可编辑保存和后端优先持久化 fallback | 更深入的数据驱动推荐、恢复提示、更多页面内 drawer 化编辑 |
| LangGraph daily lesson | 部分实现 | daily lesson graph 已在 `run_learning_task` 后支持 conditional interrupt；`LearningGraphCheckpoint` 持久化单题 waiting_user checkpoint；start/answer/status API 支持恢复题面和提交后完成 grading、memory、review、verification；学习端可启动 AI 每日题并刷新恢复，Dev Console 可查看 checkpoint | 多步骤 lesson、LangGraph 官方 checkpointer 深度集成、更多非知识题 handler |
| Agent Runtime / Harness | 部分实现 | 新增 TaskSpec、AgentEpisode、LearningEvent、ToolCallRecord、EvidenceRef、VerificationReport、ToolRegistry、MasteryEngine、RecommendationEngine、LearningOrchestrator、LearningGraphCheckpoint；Knowledge Exercise / Daily Lesson / Explore 入口已能创建 episode trace；Dev Console 已提供 Learners / Recent Episodes 上下文选择，以及 Episode Debug、Tool Registry、Tool Call Records、Evidence Debug、RAG Debug、Prompt Debug、VerificationReport 和 Simulation Report；新增 `/api/debug/learners`、`/api/debug/rag/search`、`/api/debug/simulation/scenarios`、`/api/debug/simulation/reports/latest`；Debug API 默认关闭并要求 token | 更多工具强制走 registry、证据详情解析和可回放 UI |
| Memory | 部分实现 | 4 层学习记忆架构 + HindSight-inspired Retain/Recall/Reflect 口径已落地；统一 memory event/operation、LearningEpisode、LearnerModelMemory、TeachingStrategyMemory、MemoryWriter/Retriever/Curator、显式 L1-L4 layer metadata、ErrorPattern governance、WritingPhraseMastery；普通学习端只保留学习状态摘要，Memory Center、导出/删除/禁用/我已改善、memory_context log 和 hit-rate 指标移入 Dev Console | 更完整 debug dashboard 图表、更多 regression eval、更多 session 类型反思规则 |
| Vocabulary Learning | 部分实现 | 单元 enroll、用户可编辑个人词卡、new/review/spelling session、attempt、错因记录、mastery vector、发音 URL；前端新增词根词缀库、拆词练习、localStorage 掌握标记和 morphology 展示/降级 | morphology 后端持久化、LearningProgress/Memory 联动、薄弱原因总结、题型推荐、更多表达迁移题 |
| Knowledge Base / RAG | 部分实现 | PDF 解析、chunk、embedding、文本 fallback、8 题混合练习流、hint/retry/rubric 反馈；overview 返回 sources、parser/ingest 证据、review queue、来源页码和低置信词条；前端可在多本教材之间切换；课程练习和知识点验收共用统一 ExerciseAttempt target/summary 模型 | hybrid retrieval、golden query set、练习 session 总结、更多年级 golden profile |
| Prompt & Parsing Governance | 部分实现 | Prompt Registry MVP、核心 prompt 模板、写作导入 JSON-first extraction、教材 manifest/profile/parser report；prompt render API 已作为 Debug API 保护，普通页面使用本地兼容生成指令 fallback；教材低置信词条支持确认、修改发布和忽略 | 更多 prompt eval、词汇/语法 schema-first 回填、更细的审计历史 |
| Model Provider | 部分实现 | Ollama chat/stream/embed/health，结构化 JSON repair retry | task policy、local_only 强约束、持久化 model_call_logs |
| Observability | 部分实现 | Langfuse observation 和运行时表 | run_id 贯通 graph/model/tool/memory，Dashboard 可视化 |
| Evaluation / Simulation | 部分实现 | `src/simulation` 提供 deterministic learner persona、behavior policy、scenario runner、assertion engine 和结构化 simulation report；已覆盖 smoke、vocabulary agent deposit、vocabulary practice adaptation、daily graph 基线和 episode runtime knowledge practice；report 增加 episode_count、completed_episode_count、verification_pass_count、avg_tool_latency_ms 等 runtime_metrics | 扩展写作好句闭环、Memory 可控性 regression、LLM-assisted learner 和 dashboard |
| CI | 已实现 | GitHub Actions 覆盖 backend lint/test、frontend lint/test/build/build:console、migration 文本检查 | Alembic 在线迁移检查和端到端 smoke |
| Writing Phrasebook | 基础版已实现 | 探索页写作入口、句式 CRUD、外部模型结果提取、候选收藏、识别/填空/替换练习和 attempt 记录 | 模型辅助编辑、精细 mastery、作文批改与翻译练习深度联动 |

## Issue 对应落地

| GitHub issue | 本次落地 | 仍需后续 |
|---|---|---|
| #2 代码检视与优化 | 私有教材重复上传不跨 learner 复用；RAG embedding 失败记录索引质量；chat 序号约束模型对齐；CI | 统一认证授权、上传后台任务、流式 run 状态恢复 |
| #3 文档一致性 | 更新 `AGENTS.md`、`docs/web-frontend.md`、README 状态摘要和本文档 | 持续给主要架构文档补状态标签 |
| #4 MVP 缺口 | 新增当前 scope/status 表，明确 CET 与七年级教材线边界；Daily Lesson 已支持单题 answer_required checkpoint/resume | 多步骤 daily lesson、reading/writing/weekly report |
| #5 下一阶段增强 | RAG search 返回 mode/embedding/chunk/source 信息；model structured output repair retry；CI | vocabulary 多维掌握度、observability dashboard、eval dataset |
| #7 教材练习题升级 | `ExerciseBlueprint` 生成 8 道场景化混合题；支持 `choice_context`、`fill_blank`、`dialogue_complete`、`error_fix`；新增 linter、rubric grader、hint/retry 反馈；前端改为一屏一题练习流；答题事件写入 score、error_type、next_review_signal | 独立 exercise session 表、结束复盘卡、根据 learner mastery 动态选题、micro writing/roleplay |
| #11 词汇模块升级 | 新增 `VocabularyUserOverride`、`VocabularyMistake`、`VocabularyMasteryVector`；词汇详情和练习流读取用户覆盖层；新词学习/今日复习入口分离；用户例句优先参与填空上下文；隐藏释义不进入返回 payload；错因可修正/删除 | 更丰富的题型生成、Dashboard 弱项聚合、roleplay/micro writing 生产题 |
| #12 好句收藏馆 | 新增 `writing_phrases`、练习和 attempt 数据表；提供 CRUD/import/exercises/attempts API；探索页接入好句收藏馆前端工作台 | P2 模型辅助编辑、P3 到期复习/mastery、P4 作文批改和翻译练习自动推荐 |
| #14 Memory Core | 新增 `learning_memory_events`、`memory_operations`、`writing_phrase_masteries`、`memory_context_logs`、`learner_memory_settings`；实现 writer/retriever/curator/explainer/manager；词汇、知识、写作句式、chat/session、作文批改、LangGraph 写入或读取统一 memory；Memory Center 已从普通学习端移入 Dev Console；支持查看 evidence、编辑、删除、禁用、我已改善、导出、手动整理、重置计划、情绪/节奏开关、低置信上下文开关；summary 增加 recent events 和 active weaknesses；metrics 增加 retrieval、hit-rate、used-in-prompt、stale | 更完整 memory debug dashboard 图表、长期 regression eval 扩展 |
| #19 HindSight-inspired Memory | 明确 Memory v2 采用 Retain / Recall / Reflect / Explain / Control；新增 `learning_episodes`、`learner_model_memories`、`teaching_strategy_memories`；`record_event()` 自动补 `evidence_ref`；`MemoryCurator.reflect()` 可从事件生成 episode、learner model、teaching strategy；`MemoryRetriever.for_chat/for_daily_plan/for_vocabulary_practice/for_knowledge_exercise/for_essay_review/for_writing_phrasebook/for_memory_explanation` 已实现；Chat、词汇、教材、作文、写作句式入口使用场景化 recall；用户删除/禁用 learner model 或 strategy 后后续 recall 排除；Memory Center 展示新卡片和指标 | 扩展更多 episode 模板、resolved 状态自动化、teaching strategy 效果评估和 dashboard 可视化 |
| #15 Learner Simulation Agent | 新增 `src/simulation/`、`tests/simulation/` 和 `scripts/run_learner_simulation.py`；至少 5 个内置 persona；deterministic scenario 覆盖 smoke journey、Vocabulary Agent 沉淀、词汇练习 adaptation、episode runtime knowledge practice 和 daily lesson checkpoint resume；runner 通过 API 调用系统并直接调用 daily lesson graph；每次运行生成结构化 report | 写作好句、Memory 可控性 regression、LLM-assisted 模式和 simulation dashboard |
| #16 教材解析质量止血 | 新增 `books/manifest.yaml`、parser profile、parser quality report；词汇条目增加 `raw_line`、`confidence`、`warnings` 和 `requires_review`；ingest metadata 写入 manifest/profile/report；KnowledgeBase overview 暴露 review queue/parser evidence，前端可确认、修改发布或忽略低置信词条 | layout-aware extractor、批量校对、校对审计历史 |
| 多年级教材上传与切换 | KnowledgeBase overview 支持 `source_id` 和 `sources[]`；上传不再拒绝八/九年级文件名，未知年级标记为 `unknown`；七下新增 manifest/profile，词表 parser 支持 `Words and Expressions` heading；未知教材至少生成“全册材料”节点和 RAG chunks | 八/九年级专用 manifest/profile、跨教材知识归并、学习进度 source 偏好持久化 |
| #17 Schema-first 回填 | 新增 `src/extraction`，写作好句导入优先 JSON schema，保留 regex fallback 且返回 `parse_mode`、`warnings`、`confidence`；新增 golden-style tests | 词汇字段回传和语法微课 machine_data 的完整保存链路 |
| #18 Prompt Registry | 新增 `src/prompts`、版本化 markdown 模板、schema/model policy 绑定、受 Debug Console token 保护的 `/api/prompts/{prompt_id}/render`；迁移 chat、vocabulary agent、grammar prompt、writing phrase prompt；新增 prompt eval fixtures | 更完整 observability 持久化、prompt evaluator、更多 P2 prompt 迁移 |
| #20 UI/UX 统一标准 | 阅读 issue 正文与评论，更新 `docs/frontend-design-system.md`、`docs/web-frontend.md`、README 和本文档；新增统一 UI 原语；逐页覆盖 AppShell/Header、Chat、Explore、Dashboard、Writing Phrasebook、Grammar、Vocabulary Detail、Pronunciation、KnowledgeBase、VocabularyPractice、Dashboard 词汇工作区和 Login；学习中心升级为今日学习驾驶舱；Memory/Runtime/Debug 类页面改由 Dev Console 承载；KnowledgeBase 解析校对 workspace 已落成，推荐原因和证据表达开始统一 | 更深层组件拆分、更多编辑态 Drawer 化、视觉回归截图 |
| #23 词根与词缀 | Explore 词汇分类新增“词根与词缀”入口；新增 `WordPartsPage`，包含方法入门 / 词根词缀库 / 拆词练习 / 我的掌握四个 workspace；内置 10 个前缀、10 个词根、10 个后缀和 8 张练习卡；`VocabularyDetailPage` prompt 增加可解析构词区域要求并提供 morphology fallback；`VocabularyPracticePage` 在 new/review/spelling 中按模式展示构词提示，拼写练习只显示前后缀安全提示；新增 Vitest 数据 helper 测试 | 后端 `morphology` 字段持久化、AI HTML 构词区域解析入库、LearningProgress/Memory 沉淀 |
| #24 知识点配套练习与验收 | 新增统一前端 Exercise 类型、内置题、ExerciseBlock、ExerciseRenderer、ExerciseAttemptSummary、ExerciseLearningSignal；Grammar/Vocabulary/WordParts/Reading 场景内嵌练习块；升级现有 `exercise_attempts` 表为全局 ExerciseAttempt target 模型；为 `ExerciseQuestion` 增加统一 ExerciseItem mapper 和 `/api/learners/{learner_id}/exercises` 查询入口，课程知识库题源与内置题都具备 target/source；课程知识库练习 UI 和页面知识点验收共用 ExerciseRenderer、`ExerciseAttemptService`、summary 规则和 localStorage fallback；新增 `/api/learners/{learner_id}/exercises/generate` 与 AddExerciseForm，AI 生成题先进入可编辑表单，确认保存后作为 generated/manual ExerciseItem 进入统一渲染 | 更多题型、Memory 真正写入、mastery/error pattern 联动、后端 ExerciseItem 管理 |
| Core Runtime Upgrade | 新增 `src/runtime`、`src/evidence`、`src/mastery`、`src/recommendation`、`src/learning`、`src/verification`；Knowledge Exercise 提交写入完整 AgentEpisode trace；Daily Lesson start/answer/status 接入 TaskSpec + LearningGraphCheckpoint checkpoint/resume；Explore skill start 接入 TaskSpec；`/runtime/episodes/:episodeId` Debug 页面已移入 Dev Console；simulation 增加 episode runtime 和 checkpoint resume regression | 多步骤 checkpoint/resume、权限隔离、更多 handler 从 not_implemented 变成完整闭环 |

## 可运行能力

```bash
./scripts/dev.sh
python -m pytest tests/ -v
cd binnagent-frontend && npm run lint && npm run test && npm run build && npm run build:console
```

## 最近风险

- 多用户远程部署前必须把 learner 身份从请求参数迁移到统一认证依赖。
- 教材 ingest 仍在请求链路内执行，较大 PDF 或 embedding 慢时需要后台任务。
- Daily lesson 目前是单题单 active checkpoint，后续多步骤 lesson 需要扩展 checkpoint 编排与恢复策略。
