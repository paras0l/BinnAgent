import { describe, expect, it } from 'vitest'
import { buildTodaySteps } from './dashboardLearningFlow'
import type { DashboardSummary } from '@/types'

const summary = {
  stats: { today_reviews: 0, today_ai_conversations: 0 },
  today_goal: { completed: 0, total: 1 },
} as DashboardSummary

describe('buildTodaySteps', () => {
  it('replaces textbook steps and actions for the reading track', () => {
    const steps = buildTodaySteps(summary, 'reading')

    expect(steps.map((step) => step.title)).toContain('阅读今天的个性化短文')
    expect(steps.map((step) => step.title).join(' ')).not.toContain('教材')
    expect(steps[1].action).toBe('reading')
    expect(steps[2].action).toBe('reading')
  })

  it('keeps the existing lesson flow for the school track', () => {
    const steps = buildTodaySteps(summary, 'school')

    expect(steps[1].title).toBe('开始今天的教材课')
    expect(steps[1].action).toBe('lesson')
  })
})
