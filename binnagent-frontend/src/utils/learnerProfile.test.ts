import { describe, expect, it } from 'vitest'
import { learningTrackForGoal, learningTrackLabel } from './learnerProfile'

describe('learner profile learning tracks', () => {
  it('groups school, exam, and general goals into stable product tracks', () => {
    expect(learningTrackForGoal('zhongkao')).toBe('school')
    expect(learningTrackForGoal('cet6')).toBe('exam')
    expect(learningTrackForGoal('daily_communication')).toBe('general')
    expect(learningTrackForGoal(null)).toBe('general')
  })

  it('provides learner-facing labels', () => {
    expect(learningTrackLabel('gaokao')).toBe('同步教材学习')
    expect(learningTrackLabel('ielts')).toBe('考试备考')
    expect(learningTrackLabel('daily_communication')).toBe('通用英语提升')
  })
})
