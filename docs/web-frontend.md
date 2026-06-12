# BinnAgent Web Frontend

> 漂亮的网页也是可以增加学习动力的 — Beautiful UI increases learning motivation

基于 React.js 的前后端分离 Web 前端，为 BinnAgent 英语学习 AI 伙伴提供现代化的交互界面。

## 设计理念

**活泼教育风 (Lively Educational Style)**：明亮、活泼、易于上手 — 类似 Duolingo 的风格，但专注于英语对话练习。不是游戏化的，而是视觉上令人愉悦和有吸引力的。

**核心理念**：美观的界面能够显著提升学习者的使用意愿和学习动力。

## 技术栈

| 层级 | 技术选择 | 说明 |
|------|---------|------|
| 构建工具 | Vite 6 | 快速 HMR，原生 ESM |
| UI 框架 | React 19 | 最新稳定版，并发特性 |
| 开发语言 | TypeScript (strict) | 类型安全 |
| CSS 框架 | Tailwind CSS v4 | CSS-first 配置，`@theme` tokens |
| 组件库 | shadcn/ui (Radix) | 可复制粘贴，可访问，可定制 |
| 路由 | React Router v7 | 简单 Tab 路由 |
| 服务端状态 | TanStack Query | 缓存，开发工具 |
| 客户端状态 | Zustand | 轻量级 learner 状态管理 |
| 图标 | Lucide React | shadcn 标配 |

## 布局设计

### 顶部导航栏
```
+--------------------------------------------------+
|  [Logo] BinnAgent    [AI对话]  [学习中心]        |
+--------------------------------------------------+
|                                                    |
|           (Tab 内容区域 - 全宽)                     |
|                                                    |
+--------------------------------------------------+
```

- **固定顶部导航栏**：包含 Logo + 两个 Tab
- **Tab 切换**：点击 Tab 切换内容，无需 URL 变化
- **选中 Tab**：主色高亮 + 下划线指示器
- **内容区域**：全宽，可滚动

### Tab 1: AI 对话 (AI Chat)

#### 布局
```
+--------------------------------------------------+
|  消息区域 (可滚动，自动滚动)                      |
|  ┌─────────────────────────────────────────────┐  |
|  │  [AI 头像] Hello! Let's practice...         │  |
|  └─────────────────────────────────────────────┘  |
|                                                    |
|  ┌─────────────────────────────────────────────┐  |
|  │  Hi! I want to learn about travel vocab...  │  │
|  └─────────────────────────────────────────────┘  |
|  [用户头像]                                        |
|                                                    |
+--------------------------------------------------+
|  [输入框: 输入你想练习的内容...]    [发送] [停止]  |
+--------------------------------------------------+
```

#### 组件

