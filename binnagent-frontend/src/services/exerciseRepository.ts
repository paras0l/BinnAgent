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

export async function fetchExercisesForTarget(
  learnerId: string,
  target: ExerciseTarget,
  options: ExerciseQueryOptions = {},
): Promise<ExerciseItem[]> {
  const builtinExercises = getExercisesForTarget(target)
  const backendExercises = target.type === 'curriculum_node'
    ? await fetchBackendExercisesForTarget(learnerId, target, options)
    : []
  const exercises = mergeExercises(backendExercises, builtinExercises)

  if (typeof options.limit !== 'number') return exercises
  return exercises.slice(0, Math.max(0, options.limit))
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

export async function fetchExerciseAttemptsForTarget(
  learnerId: string,
  target: ExerciseTarget,
): Promise<ExerciseAttempt[]> {
  try {
    const params = new URLSearchParams({
      target_type: target.type,
      target_id: target.id,
    })
    const response = await fetch(
      `/api/learners/${encodeURIComponent(learnerId)}/exercise-attempts?${params.toString()}`,
    )
    if (!response.ok) {
      throw new Error(`Exercise attempts request failed with ${response.status}`)
    }
    const data = await response.json() as unknown
    return Array.isArray(data) ? data.filter(isExerciseAttempt) : []
  } catch (error) {
    console.warn('Unable to fetch exercise attempts from backend; using localStorage fallback.', error)
    return getExerciseAttemptsForTarget(target)
  }
}

async function fetchBackendExercisesForTarget(
  learnerId: string,
  target: ExerciseTarget,
  options: ExerciseQueryOptions,
): Promise<ExerciseItem[]> {
  try {
    const params = new URLSearchParams({
      target_type: target.type,
      target_id: target.id,
    })
    if (typeof options.limit === 'number') {
      params.set('limit', String(Math.max(1, options.limit)))
    }
    const response = await fetch(
      `/api/learners/${encodeURIComponent(learnerId)}/exercises?${params.toString()}`,
    )
    if (!response.ok) {
      throw new Error(`Exercises request failed with ${response.status}`)
    }
    const data = await response.json() as unknown
    return Array.isArray(data) ? data.filter(isExerciseItem) : []
  } catch (error) {
    console.warn('Unable to fetch exercises from backend; using builtin fallback.', error)
    return []
  }
}

export async function fetchExerciseSummaryForTarget(
  learnerId: string,
  target: ExerciseTarget,
): Promise<ExerciseAttemptSummary> {
  try {
    const params = new URLSearchParams({
      target_type: target.type,
      target_id: target.id,
    })
    const response = await fetch(
      `/api/learners/${encodeURIComponent(learnerId)}/exercise-attempts/summary?${params.toString()}`,
    )
    if (!response.ok) {
      throw new Error(`Exercise summary request failed with ${response.status}`)
    }
    const data = await response.json() as unknown
    return normalizeExerciseSummary(data, target)
  } catch (error) {
    console.warn('Unable to fetch exercise summary from backend; using localStorage fallback.', error)
    return getExerciseSummaryForTarget(target)
  }
}

export async function saveExerciseAttempt(
  learnerId: string,
  attempt: ExerciseAttempt,
): Promise<ExerciseAttempt> {
  try {
    const response = await fetch(
      `/api/learners/${encodeURIComponent(learnerId)}/exercise-attempts`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(attempt),
      },
    )
    if (!response.ok) {
      throw new Error(`Exercise attempt save failed with ${response.status}`)
    }
    const data = await response.json() as unknown
    const savedAttempt = isExerciseAttempt(data) ? data : attempt
    notifyExerciseAttemptsUpdated(savedAttempt)
    return savedAttempt
  } catch (error) {
    console.warn('Unable to save exercise attempt to backend; using localStorage fallback.', error)
    recordExerciseAttempt(attempt)
    return attempt
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

function isExerciseItem(value: unknown): value is ExerciseItem {
  if (!value || typeof value !== 'object') return false
  const exercise = value as Partial<ExerciseItem>
  return (
    typeof exercise.id === 'string' &&
    Boolean(exercise.target) &&
    typeof exercise.target === 'object' &&
    typeof exercise.target.type === 'string' &&
    typeof exercise.target.id === 'string' &&
    typeof exercise.target.label === 'string' &&
    isExerciseSkill(exercise.skill) &&
    isExerciseType(exercise.type) &&
    typeof exercise.prompt === 'string' &&
    typeof exercise.correctAnswer === 'string' &&
    typeof exercise.explanation === 'string' &&
    Boolean(exercise.source) &&
    typeof exercise.source === 'object' &&
    isExerciseSourceType(exercise.source.type)
  )
}

function isExerciseSkill(value: unknown) {
  return value === 'grammar' || value === 'vocabulary' || value === 'reading'
}

function isExerciseType(value: unknown) {
  return value === 'single_choice' || value === 'fill_blank'
}

function isExerciseSourceType(value: unknown) {
  return (
    value === 'builtin' ||
    value === 'curriculum' ||
    value === 'generated' ||
    value === 'imported' ||
    value === 'manual'
  )
}

function mergeExercises(primary: ExerciseItem[], secondary: ExerciseItem[]) {
  const seen = new Set<string>()
  const merged: ExerciseItem[] = []
  for (const exercise of [...primary, ...secondary]) {
    if (seen.has(exercise.id)) continue
    seen.add(exercise.id)
    merged.push(exercise)
  }
  return merged
}

function normalizeExerciseSummary(value: unknown, target: ExerciseTarget): ExerciseAttemptSummary {
  if (!value || typeof value !== 'object') {
    return getExerciseSummaryForTarget(target)
  }
  const summary = value as Record<string, unknown>
  const total = numberValue(summary.total)
  const correct = numberValue(summary.correct)
  const incorrect = numberValue(summary.incorrect)
  const accuracy = numberValue(summary.accuracy)
  const lastResult = exerciseResultValue(summary.lastResult ?? summary.last_result)
  const learningStatus = exerciseLearningStatusValue(
    summary.learningStatus ?? summary.learning_status,
    getExerciseLearningStatus(total, accuracy, lastResult),
  )

  return {
    total,
    correct,
    incorrect,
    accuracy,
    lastAttemptAt: stringOrNull(summary.lastAttemptAt ?? summary.last_attempt_at),
    lastResult,
    needsReview: Boolean(summary.needsReview ?? summary.needs_review),
    learningStatus,
  }
}

function numberValue(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function stringOrNull(value: unknown) {
  return typeof value === 'string' ? value : null
}

function exerciseResultValue(value: unknown): ExerciseAttempt['result'] | null {
  if (value === 'correct' || value === 'incorrect') return value
  return null
}

function exerciseLearningStatusValue(
  value: unknown,
  fallback: ExerciseLearningStatus,
): ExerciseLearningStatus {
  if (
    value === 'mastered' ||
    value === 'needs_review' ||
    value === 'unstable' ||
    value === 'not_started'
  ) {
    return value
  }
  return fallback
}
