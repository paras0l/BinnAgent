# Frontend Design System

> 适用范围：BinnAgent React 前端的核心学习页面。目标是保持低噪音、重引导、重练习闭环的学习产品体验。

## Issue #20 UI/UX Direction

BinnAgent 的统一方向是“功能优先的英语学习工作台”。统一不等于所有页面长一样，而是所有页面都遵循同一套外壳、组件、状态反馈、推荐原因和证据表达。

主导航固定为：

```text
AI对话 / 探索 / 学习中心 / 记忆
```

新增功能只能归入这四个入口体系，不再新增一级导航。好句收藏馆只是一个可借鉴的较好实现，不作为全局页面模板。

Issue #20 覆盖页面清单：

```text
0. AppShell / Header / 全局布局
1. ChatPage / ChatContainer
2. ExplorePage
3. DashboardPage
4. MemoryCenterPage
5. WritingPhrasebookPage
6. GrammarPage
7. VocabularyDetailPage
8. PronunciationPage
9. KnowledgeBasePage
10. VocabularyPracticePage
11. Dashboard 内部 VocabularyWorkspace
12. LoginPage
```

所有页面整改必须满足：

- 标准功能页使用 `PageShell` 和 `FeatureHero`。
- 普通卡片使用 `SurfaceCard` 或派生组件。
- 复杂功能拆成 `WorkspaceTabs` 或同等工作区。
- 学习推荐必须展示原因，优先使用 `ReasonCard`。
- 证据、来源、解析状态优先使用 `EvidencePanel` 或同等结构。
- `KnowledgeBasePage` 必须保持真实教材工作台：四个工作区为教材结构、单元学习、练习任务、解析校对；解析校对必须展示 `requires_review`、warnings、parser/ingest 证据、来源页码和低置信词条确认入口。
- 删除、清空、否认长期记忆必须使用 `ConfirmDialog` 或同等二次确认。
- 空状态必须给出下一步动作。
- AI 或外部模型生成内容保存前必须可确认、可编辑、可追溯。

## PageShell

核心学习页面统一使用浅灰工作区背景和居中内容宽度：

- 外层背景：`bg-[#f6f7f9]`
- 页面宽度：`max-w-[1180px]`
- 页面间距：`px-4 py-6 sm:px-6 lg:px-8`
- 区块间距：`gap-5`
- `variant="standard"`：默认 1180px。
- `variant="full"`：只允许 Chat、KnowledgeBase 等复杂工作台按需使用。

组件位置：

```text
binnagent-frontend/src/components/layout/PageShell.tsx
```

## FeatureHero

学习功能页首屏使用 Hero 说明当前能力、下一步行动和关键数据。

- 标题：`text-3xl font-black tracking-tight text-slate-950`
- 说明：`text-sm leading-6 text-slate-500`
- 统计：总量、待复习、收藏、归档等学习资产状态
- 主按钮：只放 1-2 个关键操作

组件位置：

```text
binnagent-frontend/src/components/layout/FeatureHero.tsx
```

## Workspace Tabs

复杂功能拆成工作区，不把所有工具常驻在同一列。

推荐工作区：

- 浏览/收藏
- 导入/生成
- 练习/检测
- 调用/输出

组件位置：

```text
binnagent-frontend/src/components/layout/WorkspaceTabs.tsx
```

## Surface Card

卡片是学习页面的主要承载单元。

标准样式：

```text
rounded-[13px]
border border-slate-200
bg-white
p-5
shadow-[0_4px_14px_rgba(15,23,42,0.05)]
```

组件位置：

```text
binnagent-frontend/src/components/ui/SurfaceCard.tsx
```

## Buttons

按钮分为三层：

- Primary：保存、确认收藏、开始练习等主行动，使用 `bg-primary text-primary-foreground`。
- Secondary：复制 Prompt、新增、编辑等次行动，使用白底边框。
- Ghost/Icon：收藏、归档、关闭等轻操作，使用图标按钮和 hover 状态。

删除类操作必须使用 danger hover，例如 `hover:text-error`。

每个页面最多一个最强主操作。若主操作超过两个，页面应拆分工作区。

组件位置：

```text
binnagent-frontend/src/components/ui/Button.tsx
binnagent-frontend/src/components/ui/IconButton.tsx
```

## Tags And Chips

筛选标签和内容标签需要区分：

