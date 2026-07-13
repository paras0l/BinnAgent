import { describe, expect, it } from 'vitest'
import { buildReadingCoachContext } from './readingCoachContext'

describe('buildReadingCoachContext', () => {
  it('captures the latest reading session without mixing it into the visible question', () => {
    const context = buildReadingCoachContext({
      material: {
        title: 'A Better Way to Read',
        text: 'Readers slow down when a sentence becomes difficult.',
        level: 'general',
        goal: 'intensive',
        material_type: 'passage',
      },
      materialId: 'material-1',
      workspace: 'intensive',
      currentSentence: { id: 'sentence-1', order: 1, text: 'Readers slow down when a sentence becomes difficult.' },
      selectedText: 'slow down',
      extensiveNotes: { gist: 'Reading strategies', attitude: '', paragraphFunction: '', centralSentence: '' },
      intensiveNotes: { mainStructure: 'Readers slow down', phraseNotes: '', evidenceNote: '' },
      grammarTopics: ['时间状语从句'],
    })

    expect(context.artifactType).toBe('reading_session')
    expect(context.payload.workspace).toBe('intensive')
    expect(context.payload.focus).toEqual({
      sentenceOrder: 1,
      sentence: 'Readers slow down when a sentence becomes difficult.',
      selectedText: 'slow down',
    })
    expect(context.payload.learnerWork.grammarTopics).toEqual(['时间状语从句'])
  })
})
