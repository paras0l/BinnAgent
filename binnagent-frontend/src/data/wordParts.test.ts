import { describe, expect, it } from 'vitest'
import {
  WORD_PARTS,
  inferWordPartAnalysis,
  searchWordParts,
  spellingSafeMorphologyParts,
} from './wordParts'

describe('wordParts data helpers', () => {
  it('includes common prefixes, roots, and suffixes', () => {
    expect(WORD_PARTS.filter((item) => item.kind === 'prefix')).toHaveLength(10)
    expect(WORD_PARTS.filter((item) => item.kind === 'root')).toHaveLength(10)
    expect(WORD_PARTS.filter((item) => item.kind === 'suffix')).toHaveLength(10)
  })

  it('searches forms, meanings, and example words', () => {
    const results = searchWordParts('prediction')
    expect(results.map((item) => item.id)).toEqual(
      expect.arrayContaining(['prefix-pre', 'root-dict', 'suffix-tion']),
    )
  })

  it('infers exact morphology for supported practice words', () => {
    const analysis = inferWordPartAnalysis('prediction')
    expect(analysis?.parts.map((part) => part.form)).toEqual(['pre-', 'dict', '-ion'])
    expect(analysis?.related_word_part_ids).toEqual(['prefix-pre', 'root-dict', 'suffix-tion'])
  })

  it('returns null when a word has no reliable word-part match', () => {
    expect(inferWordPartAnalysis('cat')).toBeNull()
  })

  it('keeps spelling hints to prefixes and suffixes only', () => {
    const analysis = inferWordPartAnalysis('prediction')
    const hints = spellingSafeMorphologyParts(analysis)
    expect(hints.map((part) => part.kind)).toEqual(['prefix', 'suffix'])
    expect(hints.map((part) => part.form)).toEqual(['pre-', '-ion'])
  })
})
