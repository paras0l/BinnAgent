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
- `ExplorePage`: 学习能力探索、入口偏好和能力推荐。
- `DashboardPage`: 今日复习、学习目标、错因和学习统计。
- `PronunciationPage`: 发音练习。
- `GrammarPage`: 语法主题和缓存内容。
- `KnowledgeBasePage`: 学习者教材入口、教材切换、今日单元、练习任务和课程/练习弹窗；解析治理移入 Dev Console。
- `VocabularyPracticePage`: 单元词汇、review/spelling practice、富词典详情。
- `VocabularyDetailPage`: 词汇详情页面。
- `WordPartsPage`: 词根词缀方法入门、内置库、拆词练习和本地掌握记录。
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

Issue #20 / #33 已把前端方向收敛为“功能优先的英语学习工作台”，用户端主导航固定为：

```text
AI对话 / 探索 / 学习中心
```

`记忆` 不再作为普通用户端一级 tab。Memory、raw memory、EpisodeTrace、PromptExecution、ToolCall、VerificationReport 等调试对象进入 Dev Console；用户端在学习中心内展示“学习记录”和“学习者画像”。

本轮已完成的统一整改：

- 新增统一基础组件：`Button`、`IconButton`、`FormField`、`StatusBanner`、`LoadingState`、`ErrorState`、`EmptyState`、`ConfirmDialog`、`ReasonCard`、`EvidencePanel`。
- `PageShell` 支持 `standard/full` 变体，标准宽度统一为 `max-w-[1180px]`。
- `DashboardPage` 从数据面板升级为今日学习入口页：`FeatureHero`、今日主推荐、复习队列、继续学习、学习记录、学习者画像和推荐原因；画像页包含能力雷达、掌握度分布和薄弱点排行，记录页包含活动热力、每日完成趋势、正确率/复习负荷趋势；词汇工作区已补统一练习入口卡、词汇搜索/新增表单状态和可键盘访问的词汇行，Dashboard 共享统计卡、学习目标进度条和词汇复习卡已清理伪按钮与 `transition-all`。
- `ExplorePage` 改为学习能力工作台：优先展示后端 ExploreCapability 推荐，保留固定入口、收藏、搜索和分类筛选；搜索框已补可访问属性和 focus-visible，能力卡与收藏按钮已补基础 hover/focus/disabled 状态。
- `ChatContainer` 的 Skill 状态使用 `StatusBanner`；顶部操作、历史侧栏、记忆面板、欢迎入口和发送/停止操作已接入统一 `Button` / `IconButton`，聊天输入补齐 `name` / `autocomplete` / focus-visible，streaming/typing 使用 `aria-live` 并尊重 reduced-motion。
- Header 右侧改为学习者菜单，包含学习设置、当前学习者摘要和登出/切换学习者；裸退出 icon 不再常驻导航。
- 新增 learner-scoped 本地学习设置，覆盖词汇练习默认模式、数量、英/美音、是否显示 setup、自动播放、拼写填满自动检查、答对后自动进入下一题和单元词汇范围。
- `MemoryCenterPage` 不在用户端主导航出现；Dev Console 可继续复用它查看和管理 memory/debug evidence。
- `GrammarPage`、`PronunciationPage`、`VocabularyDetailPage`、`LoginPage` 接入统一外壳和表单/按钮标准；`LoginPage` 登录字段已补 `name` / `autocomplete` / `spellCheck`，产品能力卡已有 hover elevation/translate。
- `VocabularyDetailPage` 已补生成-回填-保存四步 stepper，生成指令、HTML 回填、个人词卡和构词笔记表单已统一 `name` / `autocomplete` / focus-visible 与省略号占位文案。
- `GrammarPage` 已补知识点分类矩阵、已打开/已学习/已缓存/喜爱状态卡、难度掌握分布和生成链路状态卡；重新生成、清空 HTML、删除目标网站使用确认弹窗。
- `KnowledgeBasePage` 保留全宽教材学习页，并拆成“今日单元 / 练习任务”两个学习者 workspace；左侧支持多本教材切换，右侧只展示教材信息、学习路径和推荐理由，移动端可展开/收起教材目录和学习概览。主学习区已补教材学习概览图表，覆盖教材单元、知识点、RAG 片段、待校对、单元掌握、知识点类型、教材路径和解析索引覆盖。解析校对、解析质量、教材结构内部产物、parser/ingest 证据和调试表格统一放入 Dev Console 的 Textbook Parsing。
- 共享练习组件 `AddExerciseForm` / `ExerciseRenderer` 已补练习表单 `name` / `autocomplete` / focus-visible、选项 pressed/focus 状态、提交与生成 loading 文案、练习进度条；`ExerciseSessionDialog` 改为固定高度弹层和内部滚动，让教材练习入口更接近 TaskShell。
- `DailyLessonRuntimeDialog` 已改为固定头部、内部滚动内容和固定底部 ActionBar，选项补 pressed/focus 状态，提交按钮有 loading 文案，并支持 ESC 关闭和焦点恢复。
- `VocabularyPracticePage` 保持沉浸式一屏一任务，并在顶部明确模式和来源；练习阶段按主任务区、学习辅助区和底部操作区组织，底部操作栏固定可见，中间内容内部滚动，避免用户上下翻动才能评分或进入下一题；核心按钮、进度条和拼写输入已补 `type` / focus-visible / `name` / `autocomplete` 与显式 transition。
- `WordPartsPage` 按“方法入门 / 词根词缀库 / 拆词练习 / 我的掌握”四个 workspace 组织，复用 `PageShell`、`FeatureHero`、`WorkspaceTabs`、`SurfaceCard`、`FilterChip` 和统一 `Button`。
- `WordPartsPage` 的“我的掌握”已补整体掌握堆叠条、prefix/root/suffix 掌握条和练习次数趋势；重置本地记录使用确认弹窗。
- `ReadingWorkshopPage` 的材料历史和精读句子列表已支持移动端折叠；复盘页已补关键词频次条、句子难度热力图和语法卡点分布，泛读/精读沉淀可图形化回看。
- `WritingPhrasebookPage` 继续作为专项资产库页面，保留 `PageShell`、`FeatureHero`、`WorkspaceTabs` 的既有较好实现；主操作、详情操作、导入操作、练习推进和编辑抽屉关键按钮已接入统一 `Button` / `IconButton`，练习页补充进度条、题型分布、已填写统计和移动端句式列表折叠，编辑抽屉表单已补基础可访问属性。
- `PronunciationPage` 的 Minimal Pairs / Records 已从占位页升级为可用工作区，支持易混音组练习、本地自评记录、音标完成度、shadowing 自评分布和最小对立音清晰率图表；Shadowing 工作区已补移动端句子列表折叠、原句播放状态、节奏条和重音词可视化。
- Dev Console 的 `EpisodeDebugPage` 已补 Graph Run Overview、Node Waterfall、Event Rhythm、Tool Latency 和 Verification Map，Graph Runs 可先通过图形化链路扫读，再下钻表格/JSON。

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
| ExploreCapability | `/api/explore/capabilities`, `/api/learners/{id}/explore/recommendations`, `/api/learners/{id}/explore/capabilities/{capability_id}/events` | 基础版已实现 |
| Vocabulary Practice | `/api/learners/{id}/vocabulary-learning/*` | 部分实现 |
| 发音 | `/api/learners/{id}/pronunciation/*` | 部分实现 |
| 语法缓存 | `/api/grammar/topics/{topic_id}/html-cache` | 已实现 |

