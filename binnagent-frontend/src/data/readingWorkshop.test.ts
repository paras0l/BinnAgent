import { describe, expect, it } from 'vitest'
import {
  buildKeywordCandidates,
  buildSentenceFocusHints,
  countEnglishWords,
  estimateReadingMinutes,
  splitReadingSentences,
  suggestGrammarOptionIds,
} from './readingWorkshop'

describe('readingWorkshop helpers', () => {
  it('splits pasted reading material into stable ordered sentences', () => {
    const sentences = splitReadingSentences(
      'Students often read quickly for the main idea. However, difficult sentences need slower work!'
    )

    expect(sentences).toEqual([
      {
        id: 'reading-sentence-1',
        order: 1,
        text: 'Students often read quickly for the main idea.',
      },
      {
        id: 'reading-sentence-2',
        order: 2,
        text: 'However, difficult sentences need slower work!',
      },
    ])
  })

  it('counts words and estimates at least one minute of reading time', () => {
    expect(countEnglishWords('Fast reading is not careless reading.')).toBe(6)
    expect(estimateReadingMinutes('Short text.', 'cet4')).toBe(1)
  })

  it('returns high-signal keyword candidates before common words', () => {
    const keywords = buildKeywordCandidates(
      'Reading strategy helps students read with purpose. Strategy also keeps reading focused.',
      3
    )

    expect(keywords).toEqual([
      { word: 'reading', count: 2 },
      { word: 'strategy', count: 2 },
      { word: 'helps', count: 1 },
    ])
  })

  it('suggests grammar topics from sentence signals', () => {
    const suggestions = suggestGrammarOptionIds(
      'If students meet a sentence which looks long, they should find the main verb first.'
    )

    expect(suggestions).toEqual(
      expect.arrayContaining(['relative-clause', 'present-for-future'])
    )
  })

  it('builds fallback sentence hints when no obvious signal is present', () => {
    const hints = buildSentenceFocusHints('Students read every day.')

    expect(hints).toEqual([
      {
        id: 'baseline',
        label: '主干线索',
        text: '先找谓语动词，再定位主语和宾语/表语；修饰语放到第二遍处理。',
      },
    ])
  })
})
