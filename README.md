# BinnAgent

BinnAgent 是面向英语学习场景的个性化 Agent 系统。它不是普通 Chatbot，而是把学习任务编排、用户作答、练习评分、掌握度更新、长期记忆、复习安排、下一步推荐和调试验证串成可追踪、可回归的学习闭环。

**核心闭环**：TaskSpec → LangGraph Runtime → ExerciseAttempt → Mastery → Memory → Review → Recommendation → Verification

核心能力包括：

- **LangGraph Runtime**：Daily Lesson 支持 checkpoint / interrupt / resume，等待真实用户作答后再继续评分和反馈。
- **Memory + Mastery**：用学习证据更新掌握度、错因、复习计划和个性化推荐。
- **PromptExecutor + Schema-first**：结构化 LLM 输出必须经过 schema validation / repair / fallback decision 后才能进入业务写入。
- **Simulation / Evaluation**：contract / integration / e2e 分层回归，覆盖学习闭环、Prompt schema、Memory/Mastery 和 Runtime trace。
- **Dev Console**：集中查看 EpisodeTrace、ToolCall、PromptExecution、VerificationReport、Memory、RAG 和解析质量。
- **学习者账号**：邮箱验证码登录，同一邮箱可选择多个独立学习者；新用户通过可追踪邀请关系的邀请码注册。

教材解析用于冷启动知识来源和教材线体验，不是项目主卖点；项目主线是“可解释、可验证、可持续个性化”的 Agent Runtime。

## 快速开始

### 一键启动开发环境

```bash
./scripts/dev.sh
```

脚本会启动 Docker 服务（PostgreSQL、Redis、后端 API）、执行数据库迁移，并启动前端开发服务器。
默认会同时启动 Learner App 和 Dev Console；Dev Console 本地 token 默认为 `dev`。

- 后端 API：http://localhost:8000/docs
- 学习端页面：http://localhost:5175
- Dev Console：http://localhost:5176

### Docker 部署（推荐）

```bash
docker compose up -d
docker compose exec app alembic upgrade head
ollama pull gemma4:e2b
ollama pull nomic-embed-text:latest
```

访问 http://localhost:8000/docs 查看 API 文档。

### 本地 Langfuse（按需开启）

```bash
./scripts/langfuse.sh setup
./scripts/langfuse.sh start
./scripts/langfuse.sh credentials
```

Langfuse UI 使用 http://localhost:3100，避免与前端 3000 端口冲突。M2/16GB 同时运行
本地 Ollama 与 Langfuse 时内存较紧，压力测试前可执行 `./scripts/langfuse.sh stop`。

### 本地开发

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 运行测试

```bash
python -m pytest tests/ -v
```

## 前端开发

基于 React.js 的前后端分离 Web 前端，提供现代化的交互界面。

```bash
cd binnagent-frontend
npm install
npm run dev
npm run dev:console
npm run test
```

学习端运行在 http://localhost:5175，自动代理 API 请求到后端。Dev Console 运行在
http://localhost:5176，可在 Learners / Recent Episodes 中直接选择 learner 和 episode，并用于 Memory / Episode / Tool / Evidence / Prompt 等内部调试页面。

## 文档索引

### 架构文档

