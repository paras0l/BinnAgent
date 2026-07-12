import { describe, expect, it } from 'vitest'
import exploreSource from './ExplorePage.tsx?raw'

describe('Explore vocabulary navigation', () => {
  it('does not show vocabulary manager or review cards in explore', () => {
    expect(exploreSource).toContain('HIDDEN_EXPLORE_FEATURE_IDS')
    expect(exploreSource).not.toContain("title: '词汇本管理'")
    expect(exploreSource).not.toContain("title: '复习待掌握词汇'")
  })

  it('does not expose the expression lab from explore', () => {
    expect(exploreSource).toContain("'expression-lab'")
    expect(exploreSource).not.toContain("title: '英语表达实验室'")
    expect(exploreSource).not.toContain('onOpenExpressionLab')
  })

  it('prioritizes the learner track and hides planned capabilities by default', () => {
    expect(exploreSource).toContain('learningTrackForGoal')
    expect(exploreSource).toContain('learningTrackLabel')
    expect(exploreSource).toContain("feature.status === 'ready'")
    expect(exploreSource).toContain('查看规划中能力')
    expect(exploreSource).toContain('全部可用工具')
  })
})
