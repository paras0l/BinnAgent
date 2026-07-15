import { describe, expect, it } from 'vitest'
import {
  buildReadingCompletionPayload,
  buildReadingCompletionState,
  buildKeywordCandidates,
  buildSentenceFocusHints,
  countEnglishWords,
  estimateReadingMinutes,
  fingerprintReadingCompletionPayload,
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

  it('returns zero minutes for empty text and at least one minute for non-empty text', () => {
    expect(countEnglishWords('Fast reading is not careless reading.')).toBe(6)
    expect(estimateReadingMinutes('   ', 'general')).toBe(0)
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

  it('does not infer a nonfinite form from ing or ed substrings alone', () => {
    for (const sentence of [
      'Reading improves concentration.',
      'This thing matters.',
      'Students need more time.',
    ]) {
      expect(suggestGrammarOptionIds(sentence)).not.toContain('nonfinite-modifier')
    }

    expect(suggestGrammarOptionIds('The students are reading in the library.')).toContain('nonfinite-modifier')
    expect(suggestGrammarOptionIds('They joined a program designed for young readers.')).toContain('nonfinite-modifier')
  })

  it('does not confuse ordinary to-prepositional phrases with infinitives', () => {
    for (const sentence of [
      'They walk to school every morning.',
      'She went to London last summer.',
      'I spoke to him after class.',
    ]) {
      expect(suggestGrammarOptionIds(sentence)).not.toContain('nonfinite-modifier')
    }

    expect(suggestGrammarOptionIds('They read every day to improve their vocabulary.')).toContain(
      'nonfinite-modifier'
    )
  })

  it('requires only extensive evidence for an extensive-reading completion', () => {
    expect(buildReadingCompletionState({
      hasMaterial: true,
      hasExtensiveEvidence: true,
      analyzedSentenceCount: 0,
      goal: 'extensive',
      isRecorded: false,
    })).toEqual({
      completion: {
        input: true,
        extensive: true,
        intensive: false,
        review: false,
      },
      canComplete: true,
      missingLabels: [],
    })
  })

  it('requires an analyzed sentence for an intensive-reading completion', () => {
    const state = buildReadingCompletionState({
      hasMaterial: true,
      hasExtensiveEvidence: false,
      analyzedSentenceCount: 0,
      goal: 'intensive',
      isRecorded: false,
    })

    expect(state.canComplete).toBe(false)
    expect(state.missingLabels).toEqual(['完成至少 1 个精读句'])
  })

  it('requires both reading modes for mixed training and tracks the recorded review separately', () => {
    const incomplete = buildReadingCompletionState({
      hasMaterial: true,
      hasExtensiveEvidence: true,
      analyzedSentenceCount: 0,
      goal: 'mixed',
      isRecorded: false,
    })
    const recorded = buildReadingCompletionState({
      hasMaterial: true,
      hasExtensiveEvidence: true,
      analyzedSentenceCount: 2,
      goal: 'mixed',
      isRecorded: true,
    })

    expect(incomplete.canComplete).toBe(false)
    expect(incomplete.missingLabels).toEqual(['完成至少 1 个精读句'])
    expect(recorded.canComplete).toBe(true)
    expect(recorded.completion).toEqual({
      input: true,
      extensive: true,
      intensive: true,
      review: true,
    })
  })

  it('omits extensive evidence from intensive-only completion payloads', () => {
    const payload = buildReadingCompletionPayload({
      clientAttemptId: 'attempt-intensive-1',
      analyzedSentenceIds: ['reading-sentence-2'],
      goal: 'intensive',
      extensiveEvidence: { gist: '', centralSentence: '' },
      grammarTopicCount: 1,
      grammarBlindSpots: ['定语从句'],
      notes: 'Sentence 2 evidence',
    })

    expect(payload).not.toHaveProperty('extensive_evidence')
    expect(payload).toMatchObject({
      client_attempt_id: 'attempt-intensive-1',
      selected_sentence_count: 1,
      analyzed_sentence_ids: ['reading-sentence-2'],
    })
  })

  it('includes normalized extensive evidence for mixed completion payloads', () => {
    const payload = buildReadingCompletionPayload({
      clientAttemptId: 'attempt-mixed-1',
      analyzedSentenceIds: ['reading-sentence-1'],
      goal: 'mixed',
      extensiveEvidence: {
        gist: '  Effective readers change speed.  ',
        centralSentence: '  Effective readers do more than race through words.  ',
      },
      grammarTopicCount: 0,
      grammarBlindSpots: [],
      notes: null,
    })

    expect(payload).toMatchObject({
      extensive_evidence: {
        gist: 'Effective readers change speed.',
        central_sentence: 'Effective readers do more than race through words.',
      },
    })
  })

  it('fingerprints completion evidence independently from the retry attempt id', () => {
    const first = buildReadingCompletionPayload({
      clientAttemptId: 'attempt-first',
      analyzedSentenceIds: ['reading-sentence-1'],
      goal: 'mixed',
      extensiveEvidence: {
        gist: 'Readers adapt their pace.',
        centralSentence: 'Effective readers change speed.',
      },
      grammarTopicCount: 1,
      grammarBlindSpots: ['定语从句'],
      notes: 'Sentence 1 evidence',
    })
    const retry = { ...first, client_attempt_id: 'attempt-retry' }
    const edited = { ...retry, notes: 'Updated sentence evidence' }

    expect(fingerprintReadingCompletionPayload(retry)).toBe(
      fingerprintReadingCompletionPayload(first),
    )
    expect(fingerprintReadingCompletionPayload(edited)).not.toBe(
      fingerprintReadingCompletionPayload(first),
    )
  })

  it('keeps every stage incomplete without reading material', () => {
    const state = buildReadingCompletionState({
      hasMaterial: false,
      hasExtensiveEvidence: true,
      analyzedSentenceCount: 3,
      goal: 'mixed',
      isRecorded: true,
    })

    expect(state.completion).toEqual({
      input: false,
      extensive: false,
      intensive: false,
      review: false,
    })
    expect(state.canComplete).toBe(false)
    expect(state.missingLabels).toEqual(['添加阅读材料', '完成泛读记录', '完成至少 1 个精读句'])
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
