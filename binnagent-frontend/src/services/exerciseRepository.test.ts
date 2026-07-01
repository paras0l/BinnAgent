import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BUILTIN_EXERCISES } from '@/data/exercises/builtinExercises'
import type { ExerciseAttempt, ExerciseTarget } from '@/types/exercises'
import {
  fetchExercisesForTarget,
  fetchExerciseSummaryForTarget,
  getExerciseAttemptsForTarget,
  getExerciseSummaryForTarget,
  getExercisesForTarget,
  getRecentExerciseAttempts,
  normalizeExerciseTargetId,
  saveExerciseAttempt,
} from './exerciseRepository'

const ATTEMPTS_STORAGE_KEY = 'binnExerciseAttempts:v1'
const grammarTarget = { type: 'grammar_topic', id: 'present-for-future', label: '主将从现' } satisfies ExerciseTarget

describe('exerciseRepository', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', createLocalStorageMock())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns exercises by exact target type and id with a limit', () => {
    const exercises = getExercisesForTarget(
      grammarTarget,
      { limit: 1 },
    )

    expect(exercises).toHaveLength(1)
    expect(exercises[0]?.target).toMatchObject({
      type: 'grammar_topic',
      id: 'present-for-future',
    })
  })

  it('returns an empty array when the target has no builtin exercises', () => {
    expect(
      getExercisesForTarget({ type: 'grammar_topic', id: 'missing-topic', label: 'Missing' }),
    ).toEqual([])
  })

  it('keeps target metadata on every builtin exercise item', () => {
    expect(BUILTIN_EXERCISES.every((exercise) => exercise.target.type && exercise.target.id)).toBe(true)
    expect(BUILTIN_EXERCISES.every((exercise) => exercise.source.type === 'builtin')).toBe(true)
  })

  it('returns word part exercises by word_part target', () => {
    const exercises = getExercisesForTarget({ type: 'word_part', id: 'prefix-re', label: 're-' })

    expect(exercises).toHaveLength(1)
    expect(exercises[0]?.target).toMatchObject({
      type: 'word_part',
      id: 'prefix-re',
    })
  })

  it('normalizes vocabulary terms to stable target ids', () => {
    expect(normalizeExerciseTargetId('Look up')).toBe('look-up')
    expect(normalizeExerciseTargetId('significant')).toBe('significant')
  })

  it('summarizes attempts for a target and marks recent mistakes for review', () => {
    writeStoredAttempts([
      makeAttempt('a-latest', grammarTarget, 'incorrect', '2026-06-30T10:02:00.000Z'),
      makeAttempt('a-middle', grammarTarget, 'correct', '2026-06-30T10:01:00.000Z'),
      makeAttempt(
        'a-other-target',
        { type: 'word_part', id: 'prefix-re', label: 're-' },
        'correct',
        '2026-06-30T10:03:00.000Z',
      ),
    ])

    const attempts = getExerciseAttemptsForTarget(grammarTarget)
    const summary = getExerciseSummaryForTarget(grammarTarget)

    expect(attempts.map((attempt) => attempt.id)).toEqual(['a-latest', 'a-middle'])
    expect(summary).toMatchObject({
      total: 2,
      correct: 1,
      incorrect: 1,
      accuracy: 50,
      lastAttemptAt: '2026-06-30T10:02:00.000Z',
      lastResult: 'incorrect',
      needsReview: true,
      learningStatus: 'needs_review',
    })
  })

  it('returns not_started when a target has no attempts', () => {
    expect(getExerciseSummaryForTarget(grammarTarget)).toMatchObject({
      total: 0,
      accuracy: 0,
      lastResult: null,
      needsReview: false,
      learningStatus: 'not_started',
    })
  })

  it('marks correct latest attempts below mastery threshold as unstable', () => {
    writeStoredAttempts([
      makeAttempt('latest', grammarTarget, 'correct', '2026-06-30T10:03:00.000Z'),
      makeAttempt('middle', grammarTarget, 'correct', '2026-06-30T10:02:00.000Z'),
      makeAttempt('older', grammarTarget, 'incorrect', '2026-06-30T10:01:00.000Z'),
      makeAttempt('oldest', grammarTarget, 'correct', '2026-06-30T10:00:00.000Z'),
    ])

    expect(getExerciseSummaryForTarget(grammarTarget)).toMatchObject({
      total: 4,
      correct: 3,
      accuracy: 75,
      lastResult: 'correct',
      learningStatus: 'unstable',
    })
  })

  it('marks accuracy below 70 percent as unstable when latest attempt is correct', () => {
    writeStoredAttempts([
      makeAttempt('latest', grammarTarget, 'correct', '2026-06-30T10:03:00.000Z'),
      makeAttempt('older', grammarTarget, 'incorrect', '2026-06-30T10:02:00.000Z'),
      makeAttempt('oldest', grammarTarget, 'incorrect', '2026-06-30T10:01:00.000Z'),
    ])

    expect(getExerciseSummaryForTarget(grammarTarget)).toMatchObject({
      total: 3,
      correct: 1,
      accuracy: 33,
      lastResult: 'correct',
      needsReview: true,
      learningStatus: 'unstable',
    })
  })

  it('marks 80 percent or higher accuracy with a correct latest attempt as mastered', () => {
    writeStoredAttempts([
      makeAttempt('latest', grammarTarget, 'correct', '2026-06-30T10:03:00.000Z'),
      makeAttempt('middle', grammarTarget, 'correct', '2026-06-30T10:02:00.000Z'),
      makeAttempt('older', grammarTarget, 'incorrect', '2026-06-30T10:01:00.000Z'),
      makeAttempt('oldest', grammarTarget, 'correct', '2026-06-30T10:00:00.000Z'),
      makeAttempt('first', grammarTarget, 'correct', '2026-06-30T09:59:00.000Z'),
    ])

    expect(getExerciseSummaryForTarget(grammarTarget)).toMatchObject({
      total: 5,
      correct: 4,
      accuracy: 80,
      lastResult: 'correct',
      learningStatus: 'mastered',
    })
  })

  it('returns recent attempts sorted by created time and limited', () => {
    writeStoredAttempts([
      makeAttempt('older', grammarTarget, 'correct', '2026-06-30T10:00:00.000Z'),
      makeAttempt('newer', grammarTarget, 'correct', '2026-06-30T10:04:00.000Z'),
      makeAttempt('middle', grammarTarget, 'incorrect', '2026-06-30T10:02:00.000Z'),
    ])

    expect(getRecentExerciseAttempts(2).map((attempt) => attempt.id)).toEqual(['newer', 'middle'])
  })

  it('fetches curriculum exercises from backend through the unified ExerciseItem shape', async () => {
    const curriculumTarget = {
      type: 'curriculum_node',
      id: '11111111-1111-1111-1111-111111111111',
      label: 'Starter Unit 1',
    } satisfies ExerciseTarget
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: '22222222-2222-2222-2222-222222222222',
          target: curriculumTarget,
          skill: 'vocabulary',
          type: 'single_choice',
          prompt: 'Which answer is correct?',
          options: ['Good morning!', 'Other'],
          correctAnswer: 'Good morning!',
          acceptedAnswers: [],
          explanation: 'Use the greeting in context.',
          difficulty: 0.3,
          source: {
            type: 'curriculum',
            name: 'knowledge_base',
            refId: '22222222-2222-2222-2222-222222222222',
          },
          metadata: {
            question_type: 'choice_context',
          },
        },
      ],
    }))

    await expect(fetchExercisesForTarget('learner-1', curriculumTarget, { limit: 3 })).resolves.toMatchObject([
      {
        target: curriculumTarget,
        source: { type: 'curriculum' },
        prompt: 'Which answer is correct?',
      },
    ])
  })

  it('falls back to localStorage summary when backend summary is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    writeStoredAttempts([
      makeAttempt('local-latest', grammarTarget, 'correct', '2026-06-30T10:03:00.000Z'),
      makeAttempt('local-older', grammarTarget, 'incorrect', '2026-06-30T10:02:00.000Z'),
    ])

    await expect(fetchExerciseSummaryForTarget('learner-1', grammarTarget)).resolves.toMatchObject({
      total: 2,
      correct: 1,
      accuracy: 50,
      lastResult: 'correct',
      learningStatus: 'unstable',
    })
  })

  it('falls back to localStorage when backend save fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503 }))
    const attempt = makeAttempt('save-fallback', grammarTarget, 'incorrect', '2026-06-30T10:05:00.000Z')

    await expect(saveExerciseAttempt('learner-1', attempt)).resolves.toMatchObject({
      id: 'save-fallback',
    })

    expect(getExerciseAttemptsForTarget(grammarTarget).map((item) => item.id)).toEqual(['save-fallback'])
  })
})

function writeStoredAttempts(attempts: ExerciseAttempt[]) {
  localStorage.setItem(ATTEMPTS_STORAGE_KEY, JSON.stringify({ version: 1, attempts }))
}

function makeAttempt(
  id: string,
  target: ExerciseTarget,
  result: ExerciseAttempt['result'],
  createdAt: string,
): ExerciseAttempt {
  return {
    id,
    exerciseId: `exercise-${id}`,
    target,
    answer: result,
    result,
    createdAt,
    should_update_mastery: true,
    should_create_error_pattern: result === 'incorrect',
    should_create_memory_evidence: true,
  }
}

function createLocalStorageMock(): Storage {
  const store = new Map<string, string>()
  return {
    get length() {
      return store.size
    },
    clear: () => store.clear(),
    getItem: (key: string) => store.get(key) ?? null,
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => {
      store.delete(key)
    },
    setItem: (key: string, value: string) => {
      store.set(key, value)
    },
  }
}
