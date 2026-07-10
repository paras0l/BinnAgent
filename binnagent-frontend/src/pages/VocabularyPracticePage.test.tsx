import { describe, expect, it } from 'vitest'
import source from './VocabularyPracticePage.tsx?raw'

describe('VocabularyPracticePage learner controls', () => {
  it('places the too-easy mastery action below the edit-card action', () => {
    const editCardIndex = source.indexOf('编辑词卡 <BookOpen')
    const tooEasyIndex = source.indexOf('太简单（标记已掌握）')

    expect(editCardIndex).toBeGreaterThan(-1)
    expect(tooEasyIndex).toBeGreaterThan(editCardIndex)
    expect(source).toContain('/too-easy')
    expect(source).toContain('onTooEasy={() => void markTooEasy()}')
  })
})
