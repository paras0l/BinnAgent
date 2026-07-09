import { describe, expect, it } from 'vitest'
import exploreSource from './ExplorePage.tsx?raw'

describe('Explore vocabulary navigation', () => {
  it('does not show vocabulary manager or review cards in explore', () => {
    expect(exploreSource).toContain('HIDDEN_EXPLORE_FEATURE_IDS')
    expect(exploreSource).not.toContain("title: '词汇本管理'")
    expect(exploreSource).not.toContain("title: '复习待掌握词汇'")
  })
})
