# BinnAgent Web Frontend

BinnAgent 前端是 `binnagent-frontend/` 下的 React 19 + TypeScript + Vite 单页应用，用于承载聊天、学习路径、词汇练习、教材知识库、发音、语法和 Dashboard 等学习入口。

## 当前技术栈

| 层级 | 当前实现 |
|---|---|
| 构建工具 | Vite 8 |
| UI 框架 | React 19 |
| 开发语言 | TypeScript 6 |
| CSS | Tailwind CSS v4 |
| 路由 | React Router v7 |
| 服务端状态 | TanStack Query |
| 客户端状态 | Zustand |
| HTTP 客户端 | ky |
| 图标 | lucide-react |

当前项目未引入 shadcn/ui 或 Radix 组件库；如后续引入，应先更新依赖和本文档。

## 当前页面结构

前端不再是早期“两 Tab”原型。`src/App.tsx` 已经组织为多页面入口：

- `ChatPage`: 对话练习、技能聚焦、SSE 流式回复、会话侧边栏、记忆面板。
- `ExplorePage`: 功能探索和入口偏好。
- `DashboardPage`: 今日复习、学习目标、错因和学习统计。
- `PronunciationPage`: 发音练习。
- `GrammarPage`: 语法主题和缓存内容。
- `KnowledgeBasePage`: 七年级教材知识库、课程路径、课程/练习弹窗。
- `VocabularyPracticePage`: 单元词汇、review/spelling practice、富词典详情。
- `VocabularyDetailPage`: 词汇详情页面。
- `LoginPage`: learner 创建、登录和切换。

## 任务页体验标准

`VocabularyPracticePage`、教材练习流、口语跟读、听力精听等沉浸任务页必须是一屏一任务体验。正式练习阶段不允许把提交、提示、评分、重试或下一题按钮放到需要页面滚动才能看到的位置。

实现约束：

- 外层使用固定视口高度，例如 `h-dvh`，并避免页面级滚动。
- 顶部进度区和底部操作区固定占位。
- 中间题目/反馈内容使用 `min-h-0 flex-1 overflow-y-auto` 内部滚动。
- 正式练习阶段按功能区组织：主任务区负责当前题目、作答和反馈；辅助区负责提示、来源、编辑、证据等次操作；底部操作区只放评分、检查、提交、重试、下一题、结束/返回等关键推进动作。
- 底部操作区不能放提示、编辑、来源、设置、证据等辅助操作。
- setup 和 summary 可以页面滚动；practice 阶段必须保证底部 ActionBar 首屏可见。
- 界面不得展示设计原则、布局解释或内部标准文案。类似“底部操作区只放关键动作”“辅助操作集中在这里”的说明只能写在文档中，不能出现在用户界面。

这条优先级高于展示更多说明文案。若空间不足，应压缩说明、折叠次要信息或让内容区内部滚动，而不是牺牲操作可见性。

## UI/UX 统一标准状态

Issue #20 已把前端方向收敛为“功能优先的英语学习工作台”，主导航固定为：

```text
AI对话 / 探索 / 学习中心 / 记忆
```

本轮已完成的统一整改：

- 新增统一基础组件：`Button`、`IconButton`、`FormField`、`StatusBanner`、`LoadingState`、`ErrorState`、`EmptyState`、`ConfirmDialog`、`ReasonCard`、`EvidencePanel`。
- `PageShell` 支持 `standard/full` 变体，标准宽度统一为 `max-w-[1180px]`。
- `DashboardPage` 从数据面板升级为今日学习驾驶舱：`FeatureHero`、今日主推荐、复习队列、继续学习、能力状态和推荐原因。
- `ExplorePage` 改为专项技能工具箱：推荐工具使用 `ReasonCard`，分类筛选使用 `FilterChip`。
- `ChatContainer` 的 Skill 状态使用 `StatusBanner`。
- `MemoryCenterPage` 使用 `FeatureHero`、`ReasonCard`、`EvidencePanel` 和 `ConfirmDialog` 表达可解释、可控制记忆。
- `GrammarPage`、`PronunciationPage`、`VocabularyDetailPage`、`LoginPage` 接入统一外壳和表单/按钮标准。
- `KnowledgeBasePage` 明确保留全宽教材工作台，统一展示教材结构、单元学习、练习任务和解析证据职责。
- `VocabularyPracticePage` 保持沉浸式一屏一任务，并在顶部明确模式和来源；练习阶段按主任务区、学习辅助区和底部操作区组织，底部操作栏固定可见，中间内容内部滚动，避免用户上下翻动才能评分或进入下一题。
- `WritingPhrasebookPage` 继续作为专项资产库页面，保留 `PageShell`、`FeatureHero`、`WorkspaceTabs` 的既有较好实现，但不作为全局模板。

## 当前目录结构

```text
binnagent-frontend/
├── index.html
├── package.json
├── vite.config.ts
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── index.css
│   ├── types.ts
│   ├── data/
│   ├── hooks/
│   ├── pages/
│   └── components/
│       ├── chat/
│       ├── dashboard/
│       ├── feature/
│       ├── knowledge/
│       ├── layout/
│       ├── ui/
│       └── vocabulary/
└── public/
```

## API 集成状态

| 能力 | 主要端点 | 状态 |
|---|---|---|
| Learner 登录/创建 | `/api/learners`, `/api/learners/login` | 已实现 |
| Chat | `/api/chat/send`, `/api/chat/stream` | 已实现 |
| 会话历史 | `/api/conversations` | 已实现 |
| Memory 摘要 | `/api/learners/{id}/memory/summary` | 已实现 |
| Dashboard | `/api/learners/{id}/dashboard` | 已实现 |
| Knowledge Base | `/api/learners/{id}/knowledge-base` | 部分实现 |
| 教材上传/ingest/search | `/api/knowledge/*` | 部分实现 |
| Vocabulary Practice | `/api/learners/{id}/vocabulary-learning/*` | 部分实现 |
| 发音 | `/api/learners/{id}/pronunciation/*` | 部分实现 |
| 语法缓存 | `/api/grammar/topics/{topic_id}/html-cache` | 已实现 |

## 已实现

- 多页面路由和 learner 登录流。
- Chat SSE 流式回复、取消、自动继续和会话侧边栏。
- Memory 面板和 Dashboard 学习状态。
- 七年级教材知识库课程路径、知识点、练习入口。
- 单元词汇练习、拼写反馈、富词典详情。
- Toast 通知系统。
- Issue #20 UI/UX 统一标准基础组件和 0-12 页面首轮整改。

## 待增强

- 全局“今日学习路径”：串联教材、词汇、聊天练习和复习任务。
- 练习进度保存与恢复提示。
- 空状态中的明确下一步引导。
- Dashboard 区分“今日待复习”“今日新学”“最近薄弱点”。
- Chat 与 Skill/词汇练习之间的跳转闭环。
- RAG 调试模式显示检索模式、chunk、页码和证据。

## 快速开始

```bash
cd binnagent-frontend
npm install
npm run dev
```

生产构建和验证：

```bash
npm run lint
npm run build
```

前端默认运行在 http://localhost:3000，并通过 Vite proxy 访问后端 `/api`。

## 设计规范

- 主规范：[Web Frontend Design Spec](superpowers/specs/2026-06-12-web-frontend-design.md)
- 项目级设计标准：[Frontend Design System](frontend-design-system.md)
- 拼写训练规范：[Spelling Training UI/UX](superpowers/specs/2026-06-19-spelling-training-uiux.md)
- 富词典规范：[Vocabulary Rich Dictionary Design](superpowers/specs/2026-06-21-vocabulary-rich-dictionary-design.md)
