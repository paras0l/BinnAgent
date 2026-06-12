# BinnAgent Web Frontend Design Spec

**Date**: 2026-06-12
**Status**: Draft
**Purpose**: React web frontend for BinnAgent English learning AI companion

---

## Design Philosophy

> "漂亮的网页也是可以增加学习动力的" — Beautiful UI increases learning motivation

活泼教育风 (Lively Educational Style): Bright, engaging, approachable — like Duolingo but for English conversation practice. Not gamified, but visually pleasant and inviting.

---

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Build | Vite 6 | Fast HMR, native ESM |
| UI | React 19 | Latest stable, concurrent features |
| Language | TypeScript (strict) | Type safety |
| CSS | Tailwind CSS v4 | CSS-first config, `@theme` tokens |
| Components | shadcn/ui (Radix) | Copy-paste, accessible, customizable |
| Routing | React Router v7 | Simple tab-based routing |
| Server State | TanStack Query | Caching, devtools |
| Client State | Zustand | Lightweight learner state |
| Icons | Lucide React | Standard with shadcn |

---

## Layout Structure

```
+--------------------------------------------------+
|  [Logo] BinnAgent    [AI对话]  [学习中心]        |
+--------------------------------------------------+
|                                                    |
|           (Tab content area - full width)          |
|                                                    |
+--------------------------------------------------+
```

- **Top navigation bar**: Fixed, contains logo + two tabs
- **Tab switching**: Click tab to switch content, no URL changes needed
- **Selected tab**: Highlighted with primary color + underline indicator
- **Content area**: Full width, scrollable

---

## Tab 1: AI Chat (AI对话)

### Layout
```
+--------------------------------------------------+
|  Messages area (scrollable, auto-scroll)          |
|  ┌─────────────────────────────────────────────┐  |
|  │  [AI Avatar] Hello! Let's practice...       │  |
|  └─────────────────────────────────────────────┘  |
|                                                    |
|  ┌─────────────────────────────────────────────┐  |
|  │  Hi! I want to learn about travel vocab...  │  │
|  └─────────────────────────────────────────────┘  |
|  [User Avatar]                                     |
|                                                    |
+--------------------------------------------------+
|  [Input: Type your message...]        [Send] [Stop]|
+--------------------------------------------------+
```

### Components

**MessageBubble**
- User messages: Indigo background (#6366F1), white text, right-aligned
- AI messages: Light gray background (#F1F5F9), dark text, left-aligned
- Rounded corners (16px), subtle shadow
- Timestamp below message (10px, muted)
- Typing indicator: 3 animated dots when AI is generating

**ChatInput**
- Fixed at bottom of chat area
- Rounded input field with placeholder "输入你想练习的内容..."
- Send button (indigo) when text present
- Stop button (red) when streaming
- Keyboard shortcut: Enter to send, Shift+Enter for newline

**WelcomeScreen**
- Shown when no messages yet
- Friendly greeting with AI avatar
- Quick start buttons: "开始一节对话课", "复习今天词汇", "练习口语场景"

---

## Tab 2: Learning Center (学习中心)

### Layout
```
+--------------------------------------------------+
|  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ |
|  │ 今日复习 │ │ 连续天数 │ │  正确率  │ │总词汇量│ |
|  │    12    │ │    5🔥   │ │   85%    │ │  156   │ |
|  └──────────┘ └──────────┘ └──────────┘ └────────┘ |
|                                                    |
|  +-----------------------------------------------+ |
|  |  词汇复习 (SRS Cards)                         | |
|  |  ┌─────────────────────────────────────────┐  | |
|  │  │  [Flip Card]                            │  | |
|  │  │  Front: "abundant"                      │  | |
|  │  │  Back:  丰富的 / plenty of              │  | |
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

### Components

**StatsCards** (4 cards in a row)
1. **今日复习**: Number of reviews completed today
2. **连续天数**: Consecutive learning days (with subtle fire emoji)
3. **正确率**: Overall accuracy percentage
4. **总词汇量**: Total vocabulary words learned

Each card: Rounded-xl, border, subtle shadow, icon + value + label

**VocabReviewCard**
- Flip card animation (CSS transform)
- Front: English word
- Back: Chinese definition + example sentence
- Rating buttons: 忘记/模糊/记住/熟练 (1-4 scale)
- Progress indicator: "第 N 个 / 共 M 个"

**ErrorPatternList**
- List of common error types
- Each item: Error pattern name + frequency count + example
- Click to expand: shows all instances of that error

**LearningGoalProgress**
- Progress bars for daily and weekly goals
- Filled portion in primary color
- Text: "完成 X/Y"

---

## Color System

### Light Mode
```css
--color-primary: #6366F1;        /* Indigo - knowledge/brand */
--color-primary-foreground: #FFF;
--color-accent: #22D3EE;         /* Cyan - AI/chat accent */
--color-success: #22C55E;        /* Green - correct */
--color-warning: #F59E0B;        /* Amber - due reviews */
--color-error: #EF4444;          /* Red - mistakes */
--color-background: #FFFFFF;
--color-foreground: #0F172A;
--color-muted: #F1F5F9;
--color-muted-foreground: #64748B;
--color-border: #E2E8F0;
```

### Dark Mode (auto via prefers-color-scheme)
```css
--color-background: #0F172A;
--color-foreground: #F8FAFC;
--color-muted: #1E293B;
--color-border: #334155;
```

---

## Component Specifications

### Header
- Fixed top, height: 64px
- Background: white (light) / dark (dark)
- Border bottom: 1px solid
- Logo: Left, bold "BinnAgent"
- Tabs: Center-right, horizontal

### Tab Component
- Two tabs: "AI对话" and "学习中心"
- Active: Primary color text + underline (2px, primary)
- Hover: Subtle background change
- Transition: 200ms ease

### Card Component
- Border radius: 12px
- Padding: 24px
- Shadow: sm (subtle)
- Hover: shadow-md transition

### Button Component
- Primary: Indigo background, white text
- Secondary: Muted background, foreground text
- Danger: Red background, white text
- All: Rounded-lg, padding 8px 16px, font-medium

---

## API Integration

### Endpoints Used
| Endpoint | Method | Tab | Usage |
|----------|--------|-----|-------|
| `/api/chat/send` | POST | Chat | Send message, receive AI response |
| `/api/learners` | POST | Settings | Create learner |
| `/api/learners/{id}` | GET | Settings | Get learner info |
| `/api/learners/{id}/vocabulary/due` | GET | Learning Center | Get vocabulary for review |
| `/api/learners/{id}/vocabulary/review` | POST | Learning Center | Submit review result |
| `/api/sessions/start` | POST | Chat | Start learning session |

### Streaming
- Chat uses SSE (Server-Sent Events) for streaming AI responses
- Custom `useChat` hook manages stream lifecycle
- AbortController for cancel support

---

## Dark Mode Implementation

- Use `prefers-color-scheme: dark` media query
- Toggle class on `<html>` element
- shadcn/ui CSS variables handle theme switching
- No manual toggle needed — auto follows system preference

---

## File Structure

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
│   │   ├── ui/                      # shadcn components
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

---

## Success Criteria

1. Tab switching works instantly between AI Chat and Learning Center
2. AI chat shows streaming responses with typing indicator
3. Vocab review cards flip on click with smooth animation
4. Stats cards display real data from API
5. Dark mode auto-activates based on system preference
6. All API endpoints connected and functional
7. No TypeScript errors (strict mode)
8. Responsive within desktop viewport (1024px+)
