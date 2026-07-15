import type {
  ReadingMaterial,
  ReadingMaterialCompleteResponse,
  ReadingMaterialHistoryItem,
  ReadingSentenceAnalysisResponse,
  ReadingWorkspace,
} from './readingWorkshop'

export const READING_DRAFT_VERSION = 3
const READING_DRAFT_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000
const SCRATCH_READING_DRAFT_SCOPE = 'scratch'

interface ReadingDraftExtensiveNotes {
  gist: string
  attitude: string
  paragraphFunction: string
  centralSentence: string
}

interface ReadingDraftIntensiveNotes {
  mainStructure: string
  phraseNotes: string
  evidenceNote: string
}

interface ReadingDraftCoachMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
}

type ReadingDraftTitleMode = 'empty' | 'auto' | 'user'
type ReadingDraftTitleSuggestionStatus = 'idle' | 'checking' | 'suggested' | 'incomplete' | 'error'

export interface ReadingWorkshopDraftV1 {
  version: 3
  learnerId: string
  scopeId: string
  savedAt: number
  workspace: ReadingWorkspace
  material: ReadingMaterial
  extensiveNotes: ReadingDraftExtensiveNotes
  intensiveNotesBySentenceId: Record<string, ReadingDraftIntensiveNotes>
  sentenceAnalysisBySentenceId: Record<string, ReadingSentenceAnalysisResponse>
  selectedSentenceId: string | null
  selectedGrammarOptionIds: string[]
  openedGrammarTopics: string[]
  coachThreadId: string | null
  coachMessages: ReadingDraftCoachMessage[]
  coachDraft: string
  activeMaterialId: string | null
  activeMaterialRecord: ReadingMaterialHistoryItem | null
  saveStatus: 'idle' | 'saved'
  titleMode: ReadingDraftTitleMode
  titleSuggestionStatus: ReadingDraftTitleSuggestionStatus
  autoTitleSourceText: string
  clientAttemptId: string
  attemptSubmitted: boolean
  lastSubmittedEvidenceFingerprint: string | null
  completeStatus: 'idle' | 'completed' | 'error'
  completionResult: ReadingMaterialCompleteResponse | null
}

export type ReadingNavigationBlocker = (navigate: () => void) => boolean
export type ReadingNavigationBlockerChangeHandler = (blocker: ReadingNavigationBlocker | null) => void

export function createClientAttemptId(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID()
  }
  return `reading-attempt-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`
}

export function readingMaterialDraftScope(materialId: string | null | undefined): string {
  return materialId ? `material:${materialId}` : SCRATCH_READING_DRAFT_SCOPE
}

export function runWithReadingNavigationBlocker(
  blocker: ReadingNavigationBlocker | null,
  navigate: () => void,
): 'blocked' | 'navigated' {
  if (blocker?.(navigate)) return 'blocked'
  navigate()
  return 'navigated'
}

export function readingDraftPersistenceAction({
  skipPersist,
  hasContent,
}: {
  skipPersist: boolean
  hasContent: boolean
}): 'skip' | 'write' | 'clear' {
  if (skipPersist) return 'skip'
  return hasContent ? 'write' : 'clear'
}