- [Architecture README](docs/architecture/README.md)
- [00. Overview](docs/architecture/00-overview.md)
- [01. Domain & Product](docs/architecture/01-domain-product.md)
- [02. LangGraph Runtime](docs/architecture/02-langgraph-runtime.md)
- [03. Memory System](docs/architecture/03-memory-system.md)
- [04. Multi-agent Collaboration](docs/architecture/04-multi-agent-collaboration.md)
- [05. Learning Tools & MCP](docs/architecture/05-learning-tools-and-mcp.md)
- [06. Data Model](docs/architecture/06-data-model.md)
- [07. Evaluation & Observability](docs/architecture/07-evaluation-observability.md)
- [08. MVP Roadmap](docs/architecture/08-mvp-roadmap.md)
- [09. Model Provider & Ollama](docs/architecture/09-model-provider-and-ollama.md)
- [10. Knowledge Base](docs/architecture/10-knowledge-base.md)
- [11. Vocabulary Learning](docs/architecture/11-vocabulary-learning.md)
- [12. Textbook RAG, Langfuse & Exercises](docs/architecture/12-rag-observability-exercises.md)
- [13. Current Scope and Status](docs/architecture/13-current-scope-and-status.md)
- [14. Expression Lab](docs/architecture/14-expression-lab.md)
- [15. Dynamic Tool Registry, Discovery & Injection](docs/architecture/15-dynamic-tool-registry-discovery-injection.md)
- [16. Reading-led Learning Track](docs/architecture/16-reading-led-learning-track.md)
- [Document Parsing Pipeline](docs/architecture/document-parsing-pipeline.md)
- [LangGraph Runtime Audit](docs/architecture/langgraph-runtime-audit.md)
- [Verification Runtime Audit](docs/architecture/verification-runtime-audit.md)
- [Prompt Execution Audit](docs/architecture/prompt-execution-audit.md)
- [Prompt Execution Governance](docs/architecture/prompt-execution-governance.md)
- [Async Exercise Pool & Worker](docs/architecture/exercise-generation-pool.md)
- [Textbook Parsing Audit](docs/architecture/textbook-parsing-audit.md)
- [Textbook Parsing Quality](docs/architecture/textbook-parsing-quality.md)
- [Textbook Parser Evaluation Audit](docs/architecture/textbook-parser-evaluation-audit.md)
- [Textbook Parser Evaluation](docs/architecture/textbook-parser-evaluation.md)
- [Textbook Parsing Dev Console Audit](docs/architecture/textbook-parsing-dev-console-audit.md)
- [Textbook Review Queue Audit](docs/architecture/textbook-review-queue-audit.md)
- [Simulation / Evaluation Audit](docs/architecture/simulation-evaluation-audit.md)
- [ExploreCapability Recommendation](docs/explore-capability-recommendation.md)
- [Agent Runtime / Harness Interview Brief](docs/interview/agent-runtime-harness.md)
- [Project Interview Bullets](docs/interview/project-bullets.md)
- [Async Exercise Pool Interview Brief](docs/interview/异步练习题池设计.md)
- [Issue Roadmap Status](docs/project/issue-roadmap-status.md)
- [Demo Script](docs/demo/demo-script.md)
- [Cloud Deployment](docs/deployment-cloud.md)
- [Memory Architecture v2](docs/memory-architecture-v2.md)
- [Learner Scope Audit](docs/security/learner_scope_audit.md)
- [Email Login and Invitation Flow](docs/auth-invitation-flow.md)

## 当前实现状态