**MessageBubble**
- 用户消息：靛蓝背景 (#6366F1)，白色文字，右对齐
- AI 消息：浅灰背景 (#F1F5F9)，深色文字，左对齐
- 圆角 (16px)，微阴影
- 时间戳在消息下方 (10px，muted)
- 打字指示器：AI 生成时显示 3 个跳动的点

**ChatInput**
- 固定在聊天区域底部
- 圆角输入框，placeholder "输入你想练习的内容..."
- 有文字时显示发送按钮（靛蓝）
- 流式响应时显示停止按钮（红色）
- 快捷键：Enter 发送，Shift+Enter 换行

**WelcomeScreen**
- 无消息时显示
- 友好的问候语和 AI 头像
- 快速开始按钮："开始一节对话课"、"复习今天词汇"、"练习口语场景"

### Tab 2: 学习中心 (Learning Center)

#### 布局
```
+--------------------------------------------------+
|  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ |
|  │ 今日复习 │ │ 连续天数 │ │  正确率  │ │总词汇量│ |
|  │    12    │ │    5🔥   │ │   85%    │ │  156   │ |
|  └──────────┘ └──────────┘ └──────────┘ └────────┘ |
|                                                    |
|  +-----------------------------------------------+ |
|  |  词汇复习 (SRS 卡片)                          | |
|  |  ┌─────────────────────────────────────────┐  | |
|  │  │  [翻转卡片]                              │  | |
|  │  │  正面: "abundant"                        │  | |
|  │  │  背面:  丰富的 / plenty of               │  | |
|  │  │  [忘记] [模糊] [记住] [熟练]             │  | |
|  │  └─────────────────────────────────────────┘  | |
|  +-----------------------------------------------+ |
|                                                    |
|  +-----------------------------------------------+ |
|  |  错误模式分析                                 | |
|  |  • 时态混淆 (3次) - She go → She goes        | |
|  |  • 冠词缺失 (2次) - I want book → I want a.. | |
|  +-----------------------------------------------+ |
|                                                    |
|  +-----------------------------------------------+ |
|  |  学习目标                                     | |
|  |  今日目标: ████████░░ 80% (完成8/10)         | |
|  |  本周目标: █████░░░░░ 50% (完成5/10)         | |
|  +-----------------------------------------------+ |
+--------------------------------------------------+
```

#### 组件

**StatsCards** (4 个卡片横排)
1. **今日复习**：今日完成的复习数量
2. **连续天数**：连续学习天数（带小火焰 emoji）
3. **正确率**：整体正确率百分比
4. **总词汇量**：已学习的总词汇数

每个卡片：圆角-xl，边框，微阴影，图标 + 数值 + 标签

**VocabReviewCard**
- 翻转卡片动画 (CSS transform)
- 正面：英文单词
- 背面：中文释义 + 例句
- 评分按钮：忘记/模糊/记住/熟练 (1-4 分制)
- 进度指示器："第 N 个 / 共 M 个"

**ErrorPatternList**
- 常见错误类型列表
- 每项：错误模式名称 + 频次 + 示例
- 点击展开：显示该错误的所有实例

**LearningGoalProgress**
- 每日和每周目标的进度条
- 填充部分使用主色
- 文本："完成 X/Y"

## 颜色系统

### 浅色模式
```css
--color-primary: #6366F1;        /* 靛蓝 - 知识/品牌 */
--color-primary-foreground: #FFF;
--color-accent: #22D3EE;         /* 青色 - AI/对话强调色 */
--color-success: #22C55E;        /* 绿色 - 正确 */
--color-warning: #F59E0B;        /* 琥珀色 - 待复习 */
--color-error: #EF4444;          /* 红色 - 错误 */
--color-background: #FFFFFF;
--color-foreground: #0F172A;
--color-muted: #F1F5F9;
--color-muted-foreground: #64748B;
--color-border: #E2E8F0;
```

### 深色模式 (通过 prefers-color-scheme 自动切换)
```css
--color-background: #0F172A;
--color-foreground: #F8FAFC;
--color-muted: #1E293B;
--color-border: #334155;
```

## API 集成

### 使用的端点

| 端点 | 方法 | Tab | 用途 |
|------|------|-----|------|
| `/api/chat/send` | POST | 对话 | 发送消息，接收 AI 响应 |
| `/api/learners` | POST | 设置 | 创建学习者 |
| `/api/learners/{id}` | GET | 设置 | 获取学习者信息 |
| `/api/learners/{id}/vocabulary/due` | GET | 学习中心 | 获取待复习词汇 |
| `/api/learners/{id}/vocabulary/review` | POST | 学习中心 | 提交复习结果 |
| `/api/sessions/start` | POST | 对话 | 开始学习会话 |

### 流式响应
- 对话使用 SSE (Server-Sent Events) 流式传输 AI 响应
- 自定义 `useChat` hook 管理流生命周期
- AbortController 支持取消

## 深色模式实现

- 使用 `prefers-color-scheme: dark` 媒体查询
- 在 `<html>` 元素上切换 class
- shadcn/ui CSS 变量处理主题切换
- 无需手动切换 — 自动跟随系统偏好

## 项目结构

```
binnagent-frontend/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── index.css                    # Tailwind @import + @theme
│   ├── components/
│   │   ├── ui/                      # shadcn 组件
│   │   ├── chat/
│   │   │   ├── ChatContainer.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   ├── TypingIndicator.tsx
│   │   │   └── WelcomeScreen.tsx
│   │   ├── dashboard/
│   │   │   ├── DashboardLayout.tsx
│   │   │   ├── StatsCards.tsx
│   │   │   ├── VocabReviewCard.tsx
│   │   │   ├── ErrorPatternList.tsx
│   │   │   └── LearningGoalProgress.tsx
│   │   └── layout/
│   │       ├── Header.tsx
│   │       └── Tabs.tsx
│   ├── hooks/
│   │   ├── useChat.ts
│   │   └── useVocab.ts
│   ├── lib/
│   │   ├── api.ts
│   │   └── utils.ts
│   ├── types/
│   │   ├── chat.ts
│   │   └── learner.ts
│   └── pages/
│       ├── ChatPage.tsx
│       └── DashboardPage.tsx
```

## 快速开始

### 1. 安装依赖
```bash
cd binnagent-frontend
npm install
```

### 2. 启动开发服务器
```bash
npm run dev
```

前端将运行在 http://localhost:3000，自动代理 `/api` 请求到后端 http://localhost:8000。

### 3. 构建生产版本
```bash
npm run build
```

## 成功标准

1. Tab 切换在 AI 对话和学习中心之间即时工作
2. AI 对话显示流式响应和打字指示器
3. 词汇复习卡片点击翻转，动画流畅
4. 统计卡片显示来自 API 的真实数据
5. 深色模式基于系统偏好自动激活
6. 所有 API 端点连接并正常工作
7. 无 TypeScript 错误（strict 模式）
8. 在桌面视口 (1024px+) 内响应式

## 设计规范

详细设计规范请参考：
- [Web Frontend Design Spec](superpowers/specs/2026-06-12-web-frontend-design.md)
