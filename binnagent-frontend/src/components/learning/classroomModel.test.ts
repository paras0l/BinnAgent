import { describe, expect, it } from 'vitest'
import { getPhaseGate, isPhaseAccessible, type PhaseGateEvidence } from './classroomModel'

const EMPTY: PhaseGateEvidence = {
  vocabularyClassified: 0,
  vocabularyRequired: 4,
  grammarAnswered: 0,
  grammarRequired: 3,
  grammarTransferLength: 0,
  continuousAudioPlayed: false,
  listenedCueCount: 0,
  textbookAnswerCount: 0,
  challengeCompleted: false,
}

describe('classroom phase gates', () => {
  it('requires active evidence before unlocking vocabulary, grammar, audio, textbook, and challenge phases', () => {
    expect(getPhaseGate('cards', EMPTY).canContinue).toBe(false)
    expect(getPhaseGate('grammar', { ...EMPTY, grammarAnswered: 3, grammarTransferLength: 8 }).canContinue).toBe(true)
    expect(getPhaseGate('audio', { ...EMPTY, listenedCueCount: 3 }).canContinue).toBe(true)
    expect(getPhaseGate('textbook', { ...EMPTY, textbookAnswerCount: 1 }).canContinue).toBe(true)
    expect(getPhaseGate('challenge', { ...EMPTY, challengeCompleted: true }).canContinue).toBe(true)
  })

  it('allows review navigation without treating locked future phases as accessible', () => {
    expect(isPhaseAccessible(0, 2, false)).toBe(true)
    expect(isPhaseAccessible(3, 2, false)).toBe(false)
    expect(isPhaseAccessible(3, 2, true)).toBe(true)
    expect(isPhaseAccessible(5, 2, true)).toBe(false)
  })
})
