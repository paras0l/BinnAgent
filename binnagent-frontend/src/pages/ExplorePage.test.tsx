import { describe, expect, it } from 'vitest'
import exploreSource from './ExplorePage.tsx?raw'

describe('Explore vocabulary navigation', () => {
  it('routes vocabulary manager to the dedicated learning center workspace', () => {
    expect(exploreSource).toContain("id: 'vocabulary-manager'")
    expect(exploreSource).toContain("toolTarget: 'vocabulary-manager'")
    expect(exploreSource).toContain('onOpenVocabularyManager()')
    expect(exploreSource).toContain('normalizeToolTarget')
    expect(exploreSource).toContain("if (featureId === 'vocabulary-manager') return 'vocabulary-manager'")
  })
})
