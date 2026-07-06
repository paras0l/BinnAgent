import { useCallback, useMemo, useState } from 'react'
import type { VocabularyPracticeMode } from '@/pages/VocabularyPracticePage'

export interface LearningPreferences {
  defaultPracticeMode: VocabularyPracticeMode
  defaultLimit: number
  pronunciationAccent: 'uk' | 'us' | 'auto'
  showSetupBeforePractice: boolean
  autoPlayPronunciation: boolean
  autoCheckSpelling: boolean
  autoAdvanceAfterPractice: boolean
  scopeUnitVocabularyByDefault: boolean
}

export const defaultLearningPreferences: LearningPreferences = {
  defaultPracticeMode: 'review',
  defaultLimit: 10,
  pronunciationAccent: 'uk',
  showSetupBeforePractice: false,
  autoPlayPronunciation: false,
  autoCheckSpelling: true,
  autoAdvanceAfterPractice: false,
  scopeUnitVocabularyByDefault: true,
}

function storageKey(learnerId: string) {
  return `binnLearningPreferences:${learnerId}`
}

function normalizePreferences(value: unknown): LearningPreferences {
  if (!value || typeof value !== 'object') return defaultLearningPreferences
  const preferences = value as Partial<LearningPreferences>
  return {
    defaultPracticeMode: ['new', 'review', 'spelling'].includes(preferences.defaultPracticeMode ?? '')
      ? preferences.defaultPracticeMode as VocabularyPracticeMode
      : defaultLearningPreferences.defaultPracticeMode,
    defaultLimit: Number.isFinite(preferences.defaultLimit)
      ? Math.max(1, Math.min(50, Math.round(preferences.defaultLimit ?? defaultLearningPreferences.defaultLimit)))
      : defaultLearningPreferences.defaultLimit,
    pronunciationAccent: ['uk', 'us', 'auto'].includes(preferences.pronunciationAccent ?? '')
      ? preferences.pronunciationAccent as LearningPreferences['pronunciationAccent']
      : defaultLearningPreferences.pronunciationAccent,
    showSetupBeforePractice: preferences.showSetupBeforePractice ?? defaultLearningPreferences.showSetupBeforePractice,
    autoPlayPronunciation: preferences.autoPlayPronunciation ?? defaultLearningPreferences.autoPlayPronunciation,
    autoCheckSpelling: preferences.autoCheckSpelling ?? defaultLearningPreferences.autoCheckSpelling,
    autoAdvanceAfterPractice: preferences.autoAdvanceAfterPractice ?? defaultLearningPreferences.autoAdvanceAfterPractice,
    scopeUnitVocabularyByDefault: preferences.scopeUnitVocabularyByDefault ?? defaultLearningPreferences.scopeUnitVocabularyByDefault,
  }
}

export function loadLearningPreferences(learnerId: string): LearningPreferences {
  const raw = localStorage.getItem(storageKey(learnerId))
  if (!raw) return defaultLearningPreferences
  try {
    return normalizePreferences(JSON.parse(raw))
  } catch {
    return defaultLearningPreferences
  }
}

export function useLearningPreferences(learnerId?: string | null) {
  const [, forceRefresh] = useState(0)
  const preferences = learnerId ? loadLearningPreferences(learnerId) : defaultLearningPreferences

  const updatePreferences = useCallback((patch: Partial<LearningPreferences>) => {
    if (!learnerId) return
    const current = loadLearningPreferences(learnerId)
    const next = normalizePreferences({ ...current, ...patch })
    localStorage.setItem(storageKey(learnerId), JSON.stringify(next))
    forceRefresh((value) => value + 1)
  }, [learnerId])

  const resetPreferences = useCallback(() => {
    if (!learnerId) return
    localStorage.setItem(storageKey(learnerId), JSON.stringify(defaultLearningPreferences))
    forceRefresh((value) => value + 1)
  }, [learnerId])

  return useMemo(() => ({
    preferences,
    resetPreferences,
    updatePreferences,
  }), [preferences, resetPreferences, updatePreferences])
}