export function readReadingWorkshopDraft(
  learnerId: string,
  scopeId?: string,
): ReadingWorkshopDraftV1 | null {
  if (typeof window === 'undefined') return null
  try {
    const resolvedScopeId = scopeId
      ?? window.localStorage.getItem(activeReadingDraftScopeKey(learnerId))
      ?? SCRATCH_READING_DRAFT_SCOPE
    const storageKey = readingDraftStorageKey(learnerId, resolvedScopeId)
    let raw = window.localStorage.getItem(storageKey)
    let isLegacyScratchDraft = false
    if (!raw && resolvedScopeId === SCRATCH_READING_DRAFT_SCOPE) {
      raw = window.localStorage.getItem(legacyReadingDraftStorageKey(learnerId))
      isLegacyScratchDraft = Boolean(raw)
    }
    if (!raw) return null
    const parsed = JSON.parse(raw) as unknown
    const draft = normalizeReadingWorkshopDraft(parsed, learnerId, resolvedScopeId)
    if (!draft || Date.now() - draft.savedAt > READING_DRAFT_MAX_AGE_MS) {
      if (isLegacyScratchDraft) {
        window.localStorage.removeItem(legacyReadingDraftStorageKey(learnerId))
      } else {
        clearReadingWorkshopDraft(learnerId, resolvedScopeId)
      }
      return null
    }
    if (isLegacyScratchDraft) {
      writeReadingWorkshopDraft(draft)
      window.localStorage.removeItem(legacyReadingDraftStorageKey(learnerId))
    }
    return draft
  } catch (error) {
    console.warn('Reading workshop draft recovery failed:', error)
    return null
  }
}

export function writeReadingWorkshopDraft(draft: ReadingWorkshopDraftV1): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(readingDraftStorageKey(draft.learnerId, draft.scopeId), JSON.stringify({
      ...draft,
      savedAt: Date.now(),
    }))
    window.localStorage.setItem(activeReadingDraftScopeKey(draft.learnerId), draft.scopeId)
  } catch (error) {
    console.warn('Reading workshop draft save failed:', error)
  }
}

export function clearReadingWorkshopDraft(
  learnerId: string,
  scopeId = SCRATCH_READING_DRAFT_SCOPE,
): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(readingDraftStorageKey(learnerId, scopeId))
    if (window.localStorage.getItem(activeReadingDraftScopeKey(learnerId)) === scopeId) {
      window.localStorage.removeItem(activeReadingDraftScopeKey(learnerId))
    }
  } catch (error) {
    console.warn('Reading workshop draft cleanup failed:', error)
  }
}