| 能力 | 状态 |
|------|------|
| Chat / Memory / Dashboard | 部分实现，Memory v2 已落地 Retain / Recall / Reflect、LearningEpisode、LearnerModelMemory、TeachingStrategyMemory；普通学习端只展示学习状态摘要，Memory Center 已移入 Dev Console |
| Reading-led Learning Track | 基础版已实现；学习者可从画像自由切换到个性化阅读主线，Dashboard 会将唯一主动作改为今日阅读；短文按当前水平、兴趣、薄弱点与时间预算生成，并通过泛读、精读、纠错复盘把阅读证据写回 Memory；阅读工作台内置可收缩的上下文助手，可携带当前材料、选句、划词与笔记持续提问 |
| 宠物精灵通知 | 已实现，小冰接管全局 Toast 消息，支持按重要性抢占与配色、重复消息合并、七套统一视觉锚点的高清状态原画、观察/挥手等连续微动作、可调静置动作频率、贴边偷看、记忆变更晶石发光、任务完成庆祝、长耗时陪伴反馈、协作式文案、惯性拖动与跨窗口尺寸位置回收、点击/键盘互动、系统减少动态偏好、功能页首次介绍，以及用户菜单中的精灵设置 |
| 教材 Knowledge Base / RAG / Exercises | 部分实现，作为冷启动知识来源；已支持 split public textbook pack v2、长沙市七年级人教新目标 2024 版上下册公共目录、UnitLearningWorkspace、多教材切换、文档解析/校对、统一 ExerciseItem / ExerciseAttempt 与单元阅读语感材料；2024 上册已接入 333 条本册词汇、349 条小学复现词、10 个单元连续朗读音频和正文第 1-74 印刷页的完整教材活动页题图，Starter Unit 1 另有 186 段精校时间轴；单元题库采用 PostgreSQL 持久化任务与独立 Worker 异步补池，支持六维质量评分、双重门禁和 mastery-aware 选题 |
| Vocabulary Personal Cards / Practice / Spelling / Word Parts | 部分实现，已新增“词根与词缀”探索入口、四工作区学习页、内置词根词缀库、拆词练习、跨设备掌握进度、本地离线降级、morphology 前端展示/降级和知识点配套练习验收；训练中可在学习提示区将单词标记为“太简单（已掌握）”，并显著降低后续训练频率 |
| Writing Phrasebook | 基础版已实现 |
| Expression Lab 英语表达实验室 | 已实现，支持中文表达缺口、英文草稿、好句迁移、词汇/语法目标和群聊学习线索输入；提供十类 schema 驱动内容块、局部重生成、1–3 题动态加练、确认后保存长期资产、会话恢复/删除，以及 Attempt → LearningEvent → Memory → Recommendation 学习闭环；Explore、Dashboard 辅助入口和群聊表达真实复用追踪已接通 |
| 对话内互动 Artifact | 基础版已实现；普通用户用自然语言即可触发互动练习，内部 `binnagent-widget` HTML/CSS/JS 协议不会在生成或回传时暴露；组件运行在隔离 iframe，作答后须确认才会以自然语言消息和隐藏的结构化上下文继续对话；Markdown 图片可升级为选择、全屏查看和局部坐标标注图片板；沙箱禁止网络、存储、父页面访问和未确认业务写入 |
| 群聊学习线索 | 第一版已实现并切到飞书 MCP 兼容方案，支持飞书群来源配置、MCP/OpenAPI 同步、群成员拉取与当前 learner 绑定、原始消息保留/清理、中性 JSON 导入、显式标签即时规则抽取、`@机器人 --help` 群内操作指南回复与去重、无标签消息 pending 队列、低频 LLM 小批量线索提取、最近导入记录、收件箱分页接受/忽略/删除，以及接受后写入词汇候选、好句候选或语法学习进度 |
| ExploreCapability 推荐 | 基础版已实现，Explore Tab 入口由后端 registry 统一管理；Daily Lesson 答题后可推荐 ready 学习能力，点击/忽略事件写入 Memory 和 episode trace |
| Generative Classroom | 已实现可体验版本；每日学习采用数字教材桌面，按当前任务、最低完成证据和下一步组织词汇三档判断、Grammar Lab、教材原声听辨、PDF 原题作答、智能诊断与学习复盘；阶段门槛阻止任意跳关，返回不再误记完成，退出保留 Daily Lesson 并可原位恢复，保存状态显示真实时间；全册 10 个 Grammar Lab 提供明确 can-do 目标、规则归纳、结构模板、易错点、3 道即时辨析和迁移表达；LLM 诊断通过 `PromptExecutor` 对照教材与学生答案生成 schema 约束的最小提示，离线时使用确定性兜底；词汇判断、听辨证据、语法答案、迁移表达、教材答案、Daily Lesson checkpoint、Mastery、Memory、复习计划和 ExploreCapability 推荐保持联动 |
| Frontend UI/UX 统一标准 | Issue #20 首轮整改已落地，普通学习端主导航保留 AI对话 / 探索 / 学习中心，Debug/Memory/Runtime 页面移入 Dev Console；Dashboard 首页提供唯一优先动作；学习目标归并为同步教材、考试备考、通用英语三条产品主线，Explore 按主线推荐并默认隐藏规划中能力；推荐卡显示学习依据、预计时长和完成收益；AI 对话支持显式学习收口、迁移练习与恢复说明；学习设置可编辑学习目标和 CEFR 当前水平，保存失败会回滚界面状态；教材解析治理集中到 Dev Console Textbook Parsing |
| Prompt Registry / Schema-first Import / Parser Quality | 基础治理已实现；PromptExecutor 已统一 text/structured/stream prompt 调用，PromptExecutionRecord、结构化校验记录、Prompt Debug API、prompt eval CLI / eval sets、核心 prompt 迁移、画像驱动 prompt 背景和教材解析质量门禁已落地 |
| Model Provider | 部分实现；本地默认 Ollama，云端可通过环境变量或 Dev Console Debug 页面切换到 DeepSeek / LongCat OpenAI-compatible chat API；RAG embedding 暂时隔离在 Ollama 路径 |
| Agent Runtime / Harness | 第二阶段补强中，TaskSpec、AgentEpisode、LearningEvent、EvidenceRef、ToolCallRecord、VerificationReport、MasteryEngine、RecommendationEngine、LearningGraphCheckpoint 和 Dev Console 调试入口已接入；Tool Catalog 第一阶段支持应用级发现、revision/spec hash、刷新、启停、健康监控、allowlist 解析和 schema/timeout 执行治理，Dev Console 可管理和监控生命周期；真实业务 wrapper 全量迁移与通用 MCP discovery 待完成；VerificationReport 的 critical 失败会阻止静默 completed；Debug API 默认关闭并需 token |
| Learner-scoped isolation | Issue #25 第一阶段已实现，新增 current user / current learner dependency、scoped resource helper，并加固 Runtime、Daily Lesson、Memory、Explore、ExerciseAttempt 和 Debug 高风险路径 |
| 邮箱登录与邀请关系 | 基础版已实现，6 位邮箱验证码、短期签名令牌、重发冷却、错误次数限制、SMTP/本地日志投递、同邮箱多学习者选择、邀请码注册、直接邀请人关系、旧账号邮箱升级和空库 bootstrap 邀请码已落地；正式认证 session 留待远程部署前补齐 |
| LangGraph daily lesson | 已升级为单题 checkpoint / interrupt / resume 学习闭环；graph 支持可选 checkpointer 编译，start 返回 waiting_user checkpoint/thread/schema/prompt，answer 从 `grade_attempt` 恢复并完成 grading、mastery、memory、review、recommend、verification，验证报告决定 completed / completed_with_warnings / verification_failed |
| Learner Simulation Agent | Deterministic MVP 已实现，新增 contract/integration/e2e mode 分层、deterministic fake model provider、scenario contract/module_tags、impacted simulation 推导脚本、Agent Runtime 断言增强、metric_groups、baseline comparison、threshold gate、episode runtime knowledge practice、daily_lesson_checkpoint_resume、capability recommendation、verification failure blocks completed status、缺答案不写 memory、mastery 上下行和 LLM JSON repair 回归场景 |
| CET reading / writing / weekly report | 设计中 |
| CI backend lint/test + frontend lint/test/build/build:console | 已实现 |

