import { renderToString } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { LearningProfileView, LearningRecordsView } from './DashboardPage'
import dashboardSource from './DashboardPage.tsx?raw'
import type { DashboardSummary, Learner, MemorySummary } from '@/types'

const learner: Learner = {
  id: 'learner-1',
  nickname: 'Alice',
  email: null,
}

const emptySummary: DashboardSummary = {
  stats: {
    today_reviews: 0,
    today_completed_reviews: 0,
    streak_days: 0,
    accuracy: 0,
    total_vocab: 0,
  },
  review_items: [],
  error_patterns: [],
  today_goal: {
    label: '今日目标',
    completed: 0,
    total: 1,
  },
  weekly_goal: {
    label: '本周目标',
    completed: 0,
    total: 5,
  },
  daily_activity: Array.from({ length: 14 }, (_, index) => ({
    date: `2026-07-${String(index + 1).padStart(2, '0')}`,
    count: 0,
  })),
  profile: {
    ability_scores: [],
    mastery_buckets: [],
    trend: [],
  },
}

const emptyMemorySummary: MemorySummary = {
  learner,
  stats: {
    conversation_count: 0,
    message_count: 0,
    total_vocab: 0,
    due_reviews: 0,
    mastered_vocab: 0,
  },
  latest_thread_id: null,
  latest_thread_title: null,
  latest_thread_summary: null,
  error_patterns: [],
  recent_sessions: [],
  recent_events: [],
  active_weaknesses: [],
}

describe('Dashboard learning profile workspaces', () => {
  it('renders a learner-facing profile empty state without debug wording', () => {
    const html = renderToString(
      <LearningProfileView
        learner={learner}
        summary={emptySummary}
        memorySummary={emptyMemorySummary}
        onBack={vi.fn()}
        onOpenDailyLearning={vi.fn()}
        onOpenRecords={vi.fn()}
      />,
    ).replaceAll('<!-- -->', '')

    expect(html).toContain('我的学习画像')
    expect(html).toContain('目标与水平')
    expect(html).toContain('查看分级标准')
    expect(html).toContain('画像正在建立中')
    expect(html).toContain('状态摘要')
    expect(html).toContain('最近表现')
    expect(html).toContain('下一步建议')
    expect(html).toContain('还没有足够的能力证据')
    expect(html).toContain('还没有掌握度记录')
    expect(html).not.toContain('数据控制说明')
    expect(html).not.toContain('/memory/center')
    expect(html).not.toContain('Memory Debug')
    expect(html).not.toContain('raw_prompt')
    expect(html).not.toContain('raw_output')
    expect(html).not.toContain('confidence')
    expect(html).not.toContain('Learning Profile')
  })

  it('renders a records empty state with calendar, sessions, events, and stats sections', () => {
    const html = renderToString(
      <LearningRecordsView
        summary={emptySummary}
        memorySummary={emptyMemorySummary}
        onBack={vi.fn()}
        onOpenProfile={vi.fn()}
      />,
    ).replaceAll('<!-- -->', '')

    expect(html).toContain('学习记录')
    expect(html).toContain('还没有学习记录')
    expect(html).toContain('最近 14 天活跃度')
    expect(html).toContain('最近学习记录')
    expect(html).toContain('学习动态')
    expect(html).toContain('统计概览')
    expect(html).not.toContain('Learning Records')
  })

  it('does not use scrollIntoView for learning records navigation anymore', () => {
    expect(dashboardSource).not.toContain('scrollIntoView')
    expect(dashboardSource).toContain("setActiveWorkspace('records')")
    expect(dashboardSource).toContain('学习画像')
  })

  it('keeps a direct vocabulary manager entry available', () => {
    expect(dashboardSource).toContain('词汇本管理')
    expect(dashboardSource).toContain('initialVocabularyListOpen')
    expect(dashboardSource).toContain("setActiveWorkspace('vocabulary')")
  })

  it('opens vocabulary training workspace before choosing a practice mode', () => {
    expect(dashboardSource).toContain('handleOpenVocabularyTraining')
    expect(dashboardSource).toContain('onOpenVocabularyTraining')
    expect(dashboardSource).toContain('label="词汇训练"')
    expect(dashboardSource).toContain('onClick={onOpenVocabularyTraining}')
    expect(dashboardSource).not.toContain('label="词汇训练" detail="复习、新词、拼写" onClick={() => onStartVocabularyPractice()}')
  })

  it('keeps the vocabulary manager list bounded and paged', () => {
    expect(dashboardSource).toContain('VOCABULARY_PAGE_SIZE = 12')
    expect(dashboardSource).toContain('pagedVocabulary')
    expect(dashboardSource).toContain('max-h-[min(64vh,760px)] overflow-y-auto')
    expect(dashboardSource).toContain('VocabularyListPagination')
  })

  it('uses backend profile fields instead of estimating ability scores in the browser', () => {
    expect(dashboardSource).toContain('summary.profile?.ability_scores')
    expect(dashboardSource).toContain('summary.profile?.mastery_buckets')
    expect(dashboardSource).toContain('summary.profile?.trend')
    expect(dashboardSource).not.toContain('weaknessPenalty')
    expect(dashboardSource).not.toContain('summary.stats.streak_days * 6 + 45')
  })

  it('normalizes dashboard API payloads before rendering learning center', () => {
    expect(dashboardSource).toContain('normalizeDashboardSummary(await response.json())')
    expect(dashboardSource).toContain("normalizeGoal(source.today_goal, '今日课程', 0, 1)")
    expect(dashboardSource).toContain('asArray(source.daily_activity)')
    expect(dashboardSource).toContain('asArray(source.error_patterns)')
  })

  it('keeps secondary learning-center workspaces out of the first dashboard chunk', () => {
    expect(dashboardSource).toContain("const GroupLearningSignalsPage = lazy(() =>")
    expect(dashboardSource).toContain("const VocabularyPracticePage = lazy(() =>")
    expect(dashboardSource).not.toContain("import { GroupLearningSignalsPage }")
    expect(dashboardSource).not.toContain("import { VocabularyPracticePage }")
  })
})