export function normalizeReadingWorkshopDraft(
  value: unknown,
  learnerId: string,
  expectedScopeId = SCRATCH_READING_DRAFT_SCOPE,
): ReadingWorkshopDraftV1 | null {
  if (!isRecord(value) || ![1, 2, READING_DRAFT_VERSION].includes(Number(value.version)) || value.learnerId !== learnerId) return null
  const scopeId = value.version === 1
    ? SCRATCH_READING_DRAFT_SCOPE
    : typeof value.scopeId === 'string' ? value.scopeId : ''
  if (!scopeId || scopeId !== expectedScopeId) return null
  if (typeof value.savedAt !== 'number' || !Number.isFinite(value.savedAt)) return null
  if (!isReadingMaterialDraft(value.material)) return null
  if (!isExtensiveNotesDraft(value.extensiveNotes)) return null
  if (!isIntensiveNotesDraft(value.intensiveNotesBySentenceId)) return null

  const workspace = isReadingWorkspace(value.workspace) ? value.workspace : 'input'
  const selectedSentenceId = typeof value.selectedSentenceId === 'string' ? value.selectedSentenceId : null
  const activeMaterialId = typeof value.activeMaterialId === 'string' ? value.activeMaterialId : null
  const activeMaterialRecord = isReadingMaterialHistoryDraft(value.activeMaterialRecord)
    ? value.activeMaterialRecord
    : null
  const titleMode: ReadingDraftTitleMode = value.titleMode === 'auto' || value.titleMode === 'user'
    ? value.titleMode
    : 'empty'
  const titleSuggestionStatus: ReadingDraftTitleSuggestionStatus = (
    value.titleSuggestionStatus === 'checking'
    || value.titleSuggestionStatus === 'suggested'
    || value.titleSuggestionStatus === 'incomplete'
    || value.titleSuggestionStatus === 'error'
  ) ? value.titleSuggestionStatus : 'idle'
  const recoveredClientAttemptId = typeof value.clientAttemptId === 'string'
    ? value.clientAttemptId.trim()
    : ''
  const hasValidRecoveredAttemptId = recoveredClientAttemptId.length >= 8 && recoveredClientAttemptId.length <= 100
  const completionResult = isReadingCompletionResult(value.completionResult) ? value.completionResult : null
  // v1 persisted an attempt id but not whether it had already reached the server.
  // Treat a valid legacy id as potentially submitted so any evidence edit rotates
  // it instead of risking an idempotent replay of older evidence.
  const attemptSubmitted = value.attemptSubmitted === true
    || value.completeStatus === 'completed'
    || Boolean(completionResult)
    || (value.version === 1 && hasValidRecoveredAttemptId)

  return {
    version: READING_DRAFT_VERSION,
    learnerId,
    scopeId,
    savedAt: value.savedAt,
    workspace,
    material: value.material,
    extensiveNotes: value.extensiveNotes,
    intensiveNotesBySentenceId: value.intensiveNotesBySentenceId,
    sentenceAnalysisBySentenceId: normalizeSentenceAnalysisResults(value.sentenceAnalysisBySentenceId),
    selectedSentenceId,
    selectedGrammarOptionIds: stringArray(value.selectedGrammarOptionIds),
    openedGrammarTopics: stringArray(value.openedGrammarTopics),
    coachThreadId: typeof value.coachThreadId === 'string' ? value.coachThreadId : null,
    coachMessages: normalizeCoachMessages(value.coachMessages),
    coachDraft: typeof value.coachDraft === 'string' ? value.coachDraft : '',
    activeMaterialId,
    activeMaterialRecord,
    saveStatus: value.saveStatus === 'saved' && activeMaterialId ? 'saved' : 'idle',
    titleMode,
    titleSuggestionStatus,
    autoTitleSourceText: typeof value.autoTitleSourceText === 'string' ? value.autoTitleSourceText : '',
    clientAttemptId: hasValidRecoveredAttemptId
      ? recoveredClientAttemptId
      : createClientAttemptId(),
    attemptSubmitted,
    lastSubmittedEvidenceFingerprint: typeof value.lastSubmittedEvidenceFingerprint === 'string'
      ? value.lastSubmittedEvidenceFingerprint
      : null,
    completeStatus: completionResult ? 'completed' : attemptSubmitted ? 'error' : 'idle',
    completionResult,
  }
}

export function deriveReadingSourceLabel({
  record,
  initialMaterialId,
  initialSourceLabel,
}: {
  record: ReadingMaterialHistoryItem | null
  initialMaterialId: string | null
  initialSourceLabel: string | null
}): string | null {
  if (!record) return null
  if (initialSourceLabel && record.id === initialMaterialId) return initialSourceLabel

  const sourceTitle = record.generation_context?.source_title?.trim()
  const unitTitle = record.generation_context?.unit_title?.trim()
  if (sourceTitle && unitTitle) return `${sourceTitle} · ${unitTitle}`
  if (sourceTitle) return sourceTitle
  if (unitTitle) return unitTitle
  if (record.source === 'reading_workshop') return '阅读工作坊'
  if (record.source === 'unit_llm_generation') return 'AI 生成阅读材料'
  return record.source.trim() || null
}

function readingDraftStorageKey(learnerId: string, scopeId: string): string {
  return `binnagent:reading-workshop-draft:v${READING_DRAFT_VERSION}:${learnerId}:${encodeURIComponent(scopeId)}`
}

function legacyReadingDraftStorageKey(learnerId: string): string {
  return `binnagent:reading-workshop-draft:v1:${learnerId}`
}

