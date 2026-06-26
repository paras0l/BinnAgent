# Frontend Design System

> 适用范围：BinnAgent React 前端的核心学习页面。目标是保持低噪音、重引导、重练习闭环的学习产品体验。

## PageShell

核心学习页面统一使用浅灰工作区背景和居中内容宽度：

- 外层背景：`bg-[#f6f7f9]`
- 页面宽度：`max-w-[1180px]`
- 页面间距：`px-4 py-6 sm:px-6 lg:px-8`
- 区块间距：`gap-5`

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
