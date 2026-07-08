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

interface StoredExerciseItems {
  version: 1
  exercises: ExerciseItem[]
}

export interface GenerateExercisesRequest {
  target: ExerciseTarget
  count: number
  exerciseTypes?: ExerciseItem['type'][]
  context?: {
    page?: string
    explanation?: string
    examples?: string[]
    learnerLevel?: string
  }
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
const EXERCISES_STORAGE_KEY = 'binnCustomExercises:v1'
const MAX_STORED_ATTEMPTS = 120
export const EXERCISE_ATTEMPTS_UPDATED_EVENT = 'binnExerciseAttemptsUpdated'
export const EXERCISES_UPDATED_EVENT = 'binnExercisesUpdated'

export { CORE_VOCABULARY_EXERCISE_TARGET }

export function getExercisesForTarget(
  target: ExerciseTarget,
  options: ExerciseQueryOptions = {},
): ExerciseItem[] {
  const matched = [...BUILTIN_EXERCISES, ...readSavedExercises()].filter(
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

export async function generateExercisesForTarget(
  learnerId: string,
  request: GenerateExercisesRequest,
): Promise<ExerciseItem[]> {
  const response = await fetch(
    `/api/learners/${encodeURIComponent(learnerId)}/exercises/generate`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    },
  )
  if (!response.ok) {
    throw new Error('AI 生成练习暂时不可用。')
  }
  const data = await response.json() as unknown
  return Array.isArray(data) ? data.filter(isExerciseItem) : []
}

export function readSavedExercises(): ExerciseItem[] {
  try {
    const raw = localStorage.getItem(EXERCISES_STORAGE_KEY)
    if (!raw) return []
    const stored = JSON.parse(raw) as Partial<StoredExerciseItems>
    return Array.isArray(stored.exercises) ? stored.exercises.filter(isExerciseItem) : []
  } catch (error) {
    console.warn('Unable to read saved exercises from localStorage.', error)
    return []
  }
}

export function saveExerciseItem(exercise: ExerciseItem) {
  try {
    const existing = readSavedExercises().filter((item) => item.id !== exercise.id)
    const next: StoredExerciseItems = {
      version: 1,
      exercises: [exercise, ...existing],
    }
    localStorage.setItem(EXERCISES_STORAGE_KEY, JSON.stringify(next))
    notifyExercisesUpdated(exercise)
  } catch (error) {
    console.warn('Unable to store exercise item in localStorage.', error)
  }
}

export function saveExerciseItems(exercises: ExerciseItem[]) {
  for (const exercise of exercises) {
    saveExerciseItem(exercise)
  }
}

export function extractExercisesFromHtml(html: string, target: ExerciseTarget): ExerciseItem[] {
  const fragment = extractHtmlFragment(html)
  if (!fragment.trim()) return []
  const extracted = typeof DOMParser === 'undefined'
    ? extractExercisesWithRegex(fragment, target)
    : extractExercisesWithDom(fragment, target)

  const seen = new Set<string>()
  return extracted.filter((exercise) => {
    const key = `${exercise.prompt}:${exercise.correctAnswer}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
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

function notifyExercisesUpdated(exercise: ExerciseItem) {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent(EXERCISES_UPDATED_EVENT, { detail: exercise }))
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
  return value === 'single_choice' || value === 'fill_blank' || value === 'grammar_fill_blank'
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

function extractExercisesWithDom(html: string, target: ExerciseTarget): ExerciseItem[] {
  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')
  const dataNodes = Array.from(doc.querySelectorAll('[data-exercise="true"], [data-exercise-answer], [data-answer]'))
  const fromDataNodes = dataNodes
    .map((node, index) => exerciseFromElement(node as HTMLElement, target, index))
    .filter((exercise): exercise is ExerciseItem => Boolean(exercise))
  if (fromDataNodes.length > 0) return fromDataNodes
  return extractExercisesFromText(doc.body.textContent ?? '', target)
}

function extractExercisesWithRegex(html: string, target: ExerciseTarget): ExerciseItem[] {
  const taggedBlocks = Array.from(
    html.matchAll(/<([a-z0-9-]+)\b([^>]*\bdata-exercise\s*=\s*["']true["'][^>]*)>([\s\S]*?)<\/\1>/gi),
  )
    .map((match, index) => {
      const attrs = match[2] ?? ''
      const content = match[3] ?? ''
      const answer = attrValue(attrs, 'data-answer') || attrValue(attrs, 'data-exercise-answer')
      if (!answer) return null
      return buildImportedExercise({
        target,
        index,
        prompt: cleanExercisePrompt(stripTags(content)),
        answer,
        explanation: attrValue(attrs, 'data-explanation') ||
          `这道题来自“${target.label}”的 HTML 讲解，请根据当前语法规则核对答案。`,
        type: exerciseTypeValue(attrValue(attrs, 'data-exercise-type')),
        acceptedAnswers: answersFromAttribute(attrValue(attrs, 'data-accepted-answers'), answer),
      })
    })
    .filter((exercise): exercise is ExerciseItem => Boolean(exercise))
  if (taggedBlocks.length > 0) return taggedBlocks
  return extractExercisesFromText(stripTags(html), target)
}

function exerciseFromElement(node: HTMLElement, target: ExerciseTarget, index: number): ExerciseItem | null {
  const prompt = cleanExercisePrompt(
    node.getAttribute('data-prompt') ||
    node.querySelector('[data-exercise-prompt]')?.textContent ||
    node.textContent ||
    '',
  )
  const answer = (
    node.getAttribute('data-answer') ||
    node.getAttribute('data-exercise-answer') ||
    node.querySelector('[data-answer]')?.textContent ||
    ''
  ).trim()
  const explanation = (
    node.getAttribute('data-explanation') ||
    node.getAttribute('data-exercise-explanation') ||
    node.querySelector('[data-explanation]')?.textContent ||
    `这道题来自“${target.label}”的 HTML 讲解，请根据当前语法规则核对答案。`
  ).trim()
  if (!prompt || !answer) return null
  return buildImportedExercise({
    target,
    index,
    prompt,
    answer,
    explanation,
    type: exerciseTypeValue(node.getAttribute('data-exercise-type')),
    acceptedAnswers: answersFromAttribute(node.getAttribute('data-accepted-answers'), answer),
  })
}

function extractExercisesFromText(text: string, target: ExerciseTarget): ExerciseItem[] {
  const normalized = text
    .replace(/\r/g, '\n')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
  const blocks = normalized
    .split(/(?:^|\n)\s*(?:题目|练习|小题|Exercise|Question)\s*\d*[\s:：.、-]*/i)
    .map((block) => block.trim())
    .filter(Boolean)

  return blocks
    .map((block, index) => exerciseFromTextBlock(block, target, index))
    .filter((exercise): exercise is ExerciseItem => Boolean(exercise))
}

function exerciseFromTextBlock(block: string, target: ExerciseTarget, index: number): ExerciseItem | null {
  const answer = matchGroup(block, /(?:答案|Answer)\s*[:：]\s*([^\n。；;]+)/i)
  if (!answer) return null
  const explanation = matchGroup(block, /(?:解析|解释|Explanation)\s*[:：]\s*([^\n]+)/i) ||
    `这道题来自“${target.label}”的 HTML 讲解，请根据当前语法规则核对答案。`
  const prompt = cleanExercisePrompt(block.split(/(?:答案|Answer)\s*[:：]/i)[0] ?? '')
  if (!prompt || !looksLikeFillBlank(prompt)) return null
  return buildImportedExercise({
    target,
    index,
    prompt,
    answer,
    explanation,
    type: 'grammar_fill_blank',
    acceptedAnswers: [answer],
  })
}

function buildImportedExercise({
  target,
  index,
  prompt,
  answer,
  explanation,
  type,
  acceptedAnswers,
}: {
  target: ExerciseTarget
  index: number
  prompt: string
  answer: string
  explanation: string
  type: ExerciseItem['type']
  acceptedAnswers: string[]
}): ExerciseItem {
  return {
    id: `imported-html-${target.type}-${target.id}-${Date.now()}-${index + 1}`,
    target,
    skill: target.type === 'grammar_topic' ? 'grammar' : 'vocabulary',
    type,
    prompt,
    options: [],
    correctAnswer: answer,
    acceptedAnswers,
    explanation,
    difficulty: 'easy',
    source: {
      type: 'imported',
      name: 'grammar_html',
    },
    metadata: {
      importedFrom: 'html',
      targetType: target.type,
      targetId: target.id,
    },
  }
}

function extractHtmlFragment(value: string) {
  const fenced = value.match(/```(?:html)?\s*([\s\S]*?)```/i)
  return (fenced?.[1] ?? value).trim()
}

function attrValue(attrs: string, name: string) {
  const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = attrs.match(new RegExp(`${escapedName}\\s*=\\s*["']([^"']*)["']`, 'i'))
  return match?.[1]?.trim() ?? ''
}

function stripTags(value: string) {
  return value
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function cleanExercisePrompt(value: string) {
  return value
    .replace(/(?:答案|Answer)\s*[:：]\s*[^\n。；;]+/gi, '')
    .replace(/(?:解析|解释|Explanation)\s*[:：]\s*[^\n]+/gi, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function exerciseTypeValue(value: string | null): ExerciseItem['type'] {
  if (value === 'single_choice' || value === 'fill_blank' || value === 'grammar_fill_blank') return value
  return 'grammar_fill_blank'
}

function answersFromAttribute(value: string | null, fallback: string) {
  const answers = value
    ? value.split(/[|,，；;]/).map((item) => item.trim()).filter(Boolean)
    : []
  return answers.length > 0 ? answers : [fallback]
}

function matchGroup(value: string, pattern: RegExp) {
  return value.match(pattern)?.[1]?.trim() ?? ''
}

function looksLikeFillBlank(value: string) {
  return /_{2,}|___|\(\s*\)|\[\s*\]|<blank>/i.test(value)
}