function activeReadingDraftScopeKey(learnerId: string): string {
  return `binnagent:reading-workshop-draft:v${READING_DRAFT_VERSION}:${learnerId}:active-scope`
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function isReadingMaterialDraft(value: unknown): value is ReadingMaterial {
  if (!isRecord(value)) return false
  return typeof value.title === 'string'
    && typeof value.text === 'string'
    && (value.level === 'junior' || value.level === 'cet4' || value.level === 'cet6' || value.level === 'general')
    && (value.goal === 'intensive' || value.goal === 'extensive' || value.goal === 'mixed')
    && (value.material_type === undefined || value.material_type === 'dialogue' || value.material_type === 'passage')
}

function isExtensiveNotesDraft(value: unknown): value is ReadingDraftExtensiveNotes {
  return isRecord(value)
    && typeof value.gist === 'string'
    && typeof value.attitude === 'string'
    && typeof value.paragraphFunction === 'string'
    && typeof value.centralSentence === 'string'
}

function isIntensiveNotesDraft(value: unknown): value is Record<string, ReadingDraftIntensiveNotes> {
  if (!isRecord(value)) return false
  return Object.values(value).every((notes) => (
    isRecord(notes)
    && typeof notes.mainStructure === 'string'
    && typeof notes.phraseNotes === 'string'
    && typeof notes.evidenceNote === 'string'
  ))
}

function isReadingMaterialHistoryDraft(value: unknown): value is ReadingMaterialHistoryItem {
  return isRecord(value)
    && typeof value.id === 'string'
    && typeof value.learner_id === 'string'
    && (typeof value.title === 'string' || value.title === null || value.title === undefined)
    && typeof value.text === 'string'
    && (value.level === 'junior' || value.level === 'cet4' || value.level === 'cet6' || value.level === 'general')
    && (value.goal === 'intensive' || value.goal === 'extensive' || value.goal === 'mixed')
    && (value.material_type === 'dialogue' || value.material_type === 'passage')
    && typeof value.source === 'string'
    && typeof value.word_count === 'number'
    && typeof value.sentence_count === 'number'
    && typeof value.created_at === 'string'
    && typeof value.updated_at === 'string'
}

function isReadingCompletionResult(value: unknown): value is ReadingMaterialCompleteResponse {
  return isRecord(value)
    && typeof value.material_id === 'string'
    && typeof value.attempt_id === 'string'
    && typeof value.reading_value === 'number'
    && typeof value.message === 'string'
}

function normalizeSentenceAnalysisResults(value: unknown): Record<string, ReadingSentenceAnalysisResponse> {
  if (!isRecord(value)) return {}
  return Object.fromEntries(
    Object.entries(value).filter((entry): entry is [string, ReadingSentenceAnalysisResponse] => (
      isReadingSentenceAnalysisResult(entry[1])
    ))
  )
}

function isReadingSentenceAnalysisResult(value: unknown): value is ReadingSentenceAnalysisResponse {
  return isRecord(value)
    && typeof value.material_id === 'string'
    && typeof value.sentence_id === 'string'
    && typeof value.sentence === 'string'
    && typeof value.event_id === 'string'
    && value.workflow_stage === 'review'
    && (value.outcome === 'SUCCESS' || value.outcome === 'UNSUCCESSFUL' || value.outcome === 'NO_ATTEMPT')
    && typeof value.score === 'number'
    && typeof value.confidence === 'number'
    && typeof value.feedback === 'string'
    && isRecord(value.correct_analysis)
    && isRecord(value.teaching)
    && Array.isArray(value.can_do_points)
    && Array.isArray(value.error_patterns)
    && typeof value.mastery_updated === 'boolean'
}

function isReadingWorkspace(value: unknown): value is ReadingWorkspace {
  return value === 'input' || value === 'extensive' || value === 'intensive' || value === 'review'
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

function normalizeCoachMessages(value: unknown): ReadingDraftCoachMessage[] {
  if (!Array.isArray(value)) return []
  const messages: ReadingDraftCoachMessage[] = []
  for (const message of value) {
    if (
      !isRecord(message)
      || typeof message.id !== 'string'
      || (message.role !== 'user' && message.role !== 'assistant')
      || typeof message.content !== 'string'
    ) continue
    messages.push({ id: message.id, role: message.role, content: message.content })
  }
  return messages.slice(-50)
}
