import { renderToString } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { selectDebugLearner } from './actions'
import { LearnersList } from './LearnersPage'
import type { LearnerDebugSummary } from './types'

const learner: LearnerDebugSummary = {
  id: 'learner-1',
  nickname: 'Alice',
  email: 'alice@example.com',
  created_at: '2026-07-02T10:00:00Z',
  updated_at: '2026-07-02T10:00:00Z',
  profile: {
    target_exam: 'CET6',
    current_level: 'intermediate',
    daily_time_budget_minutes: 30,
  },
  counts: {
    episode_count: 3,
    memory_event_count: 4,
    exercise_attempt_count: 5,
    vocabulary_count: 6,
  },
}

describe('LearnersPage', () => {
  it('renders learner list mock data', () => {
    const html = renderToString(
      <LearnersList learners={[learner]} onSelect={() => undefined} onViewEpisodes={() => undefined} />
    ).replaceAll('<!-- -->', '')

    expect(html).toContain('Alice')
    expect(html).toContain('alice@example.com')
    expect(html).toContain('CET6')
    expect(html).toContain('episodes 3')
    expect(html).toContain('vocabulary 6')
  })

  it('selectDebugLearner calls onLearnerChange', () => {
    const onLearnerChange = vi.fn()

    selectDebugLearner(learner, onLearnerChange)

    expect(onLearnerChange).toHaveBeenCalledWith({
      id: 'learner-1',
      nickname: 'Alice',
      email: 'alice@example.com',
    })
  })
})