## 已实现

- 多页面路由和 learner 登录流。
- Chat SSE 流式回复、取消、自动继续和会话侧边栏。
- Memory 面板和 Dashboard 学习状态。
- 多教材知识库课程路径、知识点、练习入口和教材切换。
- Explore 学习能力列表、偏好、推荐卡片和点击/忽略事件。
- 单元词汇练习、拼写反馈、富词典详情。
- 词根词缀学习入口、内置词根词缀库、拆词练习、localStorage 掌握标记和 vocabulary morphology 展示/优雅降级。
- Toast 通知系统。
- Issue #20 UI/UX 统一标准基础组件和 0-12 页面首轮整改。

## 待增强

- 全局“今日学习路径”：串联教材、词汇、聊天练习和复习任务。
- 练习进度保存与恢复提示。
- 空状态中的明确下一步引导。
- Dashboard 区分“今日待复习”“今日新学”“最近薄弱点”。
- Chat 与 Agent Skill / 词汇练习之间的跳转闭环。
- RAG 调试模式显示检索模式、chunk、页码和证据。
- morphology 后端持久化、AI HTML 构词区域解析入库、LearningProgress / Memory 联动。

## 快速开始

```bash
cd binnagent-frontend
npm install
npm run dev
```

生产构建和验证：

```bash
npm run test
npm run lint
npm run build
```

前端默认运行在 http://localhost:3000，并通过 Vite proxy 访问后端 `/api`。

## 设计规范

- 主规范：[Web Frontend Design Spec](superpowers/specs/2026-06-12-web-frontend-design.md)
- 项目级设计标准：[Frontend Design System](frontend-design-system.md)
- 拼写训练规范：[Spelling Training UI/UX](superpowers/specs/2026-06-19-spelling-training-uiux.md)
- 富词典规范：[Vocabulary Rich Dictionary Design](superpowers/specs/2026-06-21-vocabulary-rich-dictionary-design.md)
