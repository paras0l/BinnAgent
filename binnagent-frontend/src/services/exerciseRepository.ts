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

export interface ExerciseAttemptSummary {
  total: number
  correct: number
  incorrect: number
  accuracy: number
  lastAttemptAt: string | null
  lastResult: ExerciseAttempt['result'] | null
  needsReview: boolean
  learningStatus: ExerciseLearningStatus
}

export type ExerciseLearningStatus = 'mastered' | 'needs_review' | 'unstable' | 'not_started'

const ATTEMPTS_STORAGE_KEY = 'binnExerciseAttempts:v1'
const MAX_STORED_ATTEMPTS = 120
export const EXERCISE_ATTEMPTS_UPDATED_EVENT = 'binnExerciseAttemptsUpdated'

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

export function getExerciseAttemptsForTarget(target: ExerciseTarget): ExerciseAttempt[] {
  return readExerciseAttempts()
    .filter((attempt) => isSameExerciseTarget(attempt.target, target))
    .sort(compareAttemptDateDesc)
}

export function getExerciseSummaryForTarget(target: ExerciseTarget): ExerciseAttemptSummary {
  const attempts = getExerciseAttemptsForTarget(target)
  const total = attempts.length
  const correct = attempts.filter((attempt) => attempt.result === 'correct').length
  const incorrect = total - correct
  const accuracy = total > 0 ? Math.round((correct / total) * 100) : 0
  const lastAttempt = attempts[0]
  const lastResult = lastAttempt?.result ?? null
  const learningStatus = getExerciseLearningStatus(total, accuracy, lastResult)

  return {
    total,
    correct,
    incorrect,
    accuracy,
    lastAttemptAt: lastAttempt?.createdAt ?? null,
    lastResult,
    needsReview: total > 0 && (lastResult === 'incorrect' || accuracy < 70),
    learningStatus,
  }
}

export function getRecentExerciseAttempts(limit = 5): ExerciseAttempt[] {
  return readExerciseAttempts()
    .toSorted(compareAttemptDateDesc)
    .slice(0, Math.max(0, limit))
}

export function recordExerciseAttempt(attempt: ExerciseAttempt) {
  try {
    const next: StoredExerciseAttempts = {
      version: 1,
      attempts: [attempt, ...readExerciseAttempts()].slice(0, MAX_STORED_ATTEMPTS),
    }
    localStorage.setItem(ATTEMPTS_STORAGE_KEY, JSON.stringify(next))
    notifyExerciseAttemptsUpdated(attempt)
  } catch (error) {
    console.warn('Unable to store exercise attempt in localStorage.', error)
  }
}

function notifyExerciseAttemptsUpdated(attempt: ExerciseAttempt) {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent(EXERCISE_ATTEMPTS_UPDATED_EVENT, { detail: attempt }))
}

function isSameExerciseTarget(left: ExerciseTarget, right: ExerciseTarget) {
  return left.type === right.type && left.id === right.id
}

function getExerciseLearningStatus(
  total: number,
  accuracy: number,
  lastResult: ExerciseAttempt['result'] | null,
): ExerciseLearningStatus {
  if (total === 0) return 'not_started'
  if (lastResult === 'incorrect') return 'needs_review'
  if (accuracy >= 80 && lastResult === 'correct') return 'mastered'
  return 'unstable'
}

function compareAttemptDateDesc(left: ExerciseAttempt, right: ExerciseAttempt) {
  return Date.parse(right.createdAt) - Date.parse(left.createdAt)
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