## 当前收口结论

核心面试路线已基本完成：Agent Runtime、PromptExecutor、Memory/Mastery、Simulation、Learner Isolation、Parser Quality 和 Dev Console 已形成可讲、可演示、可回归的工程闭环。后续不建议继续重投入教材解析；优先做真实用户体验、UI polish、demo script、部署文档和少量关键路径 e2e。

### 前端文档

- [Web Frontend](docs/web-frontend.md) — React 前端设计与实现
- [Frontend Design System](docs/frontend-design-system.md) — Issue #20/#33 UI/UX 统一标准、用户端入口边界与页面整改清单
- [ExploreCapability Recommendation](docs/explore-capability-recommendation.md) — Explore 学习能力入口、推荐、Memory 和 trace 事件
- [Web Frontend Design Spec](docs/superpowers/specs/2026-06-12-web-frontend-design.md) — 详细设计规范
- [Spelling Training UI/UX](docs/superpowers/specs/2026-06-19-spelling-training-uiux.md) — 拼写训练流程、界面状态与交互规范
- [Unit Reading Fluency Training](docs/superpowers/specs/2026-07-09-unit-reading-fluency.md) — 单元阅读语感训练生成、入口和画像证据规范

### 开发指南

- [AGENTS.md](AGENTS.md) — 开发规范与文档准则

### 其他

- [Research: LangGraph Memory Multi-agent](docs/langgraph-memory-multi-agent-architecture.md)
- [Research: English Learning Companion Agent](docs/english-learning-companion-agent-architecture.md)
- [English Tips](docs/docs/englishtips/)

## 技术栈

| 层级 | 技术 |
|------|------|
| API | FastAPI (Python 3.11+) |
| 编排 | LangGraph |
| 数据库 | PostgreSQL + pgvector + SQLAlchemy |
| LLM | Ollama (gemma4:e2b) |
| 前端 | React 19 + TypeScript + Tailwind CSS v4 |

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| `app` | 8000 | FastAPI 应用 |
| `exercise-worker` | - | 持久化单元题池生成与审题 Worker |
| `db` | 5432 | PostgreSQL |
| `redis` | 6379 | Redis 缓存 |
| `frontend` | 5175 | Learner App React 开发服务器 |
| `dev-console` | 5176 | Agent Runtime / Harness 调试控制台 |
