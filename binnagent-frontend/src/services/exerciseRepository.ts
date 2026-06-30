import {
  BUILTIN_EXERCISES,
  CORE_VOCABULARY_EXERCISE_TARGET,
} from '@/data/exercises/builtinExercises'
import type { ExerciseAttempt, ExerciseItem, ExerciseTarget } from '@/types/exercises'

interface ExerciseQueryOptions {
  limit?: number
}

interface StoredExerciseAttempts {
  version: 1
  attempts: ExerciseAttempt[]
}

const ATTEMPTS_STORAGE_KEY = 'binnExerciseAttempts:v1'
const MAX_STORED_ATTEMPTS = 120

export { CORE_VOCABULARY_EXERCISE_TARGET }

export function getExercisesForTarget(
  target: ExerciseTarget,
  options: ExerciseQueryOptions = {},
): ExerciseItem[] {
  const matched = BUILTIN_EXERCISES.filter(
    (exercise) => exercise.target.type === target.type && exercise.target.id === target.id,
  )

  if (typeof options.limit !== 'number') return matched
  return matched.slice(0, Math.max(0, options.limit))
}

export function normalizeExerciseTargetId(value: string) {
  const normalized = value
    .trim()
    .toLocaleLowerCase()
    .replace(/['’]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')

  return normalized || 'unknown'
}

export function readExerciseAttempts(): ExerciseAttempt[] {
  try {
    const raw = localStorage.getItem(ATTEMPTS_STORAGE_KEY)
    if (!raw) return []
    const stored = JSON.parse(raw) as Partial<StoredExerciseAttempts>
    return Array.isArray(stored.attempts) ? stored.attempts.filter(isExerciseAttempt) : []
  } catch (error) {
    console.warn('Unable to read exercise attempts from localStorage.', error)
    return []
  }
}

export function recordExerciseAttempt(attempt: ExerciseAttempt) {
  try {
    const next: StoredExerciseAttempts = {
      version: 1,
      attempts: [attempt, ...readExerciseAttempts()].slice(0, MAX_STORED_ATTEMPTS),
    }
    localStorage.setItem(ATTEMPTS_STORAGE_KEY, JSON.stringify(next))
  } catch (error) {
    console.warn('Unable to store exercise attempt in localStorage.', error)
  }
}

function isExerciseAttempt(value: unknown): value is ExerciseAttempt {
  if (!value || typeof value !== 'object') return false
  const attempt = value as Partial<ExerciseAttempt>
  return (
    typeof attempt.id === 'string' &&
    typeof attempt.exerciseId === 'string' &&
    typeof attempt.answer === 'string' &&
    typeof attempt.createdAt === 'string' &&
    (attempt.result === 'correct' || attempt.result === 'incorrect') &&
    Boolean(attempt.target) &&
    typeof attempt.target === 'object'
  )
}
