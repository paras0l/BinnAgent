# BinnAgent

基于 LangGraph 的英语学习陪伴 Agent 系统。优先落地英语四级、六级备考场景，构建能长期陪伴学习者、持续记录错词错因、动态调整计划并形成复习闭环的 AI 英语私教系统。

**核心闭环**：诊断 → 计划 → 训练 → 反馈 → 复习 → 复盘 → 记忆更新 → 下一次训练

## 快速开始

### 一键启动开发环境

```bash
./scripts/dev.sh
```

脚本会启动 Docker 服务（PostgreSQL、Redis、后端 API）、执行数据库迁移，并启动前端开发服务器。
默认会同时启动 Learner App 和 Dev Console；Dev Console 本地 token 默认为 `dev`。

- 后端 API：http://localhost:8000/docs
- 学习端页面：http://localhost:5173
- Dev Console：http://localhost:5174

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

学习端运行在 http://localhost:5173，自动代理 API 请求到后端。Dev Console 运行在
http://localhost:5174，可在 Learners / Recent Episodes 中直接选择 learner 和 episode，并用于 Memory / Episode / Tool / Evidence / Prompt 等内部调试页面。

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
- [LangGraph Runtime Audit](docs/architecture/langgraph-runtime-audit.md)
- [Verification Runtime Audit](docs/architecture/verification-runtime-audit.md)
- [Prompt Execution Audit](docs/architecture/prompt-execution-audit.md)
- [Prompt Execution Governance](docs/architecture/prompt-execution-governance.md)
- [Textbook Parsing Audit](docs/architecture/textbook-parsing-audit.md)
- [Textbook Parsing Quality](docs/architecture/textbook-parsing-quality.md)
- [Textbook Parser Evaluation Audit](docs/architecture/textbook-parser-evaluation-audit.md)
- [Textbook Parser Evaluation](docs/architecture/textbook-parser-evaluation.md)
- [Textbook Parsing Dev Console Audit](docs/architecture/textbook-parsing-dev-console-audit.md)
- [Textbook Review Queue Audit](docs/architecture/textbook-review-queue-audit.md)
- [Simulation / Evaluation Audit](docs/architecture/simulation-evaluation-audit.md)
- [ExploreCapability Recommendation](docs/explore-capability-recommendation.md)
- [Agent Runtime / Harness Interview Brief](docs/interview/agent-runtime-harness.md)
- [Memory Architecture v2](docs/memory-architecture-v2.md)
- [Learner Scope Audit](docs/security/learner_scope_audit.md)

## 当前实现状态

| 能力 | 状态 |
|------|------|
| Chat / Memory / Dashboard | 部分实现，Memory v2 已落地 Retain / Recall / Reflect、LearningEpisode、LearnerModelMemory、TeachingStrategyMemory；普通学习端只展示学习状态摘要，Memory Center 已移入 Dev Console |
| 教材 Knowledge Base / RAG / Exercises | 部分实现，已支持多教材切换、七年级上/下册解析、八/九年级上传 fallback、ParserRun 审计、ParserQualityReport 指标、ParserReviewItem 队列、TextbookQualityScore 门禁、Golden Dataset + Parser Evaluation MVP、Parser Evidence 查询、Dev Console Textbook Parsing Report、低置信词条人工校对入口、统一 ExerciseItem / ExerciseAttempt 语义和 AI 生成练习可编辑保存 |
| Vocabulary Personal Cards / Practice / Spelling / Word Parts | 部分实现，已新增“词根与词缀”探索入口、四工作区学习页、内置词根词缀库、拆词练习、morphology 前端展示/降级和知识点配套练习验收 |
| Writing Phrasebook | 基础版已实现 |
| ExploreCapability 推荐 | 基础版已实现，Explore Tab 入口由后端 registry 统一管理；Daily Lesson 答题后可推荐 ready 学习能力，点击/忽略事件写入 Memory 和 episode trace |
| Frontend UI/UX 统一标准 | Issue #20 首轮整改已落地，普通学习端主导航保留 AI对话 / 探索 / 学习中心，Debug/Memory/Runtime 页面移入 Dev Console；KnowledgeBase 已升级为教材解析校对工作台 |
| Prompt Registry / Schema-first Import / Parser Quality | 基础治理已实现；PromptExecutor 第一阶段、PromptExecutionRecord、结构化校验记录、writing_phrase.import 迁移和教材解析质量门禁已落地 |
| Agent Runtime / Harness | 第二阶段补强中，TaskSpec、AgentEpisode、LearningEvent、EvidenceRef、ToolCallRecord、VerificationReport、MasteryEngine、RecommendationEngine、LearningGraphCheckpoint 和 Dev Console 调试入口已接入；VerificationReport 已升级为 evidence-based deterministic/schema/business_rule/evidence checks，critical 失败会阻止静默 completed；EpisodeTraceView、Graph Runs 和 Textbook Parsing Report 可查看 checkpoint、events、tool calls、prompt execution summary、verification checks、parser evidence 和 review queue；Debug API 默认关闭并需 token |
| Learner-scoped isolation | Issue #25 第一阶段已实现，新增 current user / current learner dependency、scoped resource helper，并加固 Runtime、Daily Lesson、Memory、Explore、ExerciseAttempt 和 Debug 高风险路径 |
| LangGraph daily lesson | 已升级为单题 checkpoint / interrupt / resume 学习闭环；graph 支持可选 checkpointer 编译，start 返回 waiting_user checkpoint/thread/schema/prompt，answer 从 `grade_attempt` 恢复并完成 grading、mastery、memory、review、recommend、verification，验证报告决定 completed / completed_with_warnings / verification_failed |
| Learner Simulation Agent | Deterministic MVP 已实现，新增 scenario contract/module_tags、impacted simulation 推导脚本、Agent Runtime 断言增强、metric_groups、baseline comparison、threshold gate、episode runtime knowledge practice、daily_lesson_checkpoint_resume、capability recommendation、verification failure blocks completed status、缺答案不写 memory 和 mastery 上下行回归场景 |
| CET reading / writing / weekly report | 设计中 |
| CI backend lint/test + frontend lint/test/build/build:console | 已实现 |

### 前端文档

- [Web Frontend](docs/web-frontend.md) — React 前端设计与实现
- [Frontend Design System](docs/frontend-design-system.md) — Issue #20 UI/UX 统一标准与页面整改清单
- [ExploreCapability Recommendation](docs/explore-capability-recommendation.md) — Explore 学习能力入口、推荐、Memory 和 trace 事件
- [Web Frontend Design Spec](docs/superpowers/specs/2026-06-12-web-frontend-design.md) — 详细设计规范
- [Spelling Training UI/UX](docs/superpowers/specs/2026-06-19-spelling-training-uiux.md) — 拼写训练流程、界面状态与交互规范

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
| `db` | 5432 | PostgreSQL |
| `redis` | 6379 | Redis 缓存 |
| `frontend` | 5173 | Learner App React 开发服务器 |
| `dev-console` | 5174 | Agent Runtime / Harness 调试控制台 |