- 筛选 chip：可点击，使用 `rounded-full`，有 active state。
- 内容 tag：只读，使用弱背景和 `rounded-md`。

组件位置：

```text
binnagent-frontend/src/components/ui/FilterChip.tsx
```

## Forms

表单默认按任务分组，不使用一长串裸字段。

推荐分组：

- 基础信息
- 使用说明
- 例句与标签
- 复习设置

字段标准：

- label：`text-sm font-medium text-slate-950`
- input：`rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm`
- textarea：`min-h-24 leading-6`
- focus：`focus:border-primary`

组件位置：

```text
binnagent-frontend/src/components/ui/FormField.tsx
```

## State Components

异步页面必须统一展示加载、错误和空状态：

- `LoadingState`：说明正在加载什么。
- `ErrorState`：说明失败影响，并提供重试或替代入口。
- `EmptyState`：说明为什么为空，并给出下一步动作。
- `StatusBanner`：用于 Skill 启用、生成中、记忆已加载、低置信提醒等状态。

组件位置：

```text
binnagent-frontend/src/components/ui/LoadingState.tsx
binnagent-frontend/src/components/ui/ErrorState.tsx
binnagent-frontend/src/components/ui/EmptyState.tsx
binnagent-frontend/src/components/ui/StatusBanner.tsx
```

## Explainability

任何学习推荐都必须回答：

```text
为什么推荐？
依据是什么？
完成后会改善什么？
用户能否否认或调整？
```

统一使用：

```text
binnagent-frontend/src/components/learning/ReasonCard.tsx
binnagent-frontend/src/components/learning/EvidencePanel.tsx
```

## Task Pages

沉浸任务页适用于词汇练习、拼写练习、教材题目流、口语跟读和听力精听。正式练习阶段必须是一屏一任务，核心操作始终可见。

推荐结构：

```text
TaskShell
  TaskTopBar：返回、进度、当前模式
  MainTaskArea：当前题目 / 当前词 / 当前音频 / 反馈
  SupportArea：提示、来源、编辑、解释性辅助操作
  ActionBar：提示、提交、评分、重试、下一题
```

实现约束：

- `TaskShell` 使用 `h-dvh` 和 `overflow-hidden`，避免正式练习阶段出现页面级上下滚动。
- `TaskTopBar` 和 `ActionBar` 使用 `shrink-0` 固定占位。
- `MainTaskArea` 使用 `min-h-0 flex-1 overflow-y-auto`，长内容只能在中间区域内部滚动。
- 任务页必须按功能区组织：主任务区只放当前题目、作答和反馈；辅助区放提示、来源、编辑词卡、查看证据等次要操作；底部操作区只放关键推进动作。
- 底部操作区只允许放评分、检查、提交、重试、下一题、结束/返回这类关键动作。提示、编辑、来源、说明、证据、设置等辅助操作不得挤占底部操作区。
- setup、summary、长表单可以页面滚动；practice 阶段不能让用户滚动页面才能看到操作按钮。
- 空间不足时，优先压缩说明文案、降低垂直间距、折叠次要信息，而不是把操作栏推到视口外。
- 不要把设计原则、布局解释或内部标准文案显示给用户，例如“底部操作区只放关键动作”“辅助操作集中在这里”。这些内容只写进文档、注释或评审标准，界面只保留对学习任务有直接帮助的文案。

验收标准：

- 13 英寸笔记本和常见移动端视口下，底部操作栏首屏可见。
- `显示答案`、评分按钮、`检查拼写`、`提示`、`下一个` 等关键操作不依赖页面滚动。
- 动态反馈出现后，下一步操作仍然可见。
- 顶部进度和底部操作不随中间内容滚走。
- 用户界面不出现解释设计系统或布局规则的说明文字。

## Empty States

空状态必须包含下一步动作。

示例：

```text
还没有收藏句式
可以先创建示例，或从外部模型导入一组分层递进表达。
[创建示例] [导入好句]
```

## Writing Phrasebook Reference

好句收藏馆是当前标准的首个落地页面：

- 使用 `PageShell`、`FeatureHero`、`WorkspaceTabs`、`SurfaceCard`、`FilterChip`。
- 从三栏常驻布局改为 Hero + Tabs + 双栏工作区。
- 默认展示阅读态，编辑通过 drawer 打开。
- Prompt 回填与练习检测迁移到独立工作区。
