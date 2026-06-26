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
- 拼写训练规范：[Spelling Training UI/UX](superpowers/specs/2026-06-19-spelling-training-uiux.md)
- 富词典规范：[Vocabulary Rich Dictionary Design](superpowers/specs/2026-06-21-vocabulary-rich-dictionary-design.md)
