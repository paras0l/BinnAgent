import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import {
  ArrowLeft,
  BookOpenCheck,
  CheckCircle2,
  ClipboardList,
  ExternalLink,
  FileText,
  Gauge,
  History,
  Highlighter,
  Languages,
  Layers3,
  ListChecks,
  LoaderCircle,
  MessageCircle,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  PencilLine,
  RotateCw,
  Save,
  Send,
  SearchCheck,
  Timer,
} from 'lucide-react'
import { FeatureHero } from '@/components/layout/FeatureHero'
import { PageShell } from '@/components/layout/PageShell'
import type { WorkspaceTab } from '@/components/layout/WorkspaceTabs'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { FormField } from '@/components/ui/FormField'
import { Select } from '@/components/ui/Select'
import { StatusBanner } from '@/components/ui/StatusBanner'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import { useFocusTrap } from '@/hooks/useFocusTrap'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import {
  READING_GOAL_LABELS,
  READING_LEVEL_LABELS,
  buildReadingCompletionPayload,
  buildReadingCompletionState,
  buildKeywordCandidates,
  buildSentenceFocusHints,
  countEnglishWords,
  estimateReadingMinutes,
  fingerprintReadingCompletionPayload,
  sentenceAnalysisFailureFromResponse,
  splitReadingSentences,
  uniqueList,
  type ReadingKeywordCandidate,
  type ReadingLevel,
  type ReadingMaterial,
  type ReadingMaterialCompleteResponse,
  type ReadingMaterialHistoryItem,
  type ReadingSentence,
  type ReadingSentenceAnalysisResponse,
  type ReadingSentenceHint,
  type ReadingTitleSuggestionResponse,
  type ReadingTrainingGoal,
  type ReadingWorkspace,
  type SentenceAnalysisFailure,
} from '@/data/readingWorkshop'
import {
  READING_DRAFT_VERSION,
  clearReadingWorkshopDraft,
  createClientAttemptId,
  deriveReadingSourceLabel,
  readReadingWorkshopDraft,
  readingDraftPersistenceAction,
  readingMaterialDraftScope,
  writeReadingWorkshopDraft,
  type ReadingNavigationBlocker,
  type ReadingNavigationBlockerChangeHandler,
  type ReadingWorkshopDraftV1,
} from '@/data/readingWorkshopSession'
import type { Learner, LearnerProfile } from '@/types'
import { buildReadingCoachContext } from '@/utils/readingCoachContext'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface ReadingWorkshopPageProps {
  learner: Learner
  onBack: () => void
  backLabel?: string
  initialMaterial?: ReadingMaterial | ReadingMaterialHistoryItem
  initialMaterialId?: string | null
  initialSourceLabel?: string | null
  learnerProfile?: LearnerProfile | null
  readingTrackMode?: boolean
  onNavigationBlockerChange?: ReadingNavigationBlockerChangeHandler
}

interface ExtensiveNotes {
  gist: string
  attitude: string
  paragraphFunction: string
  centralSentence: string
}

interface IntensiveNotes {
  mainStructure: string
  phraseNotes: string
  evidenceNote: string
}

type IntensiveNotesBySentenceId = Record<string, IntensiveNotes>

type PendingMaterialSwitch =
  | { kind: 'sample' }
  | { kind: 'history'; item: ReadingMaterialHistoryItem }
  | { kind: 'generated'; item: ReadingMaterialHistoryItem }
  | { kind: 'generate' }
  | { kind: 'back' }
  | { kind: 'external-navigation'; navigate: () => void }
  | { kind: 'edit'; text: string }

type TitleMode = 'empty' | 'auto' | 'user'
type TitleSuggestionStatus = 'idle' | 'checking' | 'suggested' | 'incomplete' | 'error'
type MaterialHistoryStatus = 'idle' | 'loading' | 'ready' | 'error'
type MaterialSaveStatus = 'idle' | 'saving' | 'saved' | 'error'
type MaterialCompleteStatus = 'idle' | 'saving' | 'completed' | 'error'
type ReadingCoachMessage = { id: string; role: 'user' | 'assistant'; content: string }

interface PendingCoachRequest {
  controller: AbortController
  message: string
  revision: number
  userMessageId: string
}

const SAMPLE_TEXT = `Many students believe that reading faster simply means moving their eyes quickly across a page. However, effective readers do more than race through words. They first notice the title, predict the topic, and look for sentences that show the writer's main point. When a sentence becomes difficult, they slow down, find the main verb, and separate extra information from the core meaning.`

const EMPTY_MATERIAL: ReadingMaterial = {
  title: '',
  text: '',
  level: 'general',
  goal: 'mixed',
  material_type: 'passage',
}

const EMPTY_EXTENSIVE_NOTES: ExtensiveNotes = {
  gist: '',
  attitude: '',
  paragraphFunction: '',
  centralSentence: '',
}

const EMPTY_INTENSIVE_NOTES: IntensiveNotes = {
  mainStructure: '',
  phraseNotes: '',
  evidenceNote: '',
}

const WORKSPACE_TABS: WorkspaceTab<ReadingWorkspace>[] = [
  { id: 'input', label: '材料输入', description: '标题与原文', icon: <FileText className="h-4 w-4" /> },
  { id: 'extensive', label: '泛读模式', description: '主旨与结构', icon: <Gauge className="h-4 w-4" /> },
  { id: 'intensive', label: '精读模式', description: '句子与语法', icon: <Highlighter className="h-4 w-4" /> },
  { id: 'review', label: '沉淀复盘', description: '本次记录', icon: <ClipboardList className="h-4 w-4" /> },
]

export function ReadingWorkshopPage({
  learner,
  onBack,
  backLabel = '返回探索',
  initialMaterial,
  initialMaterialId = null,
  initialSourceLabel = null,
  learnerProfile,
  readingTrackMode = false,
  onNavigationBlockerChange,
}: ReadingWorkshopPageProps) {
  const hasExplicitInitialMaterial = initialMaterial !== undefined
  const hasInitialMaterial = Boolean(initialMaterial?.text.trim())
  const initialDraftScopeId = readingMaterialDraftScope(
    initialMaterialId ?? (isReadingMaterialHistoryItem(initialMaterial) ? initialMaterial.id : null)
  )
  const [storedDraft] = useState<ReadingWorkshopDraftV1 | null>(() => (
    readReadingWorkshopDraft(learner.id, hasExplicitInitialMaterial ? initialDraftScopeId : undefined)
  ))
  const recoveredDraft = hasExplicitInitialMaterial && storedDraft?.material.text !== initialMaterial?.text
    ? null
    : storedDraft
  const initialMaterialRecord = isReadingMaterialHistoryItem(initialMaterial) ? initialMaterial : null
  const recoveredMaterialRecord = hasExplicitInitialMaterial ? null : recoveredDraft?.activeMaterialRecord ?? null
  const resolvedInitialMaterialId = initialMaterialId
    ?? initialMaterialRecord?.id
    ?? recoveredDraft?.activeMaterialId
    ?? null
  const seededMaterial = hasExplicitInitialMaterial
    ? { ...initialMaterial, material_type: initialMaterial?.material_type ?? 'passage' } as ReadingMaterial
    : recoveredDraft?.material ?? EMPTY_MATERIAL
  const [workspace, setWorkspace] = useState<ReadingWorkspace>(() => (
    seededMaterial.text.trim() ? recoveredDraft?.workspace ?? 'input' : 'input'
  ))
  const [material, setMaterial] = useState<ReadingMaterial>(() => (
    seededMaterial
  ))
  const [extensiveNotes, setExtensiveNotes] = useState<ExtensiveNotes>(
    recoveredDraft?.extensiveNotes ?? EMPTY_EXTENSIVE_NOTES
  )
  const [intensiveNotesBySentenceId, setIntensiveNotesBySentenceId] = useState<IntensiveNotesBySentenceId>(
    recoveredDraft?.intensiveNotesBySentenceId ?? {}
  )
  const [sentenceAnalysisBySentenceId, setSentenceAnalysisBySentenceId] = useState<Record<string, ReadingSentenceAnalysisResponse>>(
    recoveredDraft?.sentenceAnalysisBySentenceId ?? {}
  )
  const [sentenceAnalysisStatus, setSentenceAnalysisStatus] = useState<'idle' | 'submitting' | 'error'>('idle')
  const [sentenceAnalysisFailure, setSentenceAnalysisFailure] = useState<SentenceAnalysisFailure | null>(null)
  const [titleMode, setTitleMode] = useState<TitleMode>(
    recoveredDraft?.titleMode ?? (hasInitialMaterial && initialMaterial?.title ? 'auto' : 'empty')
  )
  const [titleSuggestionStatus, setTitleSuggestionStatus] = useState<TitleSuggestionStatus>(
    recoveredDraft?.titleSuggestionStatus
      ?? (hasInitialMaterial && initialMaterial?.title ? 'suggested' : 'idle')
  )
  const [autoTitleSourceText, setAutoTitleSourceText] = useState(
    recoveredDraft?.autoTitleSourceText ?? (hasInitialMaterial ? initialMaterial?.text ?? '' : '')
  )
  const [materialHistory, setMaterialHistory] = useState<ReadingMaterialHistoryItem[]>([])
  const [activeMaterialId, setActiveMaterialId] = useState<string | null>(resolvedInitialMaterialId)
  const [activeMaterialRecord, setActiveMaterialRecord] = useState<ReadingMaterialHistoryItem | null>(
    initialMaterialRecord ?? recoveredMaterialRecord
  )
  const [historyStatus, setHistoryStatus] = useState<MaterialHistoryStatus>('idle')
  const [saveStatus, setSaveStatus] = useState<MaterialSaveStatus>(
    recoveredDraft?.saveStatus ?? (resolvedInitialMaterialId ? 'saved' : 'idle')
  )
  const [completeStatus, setCompleteStatus] = useState<MaterialCompleteStatus>(
    recoveredDraft?.completeStatus ?? 'idle'
  )
  const [completionResult, setCompletionResult] = useState<ReadingMaterialCompleteResponse | null>(
    recoveredDraft?.completionResult ?? null
  )
  const [selectedSentenceId, setSelectedSentenceId] = useState<string | null>(recoveredDraft?.selectedSentenceId ?? null)
  const [generationTopic, setGenerationTopic] = useState(learnerProfile?.interest_topics?.[0] ?? '')
  const [generationStatus, setGenerationStatus] = useState<'idle' | 'generating' | 'error'>('idle')
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)
  const [isCoachCollapsed, setIsCoachCollapsed] = useState(true)
  const [coachThreadId, setCoachThreadId] = useState<string | null>(recoveredDraft?.coachThreadId ?? null)
  const [coachMessages, setCoachMessages] = useState<ReadingCoachMessage[]>(recoveredDraft?.coachMessages ?? [])
  const [coachDraft, setCoachDraft] = useState(recoveredDraft?.coachDraft ?? '')
  const [coachStatus, setCoachStatus] = useState<'idle' | 'sending' | 'error'>('idle')
  const [activeTextSelection, setActiveTextSelection] = useState<string | null>(null)
  const [pendingMaterialSwitch, setPendingMaterialSwitch] = useState<PendingMaterialSwitch | null>(null)
  const [queuedGeneratedMaterial, setQueuedGeneratedMaterial] = useState<ReadingMaterialHistoryItem | null>(null)
  const [showDraftRecoveryNotice, setShowDraftRecoveryNotice] = useState(Boolean(recoveredDraft))
  const [clientAttemptId, setClientAttemptId] = useState(
    recoveredDraft?.clientAttemptId ?? createClientAttemptId()
  )
  const [attemptSubmitted, setAttemptSubmitted] = useState(recoveredDraft?.attemptSubmitted ?? false)
  const [lastSubmittedEvidenceFingerprint, setLastSubmittedEvidenceFingerprint] = useState<string | null>(
    recoveredDraft?.lastSubmittedEvidenceFingerprint ?? null
  )
  const [draftScopeId, setDraftScopeId] = useState(recoveredDraft?.scopeId ?? initialDraftScopeId)
  const materialRevisionRef = useRef(0)
  const completionRevisionRef = useRef(0)
  const dataRevisionRef = useRef(0)
  const coachRevisionRef = useRef(0)
  const saveRequestSequenceRef = useRef(0)
  const completionRequestSequenceRef = useRef(0)
  const generationRequestSequenceRef = useRef(0)
  const saveAbortControllerRef = useRef<AbortController | null>(null)
  const completionAbortControllerRef = useRef<AbortController | null>(null)
  const generationAbortControllerRef = useRef<AbortController | null>(null)
  const sentenceAnalysisAttemptIdsRef = useRef<Record<string, string>>({})
  const sentenceAnalysisRequestRef = useRef<{
    controller: AbortController
    materialRevision: number
    sentenceId: string
  } | null>(null)
  const coachRequestRef = useRef<PendingCoachRequest | null>(null)
  const pendingMaterialSwitchRef = useRef(pendingMaterialSwitch)
  const skipPersistOnUnmountRef = useRef(false)
  const readingTimeBudget = learnerProfile?.daily_time_budget_minutes ?? 15

  const sentences = useMemo(() => splitReadingSentences(material.text), [material.text])
  const keywordCandidates = useMemo(() => buildKeywordCandidates(material.text), [material.text])
  const wordCount = useMemo(() => countEnglishWords(material.text), [material.text])
  const estimatedMinutes = useMemo(() => estimateReadingMinutes(material.text, material.level), [material.level, material.text])
  const selectedSentence = useMemo(
    () => selectedSentenceId
      ? sentences.find((sentence) => sentence.id === selectedSentenceId) ?? null
      : null,
    [selectedSentenceId, sentences]
  )
  const intensiveNotes = useMemo(
    () => selectedSentence ? intensiveNotesBySentenceId[selectedSentence.id] ?? EMPTY_INTENSIVE_NOTES : EMPTY_INTENSIVE_NOTES,
    [intensiveNotesBySentenceId, selectedSentence]
  )
  const analyzedSentences = useMemo(
    () => sentences.filter((sentence) => Boolean(sentenceAnalysisBySentenceId[sentence.id])),
    [sentenceAnalysisBySentenceId, sentences]
  )
  const selectedSentenceAnalysis = selectedSentence
    ? sentenceAnalysisBySentenceId[selectedSentence.id] ?? null
    : null
  const selectedSentenceHints = useMemo(
    () => buildSentenceFocusHints(selectedSentence?.text ?? ''),
    [selectedSentence]
  )
  const canUseMaterial = material.text.trim().length > 0
  const hasExtensiveEvidence = Boolean(extensiveNotes.gist.trim() && extensiveNotes.centralSentence.trim())
  const hasSessionWork = Boolean(
    extensiveNotes.gist.trim()
    || extensiveNotes.attitude.trim()
    || extensiveNotes.paragraphFunction.trim()
    || extensiveNotes.centralSentence.trim()
    || Object.values(intensiveNotesBySentenceId).some(hasAnyIntensiveNote)
    || Object.keys(sentenceAnalysisBySentenceId).length > 0
    || coachMessages.length
  )
  const hasUnsavedMaterial = Boolean(
    saveStatus !== 'saved' && (material.text.trim() || material.title.trim())
  )
  const hasDataAtRisk = Boolean(
    hasSessionWork
    || coachDraft.trim()
    || hasUnsavedMaterial
    || saveStatus === 'saving'
    || completeStatus === 'saving'
    || generationStatus === 'generating'
    || sentenceAnalysisStatus === 'submitting'
  )
  const activeSourceLabel = useMemo(() => deriveReadingSourceLabel({
    record: activeMaterialRecord,
    initialMaterialId: resolvedInitialMaterialId,
    initialSourceLabel,
  }), [activeMaterialRecord, initialSourceLabel, resolvedInitialMaterialId])
  const completionState = useMemo(() => buildReadingCompletionState({
    hasMaterial: canUseMaterial,
    hasExtensiveEvidence,
    analyzedSentenceCount: analyzedSentences.length,
    goal: material.goal,
    isRecorded: completeStatus === 'completed',
  }), [analyzedSentences.length, canUseMaterial, completeStatus, hasExtensiveEvidence, material.goal])

  useEffect(() => {
    if (!onNavigationBlockerChange) return
    const blocker: ReadingNavigationBlocker = (navigate) => {
      if (!hasDataAtRisk) {
        skipPersistOnUnmountRef.current = true
        clearReadingWorkshopDraft(learner.id, draftScopeId)
        return false
      }
      setPendingMaterialSwitch({ kind: 'external-navigation', navigate })
      return true
    }
    onNavigationBlockerChange(blocker)
    return () => onNavigationBlockerChange(null)
  }, [draftScopeId, hasDataAtRisk, learner.id, onNavigationBlockerChange])

  const invalidateCoachRequest = useCallback((preserveQuestion: boolean) => {
    coachRevisionRef.current += 1
    const pending = coachRequestRef.current
    coachRequestRef.current = null
    pending?.controller.abort()
    if (pending) {
      setCoachMessages((current) => current.filter((item) => item.id !== pending.userMessageId))
      if (preserveQuestion) {
        setCoachDraft((current) => current.trim() ? current : pending.message)
      }
    }
    setCoachStatus('idle')
  }, [])

  const invalidateCompletion = useCallback(() => {
    completionRevisionRef.current += 1
    completionRequestSequenceRef.current += 1
    completionAbortControllerRef.current?.abort()
    completionAbortControllerRef.current = null
  }, [])

  const markEvidenceMutation = useCallback(() => {
    dataRevisionRef.current += 1
    invalidateCompletion()
    if (attemptSubmitted) {
      setClientAttemptId(createClientAttemptId())
      setAttemptSubmitted(false)
      setLastSubmittedEvidenceFingerprint(null)
    }
    setCompleteStatus('idle')
    setCompletionResult(null)
  }, [attemptSubmitted, invalidateCompletion])

  const markMaterialMutation = useCallback((preserveCoachQuestion: boolean) => {
    materialRevisionRef.current += 1
    dataRevisionRef.current += 1
    saveRequestSequenceRef.current += 1
    saveAbortControllerRef.current?.abort()
    saveAbortControllerRef.current = null
    sentenceAnalysisRequestRef.current?.controller.abort()
    sentenceAnalysisRequestRef.current = null
    setSentenceAnalysisStatus('idle')
    setSentenceAnalysisFailure(null)
    invalidateCompletion()
    invalidateCoachRequest(preserveCoachQuestion)
    if (attemptSubmitted) {
      setClientAttemptId(createClientAttemptId())
      setAttemptSubmitted(false)
      setLastSubmittedEvidenceFingerprint(null)
    }
    setSaveStatus('idle')
    setCompleteStatus('idle')
    setCompletionResult(null)
  }, [attemptSubmitted, invalidateCoachRequest, invalidateCompletion])

  const resetReadingSession = useCallback(() => {
    markMaterialMutation(false)
    setWorkspace('input')
    setExtensiveNotes(EMPTY_EXTENSIVE_NOTES)
    setIntensiveNotesBySentenceId({})
    setSentenceAnalysisBySentenceId({})
    setSentenceAnalysisStatus('idle')
    setSentenceAnalysisFailure(null)
    sentenceAnalysisAttemptIdsRef.current = {}
    setSelectedSentenceId(null)
    setCompleteStatus('idle')
    setCompletionResult(null)
    setCoachThreadId(null)
    setCoachMessages([])
    setCoachDraft('')
    setCoachStatus('idle')
    setActiveTextSelection(null)
    setClientAttemptId(createClientAttemptId())
    setAttemptSubmitted(false)
    setLastSubmittedEvidenceFingerprint(null)
  }, [markMaterialMutation])

  const updateIntensiveNote = useCallback((key: keyof IntensiveNotes, value: string) => {
    if (!selectedSentence) return
    markEvidenceMutation()
    sentenceAnalysisRequestRef.current?.controller.abort()
    sentenceAnalysisRequestRef.current = null
    delete sentenceAnalysisAttemptIdsRef.current[selectedSentence.id]
    setSentenceAnalysisBySentenceId((current) => {
      if (!current[selectedSentence.id]) return current
      const next = { ...current }
      delete next[selectedSentence.id]
      return next
    })
    setSentenceAnalysisStatus('idle')
    setSentenceAnalysisFailure(null)
    setIntensiveNotesBySentenceId((current) => ({
      ...current,
      [selectedSentence.id]: {
        ...(current[selectedSentence.id] ?? EMPTY_INTENSIVE_NOTES),
        [key]: value,
      },
    }))
  }, [markEvidenceMutation, selectedSentence])

  const updateExtensiveNote = useCallback((key: keyof ExtensiveNotes, value: string) => {
    markEvidenceMutation()
    setExtensiveNotes((current) => ({ ...current, [key]: value }))
  }, [markEvidenceMutation])

  const askReadingCoach = useCallback(async () => {
    const message = coachDraft.trim()
    if (!message || coachStatus === 'sending') return

    const revision = coachRevisionRef.current
    const controller = new AbortController()
    const userMessage: ReadingCoachMessage = {
      id: `reading-coach-user-${Date.now()}`,
      role: 'user',
      content: message,
    }
    dataRevisionRef.current += 1
    setCoachMessages((current) => [...current, userMessage])
    setCoachDraft('')
    setCoachStatus('sending')
    coachRequestRef.current = {
      controller,
      message,
      revision,
      userMessageId: userMessage.id,
    }

    const isCurrentRequest = () => (
      coachRequestRef.current?.controller === controller
      && coachRevisionRef.current === revision
      && !controller.signal.aborted
    )

    try {
      const response = await fetch('/api/chat/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          learner_id: learner.id,
          message,
          thread_id: coachThreadId,
          skill_focus: 'reading',
          artifact_context: buildReadingCoachContext({
            material,
            materialId: activeMaterialId,
            workspace,
            currentSentence: selectedSentence,
            selectedText: activeTextSelection,
            extensiveNotes,
            intensiveNotes,
            grammarTopics: uniqueList(
              Object.values(sentenceAnalysisBySentenceId)
                .flatMap((result) => result.can_do_points.map((point) => point.statement))
            ),
          }),
        }),
        signal: controller.signal,
      })
      if (!response.ok) throw new Error('Reading coach request failed')
      const result = await response.json() as { reply: string; thread_id: string }
      if (!isCurrentRequest()) return
      coachRequestRef.current = null
      dataRevisionRef.current += 1
      setCoachThreadId(result.thread_id)
      setCoachMessages((current) => [...current, {
        id: `reading-coach-assistant-${Date.now()}`,
        role: 'assistant',
        content: result.reply,
      }])
      setCoachStatus('idle')
    } catch (error) {
      if (!isCurrentRequest()) return
      coachRequestRef.current = null
      console.error('Reading coach error:', error)
      setCoachMessages((current) => current.filter((item) => item.id !== userMessage.id))
      setCoachDraft(message)
      setCoachStatus('error')
    }
  }, [
    activeMaterialId,
    activeTextSelection,
    coachDraft,
    coachStatus,
    coachThreadId,
    extensiveNotes,
    intensiveNotes,
    learner.id,
    material,
    sentenceAnalysisBySentenceId,
    selectedSentence,
    workspace,
  ])

  useEffect(() => () => {
    saveAbortControllerRef.current?.abort()
    completionAbortControllerRef.current?.abort()
    generationAbortControllerRef.current?.abort()
    sentenceAnalysisRequestRef.current?.controller.abort()
    coachRequestRef.current?.controller.abort()
  }, [])

  useEffect(() => {
    pendingMaterialSwitchRef.current = pendingMaterialSwitch
  }, [pendingMaterialSwitch])

  const loadMaterialHistory = useCallback(async () => {
    setHistoryStatus('loading')
    try {
      const response = await fetch(`/api/learners/${learner.id}/reading-workshop/materials`)
      if (!response.ok) throw new Error('Failed to load reading material history')
      const data = (await response.json()) as ReadingMaterialHistoryItem[]
      setMaterialHistory(data)
      setHistoryStatus('ready')
    } catch (error) {
      console.error('Reading material history load error:', error)
      setHistoryStatus('error')
    }
  }, [learner.id])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadMaterialHistory(), 0)
    return () => window.clearTimeout(timer)
  }, [loadMaterialHistory])

  const localDraft = useMemo<ReadingWorkshopDraftV1>(() => ({
    version: READING_DRAFT_VERSION,
    learnerId: learner.id,
    scopeId: draftScopeId,
    savedAt: recoveredDraft?.savedAt ?? 0,
    workspace,
    material,
    extensiveNotes,
    intensiveNotesBySentenceId,
    sentenceAnalysisBySentenceId,
    selectedSentenceId,
    selectedGrammarOptionIds: [],
    openedGrammarTopics: [],
    coachThreadId,
    coachMessages: coachMessages.slice(-50),
    coachDraft,
    activeMaterialId,
    activeMaterialRecord,
    saveStatus: saveStatus === 'saved' ? 'saved' : 'idle',
    titleMode,
    titleSuggestionStatus,
    autoTitleSourceText,
    clientAttemptId,
    attemptSubmitted,
    lastSubmittedEvidenceFingerprint,
    completeStatus: completionResult ? 'completed' : attemptSubmitted ? 'error' : 'idle',
    completionResult,
  }), [
    activeMaterialId,
    activeMaterialRecord,
    attemptSubmitted,
    autoTitleSourceText,
    clientAttemptId,
    coachDraft,
    coachMessages,
    coachThreadId,
    completionResult,
    draftScopeId,
    extensiveNotes,
    intensiveNotesBySentenceId,
    sentenceAnalysisBySentenceId,
    learner.id,
    lastSubmittedEvidenceFingerprint,
    material,
    recoveredDraft?.savedAt,
    saveStatus,
    selectedSentenceId,
    titleMode,
    titleSuggestionStatus,
    workspace,
  ])
  const shouldPersistLocalDraft = Boolean(
    material.text.trim()
    || material.title.trim()
    || hasSessionWork
    || coachDraft.trim()
  )
  const latestLocalDraftRef = useRef(localDraft)
  const shouldPersistLocalDraftRef = useRef(shouldPersistLocalDraft)
  useEffect(() => {
    latestLocalDraftRef.current = localDraft
    shouldPersistLocalDraftRef.current = shouldPersistLocalDraft
  }, [localDraft, shouldPersistLocalDraft])
  const persistLatestLocalDraft = useCallback(() => {
    const latestDraft = latestLocalDraftRef.current
    const action = readingDraftPersistenceAction({
      skipPersist: skipPersistOnUnmountRef.current,
      hasContent: shouldPersistLocalDraftRef.current,
    })
    if (action === 'skip') return
    if (action === 'write') {
      writeReadingWorkshopDraft(latestDraft)
    } else {
      clearReadingWorkshopDraft(learner.id, latestDraft.scopeId)
    }
  }, [learner.id])

  useEffect(() => {
    const timer = window.setTimeout(persistLatestLocalDraft, 350)
    return () => window.clearTimeout(timer)
  }, [localDraft, persistLatestLocalDraft])

  useEffect(() => {
    const handlePageHide = () => persistLatestLocalDraft()
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') persistLatestLocalDraft()
    }
    window.addEventListener('pagehide', handlePageHide)
    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      window.removeEventListener('pagehide', handlePageHide)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      persistLatestLocalDraft()
    }
  }, [persistLatestLocalDraft])

  useEffect(() => {
    if (!hasDataAtRisk) return
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      persistLatestLocalDraft()
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [hasDataAtRisk, persistLatestLocalDraft])

  const moveDraftScope = useCallback((
    nextScopeId: string,
    migratedDraftPatch?: Partial<ReadingWorkshopDraftV1>,
  ) => {
    const currentScopeId = latestLocalDraftRef.current.scopeId
    if (currentScopeId === nextScopeId) return
    const movedDraft = {
      ...latestLocalDraftRef.current,
      ...migratedDraftPatch,
      scopeId: nextScopeId,
    }
    latestLocalDraftRef.current = movedDraft
    if (migratedDraftPatch) {
      writeReadingWorkshopDraft(movedDraft)
    }
    clearReadingWorkshopDraft(learner.id, currentScopeId)
    setDraftScopeId(nextScopeId)
  }, [learner.id])

  const saveCurrentMaterial = useCallback(async () => {
    const text = material.text.trim()
    if (!text) return null

    saveAbortControllerRef.current?.abort()
    const controller = new AbortController()
    const requestSequence = ++saveRequestSequenceRef.current
    const materialRevision = materialRevisionRef.current
    saveAbortControllerRef.current = controller
    const isCurrentRequest = () => (
      saveRequestSequenceRef.current === requestSequence
      && materialRevisionRef.current === materialRevision
      && !controller.signal.aborted
    )
    setSaveStatus('saving')
    try {
      const response = await fetch(`/api/learners/${learner.id}/reading-workshop/materials`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: material.title.trim() || null,
          text,
          level: material.level,
          goal: material.goal,
          material_type: material.material_type ?? 'passage',
          curriculum_node_id: activeMaterialRecord?.curriculum_node_id ?? null,
        }),
        signal: controller.signal,
      })
      if (!response.ok) throw new Error('Failed to save reading material')
      const saved = (await response.json()) as ReadingMaterialHistoryItem
      if (!isCurrentRequest()) return null
      moveDraftScope(readingMaterialDraftScope(saved.id), {
        activeMaterialId: saved.id,
        activeMaterialRecord: saved,
        saveStatus: 'saved',
      })
      setActiveMaterialId(saved.id)
      setActiveMaterialRecord(saved)
      setMaterialHistory((current) => [
        saved,
        ...current.filter((item) => item.id !== saved.id),
      ].slice(0, 20))
      setSaveStatus('saved')
      return saved
    } catch (error) {
      if (!isCurrentRequest()) return null
      console.error('Reading material save error:', error)
      setSaveStatus('error')
      return null
    } finally {
      if (saveAbortControllerRef.current === controller) {
        saveAbortControllerRef.current = null
      }
    }
  }, [activeMaterialRecord, learner.id, material.goal, material.level, material.material_type, material.text, material.title, moveDraftScope])

  const submitSentenceAnalysis = useCallback(async (unableToAnalyze: boolean) => {
    if (!selectedSentence || sentenceAnalysisStatus === 'submitting') return
    const controller = new AbortController()
    const requestMaterialRevision = materialRevisionRef.current
    sentenceAnalysisRequestRef.current?.controller.abort()
    sentenceAnalysisRequestRef.current = {
      controller,
      materialRevision: requestMaterialRevision,
      sentenceId: selectedSentence.id,
    }
    const isCurrentRequest = () => (
      sentenceAnalysisRequestRef.current?.controller === controller
      && sentenceAnalysisRequestRef.current.materialRevision === materialRevisionRef.current
      && sentenceAnalysisRequestRef.current.sentenceId === selectedSentence.id
      && !controller.signal.aborted
    )
    setSentenceAnalysisStatus('submitting')
    setSentenceAnalysisFailure(null)
    let materialId = activeMaterialId
    if (!materialId || saveStatus !== 'saved') {
      const saved = await saveCurrentMaterial()
      if (!isCurrentRequest()) return
      if (!saved) {
        setSentenceAnalysisStatus('error')
        setSentenceAnalysisFailure({
          title: '材料保存失败',
          message: '句子分析前需要先保存当前材料。你的作答仍保留在本地，可以直接重试。',
        })
        return
      }
      materialId = saved.id
    }
    const attemptId = sentenceAnalysisAttemptIdsRef.current[selectedSentence.id]
      ?? createClientAttemptId()
    sentenceAnalysisAttemptIdsRef.current[selectedSentence.id] = attemptId
    try {
      const response = await fetch(
        `/api/learners/${learner.id}/reading-workshop/materials/${materialId}/sentence-analysis`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            sentence_id: selectedSentence.id,
            client_attempt_id: attemptId,
            unable_to_analyze: unableToAnalyze,
            analysis: {
              main_structure: intensiveNotes.mainStructure,
              phrase_notes: intensiveNotes.phraseNotes,
              evidence_note: intensiveNotes.evidenceNote,
            },
          }),
          signal: controller.signal,
        }
      )
      if (!response.ok) {
        const failure = await sentenceAnalysisFailureFromResponse(response)
        throw Object.assign(new Error(failure.message), { failure })
      }
      const result = (await response.json()) as ReadingSentenceAnalysisResponse
      if (!isCurrentRequest()) return
      setSentenceAnalysisBySentenceId((current) => ({
        ...current,
        [selectedSentence.id]: result,
      }))
      setSentenceAnalysisStatus('idle')
      setSentenceAnalysisFailure(null)
      setWorkspace('review')
    } catch (error) {
      if (!isCurrentRequest()) return
      console.error('Reading sentence analysis error:', error)
      setSentenceAnalysisStatus('error')
      const failure = (
        typeof error === 'object'
        && error !== null
        && 'failure' in error
      ) ? (error as { failure: SentenceAnalysisFailure }).failure : {
        title: '无法连接句子分析服务',
        message: '请检查网络或后端服务后直接重试，你的作答仍保留在本地。',
      }
      setSentenceAnalysisFailure(failure)
    } finally {
      if (sentenceAnalysisRequestRef.current?.controller === controller) {
        sentenceAnalysisRequestRef.current = null
      }
    }
  }, [
    activeMaterialId,
    intensiveNotes.evidenceNote,
    intensiveNotes.mainStructure,
    intensiveNotes.phraseNotes,
    learner.id,
    saveCurrentMaterial,
    saveStatus,
    selectedSentence,
    sentenceAnalysisStatus,
  ])

  useEffect(() => {
    const text = material.text.trim()
    if (titleMode === 'user') return
    if (!text) return
    if (titleMode === 'auto' && autoTitleSourceText === text) return

    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setTitleSuggestionStatus('checking')
      fetch('/api/reading-workshop/title-suggestion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
        signal: controller.signal,
      })
        .then((response) => {
          if (!response.ok) throw new Error('Failed to suggest reading title')
          return response.json() as Promise<ReadingTitleSuggestionResponse>
        })
        .then((data) => {
          if (!data.is_complete || !data.suggested_title) {
            if (titleMode === 'auto') {
              markMaterialMutation(true)
              setMaterial((current) => ({ ...current, title: '' }))
              setTitleMode('empty')
              setAutoTitleSourceText('')
            }
            setTitleSuggestionStatus('incomplete')
            return
          }
          markMaterialMutation(true)
          setMaterial((current) => ({ ...current, title: data.suggested_title ?? current.title }))
          setTitleMode('auto')
          setAutoTitleSourceText(text)
          setTitleSuggestionStatus('suggested')
        })
        .catch((error) => {
          if (error instanceof DOMException && error.name === 'AbortError') return
          console.error('Reading title suggestion error:', error)
          setTitleSuggestionStatus('error')
        })
    }, 700)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [autoTitleSourceText, markMaterialMutation, material.text, titleMode])

  const openWorkspace = (nextWorkspace: ReadingWorkspace) => {
    if (nextWorkspace !== 'input' && !canUseMaterial) return
    if (nextWorkspace === 'intensive' && sentences[0] && !selectedSentenceId) {
      setSelectedSentenceId(sentences[0].id)
    }
    setWorkspace(nextWorkspace)
  }

  const startTraining = async (nextWorkspace: ReadingWorkspace) => {
    if (!activeMaterialId || saveStatus !== 'saved') {
      const saved = await saveCurrentMaterial()
      if (!saved) return
    }
    openWorkspace(nextWorkspace)
  }

  const applySampleMaterial = () => {
    moveDraftScope(readingMaterialDraftScope(null))
    resetReadingSession()
    setMaterial({
      title: 'How Effective Readers Work',
      text: SAMPLE_TEXT,
      level: 'general',
      goal: 'mixed',
      material_type: 'passage',
    })
    setActiveMaterialId(null)
    setActiveMaterialRecord(null)
    setSaveStatus('idle')
    setTitleMode('auto')
    setTitleSuggestionStatus('suggested')
    setAutoTitleSourceText(SAMPLE_TEXT)
  }

  const loadSampleMaterial = () => {
    if (hasDataAtRisk) {
      setPendingMaterialSwitch({ kind: 'sample' })
      return
    }
    applySampleMaterial()
  }

  const updateTitle = (title: string) => {
    if (title === material.title) return
    markMaterialMutation(true)
    setTitleMode('user')
    setMaterial((current) => ({ ...current, title }))
  }

  const applyTextUpdate = (text: string) => {
    moveDraftScope(readingMaterialDraftScope(null))
    if (text !== material.text) resetReadingSession()
    setSaveStatus('idle')
    setActiveMaterialId(null)
    setActiveMaterialRecord(null)
    if (!text.trim() && titleMode !== 'user') {
      setTitleMode('empty')
      setAutoTitleSourceText('')
      setTitleSuggestionStatus('idle')
      setMaterial((current) => ({ ...current, title: '', text }))
      return
    }
    setMaterial((current) => ({ ...current, text }))
  }

  const updateText = (text: string) => {
    const hasEditRisk = hasSessionWork || Boolean(coachDraft.trim()) || completeStatus === 'saving'
    if (text !== material.text && hasEditRisk) {
      setPendingMaterialSwitch({ kind: 'edit', text })
      return
    }
    applyTextUpdate(text)
  }

  const restoreMaterial = useCallback((item: ReadingMaterialHistoryItem) => {
    const nextScopeId = readingMaterialDraftScope(item.id)
    const scopedDraft = readReadingWorkshopDraft(learner.id, nextScopeId)
    moveDraftScope(nextScopeId)
    resetReadingSession()
    setMaterial({
      title: item.title ?? '',
      text: item.text,
      level: item.level,
      goal: item.goal,
      material_type: item.material_type,
    })
    setActiveMaterialId(item.id)
    setActiveMaterialRecord(item)
    setTitleMode(item.title ? 'user' : 'empty')
    setTitleSuggestionStatus(item.title ? 'suggested' : 'idle')
    setAutoTitleSourceText(item.title ? item.text : '')
    setSaveStatus('saved')
    if (scopedDraft?.material.text === item.text) {
      setWorkspace(scopedDraft.workspace)
      setExtensiveNotes(scopedDraft.extensiveNotes)
      setIntensiveNotesBySentenceId(scopedDraft.intensiveNotesBySentenceId)
      setSentenceAnalysisBySentenceId(scopedDraft.sentenceAnalysisBySentenceId)
      setSelectedSentenceId(scopedDraft.selectedSentenceId)
      setCoachThreadId(scopedDraft.coachThreadId)
      setCoachMessages(scopedDraft.coachMessages)
      setCoachDraft(scopedDraft.coachDraft)
      setClientAttemptId(scopedDraft.clientAttemptId)
      setAttemptSubmitted(scopedDraft.attemptSubmitted)
      setLastSubmittedEvidenceFingerprint(scopedDraft.lastSubmittedEvidenceFingerprint)
      setCompleteStatus(scopedDraft.completeStatus)
      setCompletionResult(scopedDraft.completionResult)
      setShowDraftRecoveryNotice(true)
    }
  }, [learner.id, moveDraftScope, resetReadingSession])

  const requestRestoreMaterial = useCallback((item: ReadingMaterialHistoryItem) => {
    if (hasDataAtRisk) {
      setPendingMaterialSwitch({ kind: 'history', item })
      return
    }
    restoreMaterial(item)
  }, [hasDataAtRisk, restoreMaterial])

  const performPersonalizedMaterialGeneration = useCallback(async () => {
    const requestSequence = ++generationRequestSequenceRef.current
    const startingDataRevision = dataRevisionRef.current
    const controller = new AbortController()
    generationAbortControllerRef.current?.abort()
    generationAbortControllerRef.current = controller
    setGenerationStatus('generating')
    try {
      const response = await fetch(`/api/learners/${learner.id}/reading-workshop/generated-materials`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          material_type: 'passage',
          length: readingTimeBudget >= 25 ? 'long' : 'short',
          goal: 'mixed',
          topic: generationTopic.trim() || null,
        }),
        signal: controller.signal,
      })
      if (!response.ok) throw new Error('Failed to generate personalized reading')
      const payload = await response.json() as { material: ReadingMaterialHistoryItem }
      if (
        generationRequestSequenceRef.current !== requestSequence
        || controller.signal.aborted
      ) return
      setMaterialHistory((current) => [
        payload.material,
        ...current.filter((item) => item.id !== payload.material.id),
      ].slice(0, 20))
      setGenerationStatus('idle')
      if (dataRevisionRef.current !== startingDataRevision) {
        if (pendingMaterialSwitchRef.current) {
          setQueuedGeneratedMaterial(payload.material)
        } else {
          setPendingMaterialSwitch({ kind: 'generated', item: payload.material })
        }
      } else {
        restoreMaterial(payload.material)
        setSaveStatus('saved')
        setWorkspace('extensive')
      }
      void loadMaterialHistory()
    } catch (error) {
      if (
        controller.signal.aborted
        || generationRequestSequenceRef.current !== requestSequence
      ) return
      console.error('Personalized reading generation error:', error)
      setGenerationStatus('error')
    } finally {
      if (generationAbortControllerRef.current === controller) {
        generationAbortControllerRef.current = null
      }
    }
  }, [generationTopic, learner.id, loadMaterialHistory, readingTimeBudget, restoreMaterial])

  const requestPersonalizedMaterialGeneration = useCallback(() => {
    if (hasDataAtRisk) {
      setPendingMaterialSwitch({ kind: 'generate' })
      return
    }
    void performPersonalizedMaterialGeneration()
  }, [hasDataAtRisk, performPersonalizedMaterialGeneration])

  const selectSentence = (sentence: ReadingSentence) => {
    setSelectedSentenceId(sentence.id)
    setActiveTextSelection(null)
  }

  const completeReadingMaterial = useCallback(async () => {
    if (!completionState.canComplete) return
    completionAbortControllerRef.current?.abort()
    const controller = new AbortController()
    const requestSequence = ++completionRequestSequenceRef.current
    const completionRevision = completionRevisionRef.current
    const materialRevision = materialRevisionRef.current
    completionAbortControllerRef.current = controller
    const isCurrentRequest = () => (
      completionRequestSequenceRef.current === requestSequence
      && completionRevisionRef.current === completionRevision
      && materialRevisionRef.current === materialRevision
      && !controller.signal.aborted
    )
    setCompleteStatus('saving')
    setCompletionResult(null)
    try {
      let materialId: string
      if (!activeMaterialId || saveStatus !== 'saved') {
        const saved = await saveCurrentMaterial()
        if (!isCurrentRequest()) return
        if (!saved) throw new Error('请先保存阅读材料。')
        materialId = saved.id
      } else {
        materialId = activeMaterialId
      }
      const intensiveSummary = analyzedSentences.flatMap((sentence) => {
        const notes = intensiveNotesBySentenceId[sentence.id] ?? EMPTY_INTENSIVE_NOTES
        const analysis = sentenceAnalysisBySentenceId[sentence.id]
        return [
          `Sentence ${sentence.order}: ${sentence.text}`,
          notes.mainStructure ? `主干：${notes.mainStructure}` : '',
          notes.phraseNotes ? `词组：${notes.phraseNotes}` : '',
          notes.evidenceNote ? `证据：${notes.evidenceNote}` : '',
          analysis ? `评估：${analysis.outcome} / ${Math.round(analysis.score * 100)}；${analysis.feedback}` : '',
          analysis ? `正确主干：${analysis.correct_analysis.main_structure}` : '',
        ].filter(Boolean)
      })
      const dynamicCanDoIds = uniqueList(
        analyzedSentences.flatMap((sentence) => (
          sentenceAnalysisBySentenceId[sentence.id]?.can_do_points.map((point) => point.can_do_id) ?? []
        ))
      )
      const dynamicBlindSpots = uniqueList(
        analyzedSentences.flatMap((sentence) => (
          sentenceAnalysisBySentenceId[sentence.id]?.error_patterns.map((pattern) => pattern.description) ?? []
        ))
      )
      const completionNotes = [
        extensiveNotes.gist ? `主旨：${extensiveNotes.gist}` : '',
        extensiveNotes.attitude ? `态度：${extensiveNotes.attitude}` : '',
        extensiveNotes.paragraphFunction ? `段落功能：${extensiveNotes.paragraphFunction}` : '',
        extensiveNotes.centralSentence ? `中心句：${extensiveNotes.centralSentence}` : '',
        ...intensiveSummary,
      ].filter(Boolean).join('\n').slice(0, 2000)
      const completionPayloadInput = {
        analyzedSentenceIds: analyzedSentences.map((sentence) => sentence.id),
        goal: material.goal,
        extensiveEvidence: {
          gist: extensiveNotes.gist,
          centralSentence: extensiveNotes.centralSentence,
        },
        grammarTopicCount: dynamicCanDoIds.length,
        grammarBlindSpots: dynamicBlindSpots,
        notes: completionNotes || null,
      }
      let requestAttemptId = clientAttemptId
      let completionPayload = buildReadingCompletionPayload({
        ...completionPayloadInput,
        clientAttemptId: requestAttemptId,
      })
      let evidenceFingerprint = fingerprintReadingCompletionPayload(completionPayload)
      if (
        attemptSubmitted
        && lastSubmittedEvidenceFingerprint
        && lastSubmittedEvidenceFingerprint !== evidenceFingerprint
      ) {
        requestAttemptId = createClientAttemptId()
        completionPayload = buildReadingCompletionPayload({
          ...completionPayloadInput,
          clientAttemptId: requestAttemptId,
        })
        evidenceFingerprint = fingerprintReadingCompletionPayload(completionPayload)
        setClientAttemptId(requestAttemptId)
      }
      const uncertainSubmissionDraft: ReadingWorkshopDraftV1 = {
        ...latestLocalDraftRef.current,
        clientAttemptId: requestAttemptId,
        attemptSubmitted: true,
        lastSubmittedEvidenceFingerprint: evidenceFingerprint,
        completeStatus: 'error',
        completionResult: null,
      }
      latestLocalDraftRef.current = uncertainSubmissionDraft
      writeReadingWorkshopDraft(uncertainSubmissionDraft)
      setAttemptSubmitted(true)
      setLastSubmittedEvidenceFingerprint(evidenceFingerprint)
      const response = await fetch(`/api/learners/${learner.id}/reading-workshop/materials/${materialId}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(completionPayload),
        signal: controller.signal,
      })
      if (!response.ok) throw new Error('阅读完成记录保存失败。')
      const data = await response.json() as ReadingMaterialCompleteResponse
      if (!isCurrentRequest()) return
      const completedDraft: ReadingWorkshopDraftV1 = {
        ...latestLocalDraftRef.current,
        activeMaterialId: data.material_id,
        clientAttemptId: requestAttemptId,
        attemptSubmitted: true,
        lastSubmittedEvidenceFingerprint: evidenceFingerprint,
        completeStatus: 'completed',
        completionResult: data,
      }
      latestLocalDraftRef.current = completedDraft
      writeReadingWorkshopDraft(completedDraft)
      setActiveMaterialId(data.material_id)
      setCompletionResult(data)
      setCompleteStatus('completed')
    } catch (error) {
      if (!isCurrentRequest()) return
      console.error('Reading completion error:', error)
      setCompleteStatus('error')
    } finally {
      if (completionAbortControllerRef.current === controller) {
        completionAbortControllerRef.current = null
      }
    }
  }, [
    activeMaterialId,
    analyzedSentences,
    attemptSubmitted,
    clientAttemptId,
    completionState.canComplete,
    extensiveNotes,
    intensiveNotesBySentenceId,
    sentenceAnalysisBySentenceId,
    learner.id,
    lastSubmittedEvidenceFingerprint,
    material.goal,
    saveCurrentMaterial,
    saveStatus,
  ])

  const clearCurrentDraftForExit = () => {
    skipPersistOnUnmountRef.current = true
    clearReadingWorkshopDraft(learner.id, draftScopeId)
  }

  const requestBack = () => {
    if (hasDataAtRisk) {
      setPendingMaterialSwitch({ kind: 'back' })
      return
    }
    clearCurrentDraftForExit()
    onBack()
  }

  const liveStatusMessage = getReadingLiveStatusMessage({
    coachStatus,
    completeStatus,
    generationStatus,
    saveStatus,
  })
  const pendingDialogCopy = getPendingMaterialDialogCopy(pendingMaterialSwitch)
  const closePendingMaterialDialog = () => {
    if (queuedGeneratedMaterial) {
      setPendingMaterialSwitch({ kind: 'generated', item: queuedGeneratedMaterial })
      setQueuedGeneratedMaterial(null)
      return
    }
    setPendingMaterialSwitch(null)
  }

  return (
    <PageShell variant="full" contentClassName="min-h-[calc(100vh-4rem)]">
      <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {liveStatusMessage}
      </p>
      <FeatureHero
        eyebrow="Reading Workshop"
        title="精读与泛读"
        description="同一篇材料，精读看结构，泛读抓主旨。先把阅读目标拆开，再把精读里卡住的语法点带到微知识点继续学。"
        stats={[
          { label: '词数', value: wordCount },
          { label: '句子', value: sentences.length },
          { label: '建议泛读', value: estimatedMinutes ? `${estimatedMinutes} 分钟` : '—', tone: 'primary' },
          { label: '训练目标', value: READING_GOAL_LABELS[material.goal], tone: 'success' },
        ]}
        actions={
          <Button variant="secondary" onClick={requestBack}>
            <ArrowLeft className="h-4 w-4" />
            {backLabel}
          </Button>
        }
      />

      {showDraftRecoveryNotice ? (
        <StatusBanner
          tone="success"
          title="已恢复上次阅读进度"
          action={
            <button
              type="button"
              className="text-xs font-black underline decoration-emerald-300 underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700"
              onClick={() => setShowDraftRecoveryNotice(false)}
            >
              知道了
            </button>
          }
        >
          材料、阅读笔记和助手对话已从本机草稿恢复。
        </StatusBanner>
      ) : null}

      {readingTrackMode ? (
        <SurfaceCard className="border-indigo-200 bg-[linear-gradient(135deg,#eef2ff,#ffffff_55%,#ecfeff)]">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:items-end">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.2em] text-primary">今日个性化阅读</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">让内容追着你的兴趣和盲点走</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                BinnAgent 会按 {learnerProfile?.current_level?.toUpperCase() ?? '当前水平'}、
                {readingTimeBudget} 分钟预算和近期薄弱点控制篇幅；完成后会保存本次阅读证据和材料历史，方便继续复盘。
              </p>
            </div>
            <div>
              <FormField
                label="今天想读什么"
                name="personalized_reading_topic"
                value={generationTopic}
                onChange={(event) => setGenerationTopic(event.target.value)}
                placeholder="留空则根据兴趣与近期学习自动选择"
              />
              <Button
                className="mt-3 w-full justify-center"
                disabled={generationStatus === 'generating'}
                onClick={requestPersonalizedMaterialGeneration}
              >
                <RotateCw className={`h-4 w-4 ${generationStatus === 'generating' ? 'animate-spin' : ''}`} />
                {generationStatus === 'generating' ? '正在定制阅读材料' : '生成今天的阅读'}
              </Button>
              {generationStatus === 'error' ? (
                <p className="mt-2 text-xs font-bold text-rose-700">生成暂时失败，可以重试或从历史材料继续。</p>
              ) : null}
            </div>
          </div>
        </SurfaceCard>
      ) : null}

      <div className={`grid min-w-0 items-start gap-5 transition-[grid-template-columns] duration-200 motion-reduce:transition-none ${
        isSidebarCollapsed
          ? 'lg:grid-cols-[76px_minmax(0,1fr)]'
          : 'lg:grid-cols-[240px_minmax(0,1fr)] xl:grid-cols-[260px_minmax(0,1fr)]'
      }`}>
        <ReadingWorkspaceSidebar
          activeWorkspace={workspace}
          canUseMaterial={canUseMaterial}
          collapsed={isSidebarCollapsed}
          stageCompletion={completionState.completion}
          onChange={openWorkspace}
          onToggleCollapsed={() => setIsSidebarCollapsed((current) => !current)}
        />

        <div className={`grid min-w-0 items-start gap-5 transition-[grid-template-columns] duration-200 motion-reduce:transition-none ${
          isCoachCollapsed
            ? 'xl:grid-cols-[minmax(0,1fr)_76px]'
            : '2xl:grid-cols-[minmax(0,1fr)_360px]'
        }`}>
        <div className="min-w-0">
          {workspace === 'input' && (
        <InputWorkspace
          material={material}
          canUseMaterial={canUseMaterial}
          onLoadSample={loadSampleMaterial}
          onRefreshHistory={loadMaterialHistory}
          onRestoreHistory={requestRestoreMaterial}
          onSaveMaterial={() => void saveCurrentMaterial()}
          onStartTraining={(nextWorkspace) => void startTraining(nextWorkspace)}
          onTitleChange={updateTitle}
          onTextChange={updateText}
          onLevelChange={(level) => {
            if (level === material.level) return
            markMaterialMutation(true)
            setMaterial((current) => ({ ...current, level }))
          }}
          onGoalChange={(goal) => {
            if (goal === material.goal) return
            markMaterialMutation(true)
            setMaterial((current) => ({ ...current, goal }))
          }}
          historyItems={materialHistory}
          historyStatus={historyStatus}
          saveStatus={saveStatus}
          titleSuggestionStatus={titleSuggestionStatus}
        />
          )}

          {workspace === 'extensive' && (
        <ExtensiveWorkspace
          material={material}
          canUseMaterial={canUseMaterial}
          estimatedMinutes={estimatedMinutes}
          keywordCandidates={keywordCandidates}
          notes={extensiveNotes}
          wordCount={wordCount}
          onNotesChange={updateExtensiveNote}
          onOpenWorkspace={openWorkspace}
        />
          )}

          {workspace === 'intensive' && (
        <IntensiveWorkspace
          canUseMaterial={canUseMaterial}
          focusHints={selectedSentenceHints}
          learnerId={learner.id}
          learnerLevel={learnerProfile?.current_level ?? null}
          notes={intensiveNotes}
          analysisResult={selectedSentenceAnalysis}
          analysisFailure={sentenceAnalysisFailure}
          analysisStatus={sentenceAnalysisStatus}
          selectedSentence={selectedSentence}
          selectedSentenceId={selectedSentence?.id ?? null}
          sentences={sentences}
          onNotesChange={updateIntensiveNote}
          onSubmitAnalysis={(unableToAnalyze) => void submitSentenceAnalysis(unableToAnalyze)}
          onOpenWorkspace={openWorkspace}
          onSelectSentence={selectSentence}
          onReadingSelectionChange={setActiveTextSelection}
        />
          )}

          {workspace === 'review' && (
        <ReviewWorkspace
          extensiveNotes={extensiveNotes}
          intensiveNotesBySentenceId={intensiveNotesBySentenceId}
          sentenceAnalysisBySentenceId={sentenceAnalysisBySentenceId}
          keywordCandidates={keywordCandidates}
          material={material}
          selectedSentences={analyzedSentences}
          sentences={sentences}
          wordCount={wordCount}
          completeStatus={completeStatus}
          completionResult={completionResult}
          canComplete={completionState.canComplete}
          missingLabels={completionState.missingLabels}
          sourceLabel={activeSourceLabel}
          onCompleteReading={() => void completeReadingMaterial()}
          onOpenWorkspace={openWorkspace}
        />
          )}
        </div>
        <ReadingCoachSidebar
          collapsed={isCoachCollapsed}
          draft={coachDraft}
          messages={coachMessages}
          status={coachStatus}
          hasMaterial={canUseMaterial}
          onDraftChange={(value) => {
            dataRevisionRef.current += 1
            setCoachDraft(value)
          }}
          onSend={() => void askReadingCoach()}
          onToggleCollapsed={() => setIsCoachCollapsed((current) => !current)}
        />
        </div>
      </div>

      <ConfirmDialog
        open={Boolean(pendingMaterialSwitch)}
        title={pendingDialogCopy.title}
        description={pendingDialogCopy.description}
        confirmLabel={pendingDialogCopy.confirmLabel}
        cancelLabel="继续本次阅读"
        danger
        onCancel={closePendingMaterialDialog}
        onConfirm={() => {
          const pending = pendingMaterialSwitch
          closePendingMaterialDialog()
          if (pending?.kind === 'sample') applySampleMaterial()
          if (pending?.kind === 'history') restoreMaterial(pending.item)
          if (pending?.kind === 'generated') {
            restoreMaterial(pending.item)
            setWorkspace('extensive')
          }
          if (pending?.kind === 'edit') applyTextUpdate(pending.text)
          if (pending?.kind === 'generate') void performPersonalizedMaterialGeneration()
          if (pending?.kind === 'back') {
            clearCurrentDraftForExit()
            onBack()
          }
          if (pending?.kind === 'external-navigation') {
            clearCurrentDraftForExit()
            pending.navigate()
          }
        }}
      />
    </PageShell>
  )
}

function ReadingCoachSidebar({
  collapsed,
  draft,
  messages,
  status,
  hasMaterial,
  onDraftChange,
  onSend,
  onToggleCollapsed,
}: {
  collapsed: boolean
  draft: string
  messages: ReadingCoachMessage[]
  status: 'idle' | 'sending' | 'error'
  hasMaterial: boolean
  onDraftChange: (value: string) => void
  onSend: () => void
  onToggleCollapsed: () => void
}) {
  const messageListRef = useRef<HTMLDivElement>(null)
  const isCoachDrawer = useMediaQuery('(max-width: 1535px)')
  const coachPanelTitleId = useId()
  const { containerRef: coachPanelRef, handleKeyDown: handleCoachPanelKeyDown } = useFocusTrap<HTMLElement>({
    isActive: isCoachDrawer && !collapsed,
    onEscape: onToggleCollapsed,
  })

  useEffect(() => {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    messageListRef.current?.scrollTo({
      top: messageListRef.current.scrollHeight,
      behavior: reducedMotion ? 'auto' : 'smooth',
    })
  }, [messages, status])

  if (collapsed) {
    return (
      <aside className="fixed bottom-4 left-4 z-[105] flex max-w-[calc(100vw-10rem)] items-center gap-3 rounded-2xl border border-indigo-200 bg-indigo-50 p-2 shadow-[0_8px_24px_rgba(15,23,42,0.12)] xl:sticky xl:bottom-auto xl:left-auto xl:top-5 xl:z-auto xl:max-w-none xl:flex-col xl:shadow-[0_8px_24px_rgba(15,23,42,0.05)]">
        <button
          type="button"
          onClick={onToggleCollapsed}
          className="flex size-10 items-center justify-center rounded-xl bg-primary text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          aria-label="展开阅读助手"
          title="展开阅读助手"
        >
          <PanelRightOpen className="size-4" />
        </button>
        <MessageCircle className="size-5 text-primary" />
        <span className="text-xs font-black tracking-[0.18em] text-indigo-900 xl:[writing-mode:vertical-rl]">阅读助手</span>
        {messages.length > 0 ? (
          <span className="flex size-6 items-center justify-center rounded-full bg-white text-xs font-black text-primary">{messages.length}</span>
        ) : null}
      </aside>
    )
  }

  return (
    <>
      {isCoachDrawer ? (
        <button
          type="button"
          aria-label="收起阅读助手"
          onClick={onToggleCollapsed}
          className="fixed inset-0 z-[110] bg-slate-950/30 transition-opacity duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary motion-reduce:transition-none 2xl:hidden"
        />
      ) : null}
    <aside
      ref={isCoachDrawer ? coachPanelRef : undefined}
      role={isCoachDrawer ? 'dialog' : undefined}
      aria-modal={isCoachDrawer ? 'true' : undefined}
      aria-labelledby={isCoachDrawer ? coachPanelTitleId : undefined}
      tabIndex={isCoachDrawer ? -1 : undefined}
      onKeyDown={isCoachDrawer ? handleCoachPanelKeyDown : undefined}
      className="fixed bottom-0 right-0 top-0 z-[120] flex w-[min(92vw,24rem)] flex-col overflow-hidden border-l border-slate-200 bg-white shadow-2xl focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-primary 2xl:sticky 2xl:top-5 2xl:z-auto 2xl:h-[calc(100vh-6rem)] 2xl:max-h-[780px] 2xl:w-auto 2xl:rounded-2xl 2xl:border"
    >
      <div className="flex items-start justify-between gap-3 border-b border-slate-200 bg-[linear-gradient(135deg,#eef2ff,#ffffff)] p-4">
        <div className="flex min-w-0 items-start gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary text-white">
            <MessageCircle className="size-5" />
          </span>
          <div>
            <h2 id={coachPanelTitleId} className="text-base font-black text-slate-950">阅读助手</h2>
            <p className="mt-0.5 text-xs leading-5 text-slate-500">已同步当前文章、精读位置和笔记</p>
          </div>
        </div>
        <button
          type="button"
          onClick={onToggleCollapsed}
          className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 hover:border-indigo-200 hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          aria-label="收起阅读助手"
          title="收起阅读助手"
        >
          <PanelRightClose className="size-4" />
        </button>
      </div>

      <div ref={messageListRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
        {messages.length === 0 ? (
          <div className="rounded-xl border border-dashed border-indigo-200 bg-indigo-50/60 p-4 text-sm leading-6 text-slate-600">
            <p className="font-black text-indigo-950">不用重复粘贴文章</p>
            <p className="mt-1">可以直接问“这句话怎么拆”“作者为什么这样写”或“检查我的主旨判断”。</p>
          </div>
        ) : messages.map((message) => (
          <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[92%] rounded-2xl px-3.5 py-2.5 text-sm leading-6 ${
              message.role === 'user'
                ? 'rounded-br-md bg-primary text-white'
                : 'rounded-bl-md bg-slate-100 text-slate-700'
            }`}>
              {message.role === 'assistant' ? (
                <div className="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                </div>
              ) : message.content}
            </div>
          </div>
        ))}
        {status === 'sending' ? (
          <div className="flex items-center gap-2 text-sm font-bold text-slate-500">
            <LoaderCircle className="size-4 animate-spin text-primary" /> BinnAgent 正在结合当前阅读位置思考…
          </div>
        ) : null}
        {status === 'error' ? (
          <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-bold text-rose-700">回复暂时失败，问题已保留，可以再次发送。</p>
        ) : null}
      </div>

      <form
        className="border-t border-slate-200 p-3"
        onSubmit={(event) => {
          event.preventDefault()
          onSend()
        }}
      >
        <label htmlFor="reading-coach-question" className="sr-only">向阅读助手提问</label>
        <textarea
          id="reading-coach-question"
          value={draft}
          disabled={!hasMaterial || status === 'sending'}
          onChange={(event) => onDraftChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.nativeEvent.isComposing) return
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              onSend()
            }
          }}
          rows={3}
          placeholder={hasMaterial ? '针对当前文章提问…' : '请先添加阅读材料'}
          className="w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm leading-6 text-slate-900 outline-none transition-colors placeholder:text-slate-400 focus:border-primary focus:bg-white disabled:cursor-not-allowed disabled:opacity-60"
        />
        <div className="mt-2 flex items-center justify-between gap-3">
          <p className="text-[11px] text-slate-400">Enter 发送 · Shift+Enter 换行</p>
          <Button type="submit" className="size-9 px-0 py-0" disabled={!draft.trim() || !hasMaterial || status === 'sending'} aria-label="发送问题">
            <Send className="size-4" />
          </Button>
        </div>
      </form>
    </aside>
    </>
  )
}

function ReadingWorkspaceSidebar({
  activeWorkspace,
  canUseMaterial,
  collapsed,
  stageCompletion,
  onChange,
  onToggleCollapsed,
}: {
  activeWorkspace: ReadingWorkspace
  canUseMaterial: boolean
  collapsed: boolean
  stageCompletion: Record<ReadingWorkspace, boolean>
  onChange: (workspace: ReadingWorkspace) => void
  onToggleCollapsed: () => void
}) {
  const activeIndex = WORKSPACE_TABS.findIndex((item) => item.id === activeWorkspace)
  return (
    <aside className={`rounded-2xl border border-slate-200 bg-white p-3 shadow-[0_8px_24px_rgba(15,23,42,0.05)] transition-[padding] duration-200 motion-reduce:transition-none lg:sticky lg:top-5 ${collapsed ? 'lg:px-2' : ''}`}>
      <div className="flex items-start justify-between gap-2 px-2 pb-3 pt-1">
        <div className={collapsed ? 'lg:hidden' : ''}>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-primary">Reading Flow</p>
          <h2 className="mt-1 text-base font-black text-slate-950">阅读学习路径</h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">先完整理解，再逐层排盲和沉淀。</p>
        </div>
        <button
          type="button"
          onClick={onToggleCollapsed}
          className="hidden size-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition-colors hover:border-indigo-200 hover:bg-indigo-50 hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary lg:flex"
          aria-label={collapsed ? '展开阅读学习路径' : '收起阅读学习路径'}
          title={collapsed ? '展开侧边栏' : '收起侧边栏'}
        >
          {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
        </button>
      </div>
      <nav className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1" aria-label="阅读工作区">
        {WORKSPACE_TABS.map((item, index) => {
          const active = item.id === activeWorkspace
          const completed = stageCompletion[item.id]
          const disabled = item.id !== 'input' && !canUseMaterial
          return (
            <button
              key={item.id}
              type="button"
              title={collapsed ? `${item.label} · ${item.description}` : undefined}
              aria-current={active ? 'step' : undefined}
              aria-disabled={disabled || undefined}
              disabled={disabled}
              onClick={() => onChange(item.id)}
              className={`group flex min-w-0 items-center gap-3 rounded-xl border px-3 py-3 text-left transition-[border-color,background-color,box-shadow] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50 ${
                active
                  ? 'border-indigo-200 bg-indigo-50 shadow-sm'
                  : 'border-transparent bg-slate-50 hover:border-slate-200 hover:bg-white'
              }`}
            >
              <span className={`flex size-9 shrink-0 items-center justify-center rounded-lg text-sm font-black ${
                active
                  ? 'bg-primary text-primary-foreground'
                  : completed
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-white text-slate-500 ring-1 ring-slate-200'
              }`}>
                {completed && !active ? '✓' : index + 1}
              </span>
              <span className={`min-w-0 flex-1 ${collapsed ? 'lg:hidden' : ''}`}>
                <span className={`block truncate text-sm font-black ${active ? 'text-indigo-950' : 'text-slate-800'}`}>{item.label}</span>
                <span className="mt-0.5 block truncate text-xs text-slate-500">{item.description}</span>
              </span>
              <span className={`size-2 shrink-0 rounded-full ${collapsed ? 'lg:hidden' : ''} ${active ? 'bg-primary' : 'bg-slate-300'}`} />
            </button>
          )
        })}
      </nav>
      <div className={`mt-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5 ${collapsed ? 'lg:hidden' : ''}`}>
        <p className="text-xs font-bold text-slate-500">当前阶段</p>
        <p className="mt-1 text-sm font-black text-slate-900">{WORKSPACE_TABS[activeIndex]?.label}</p>
      </div>
    </aside>
  )
}

function InputWorkspace({
  material,
  canUseMaterial,
  onGoalChange,
  onLevelChange,
  onLoadSample,
  onRefreshHistory,
  onRestoreHistory,
  onSaveMaterial,
  onStartTraining,
  onTextChange,
  onTitleChange,
  historyItems,
  historyStatus,
  saveStatus,
  titleSuggestionStatus,
}: {
  material: ReadingMaterial
  canUseMaterial: boolean
  historyItems: ReadingMaterialHistoryItem[]
  historyStatus: MaterialHistoryStatus
  onGoalChange: (goal: ReadingTrainingGoal) => void
  onLevelChange: (level: ReadingLevel) => void
  onLoadSample: () => void
  onRefreshHistory: () => void
  onRestoreHistory: (item: ReadingMaterialHistoryItem) => void
  onSaveMaterial: () => void
  onStartTraining: (workspace: ReadingWorkspace) => void
  onTextChange: (text: string) => void
  onTitleChange: (title: string) => void
  saveStatus: MaterialSaveStatus
  titleSuggestionStatus: TitleSuggestionStatus
}) {
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const isHistoryDrawer = useMediaQuery('(max-width: 1535px)')
  const historyPanelId = useId()
  const historyTitleId = useId()
  const { containerRef: historyPanelRef, handleKeyDown: handleHistoryPanelKeyDown } = useFocusTrap<HTMLDivElement>({
    isActive: isHistoryDrawer && isHistoryOpen,
    onEscape: () => setIsHistoryOpen(false),
  })
  const titleDescription = {
    idle: '可选；粘贴完整材料后会自动建议标题，仍可手动修改。',
    checking: '正在根据材料建议标题，仍可手动填写。',
    suggested: '已自动建议标题，仍可手动修改。',
    incomplete: '可选；材料完整后会自动建议标题。',
    error: '自动标题暂时不可用，仍可手动填写。',
  } satisfies Record<TitleSuggestionStatus, string>
  const saveStatusLabel = {
    idle: '保存材料',
    saving: '正在保存',
    saved: '已保存',
    error: '保存失败',
  } satisfies Record<MaterialSaveStatus, string>

  return (
    <section className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_360px]">
      <SurfaceCard>
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-black text-slate-950">阅读材料</h2>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <FormField
            label="标题"
            name="reading_material_title"
            autoComplete="off"
            description={titleDescription[titleSuggestionStatus]}
            value={material.title}
            onChange={(event) => onTitleChange(event.target.value)}
            placeholder="例如 The Future of Libraries…"
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="难度">
              <Select
                name="reading_material_level"
                autoComplete="off"
                className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                value={material.level}
                onChange={(event) => onLevelChange(event.target.value as ReadingLevel)}
              >
                {(Object.entries(READING_LEVEL_LABELS) as Array<[ReadingLevel, string]>).map(([id, label]) => (
                  <option key={id} value={id}>{label}</option>
                ))}
              </Select>
            </FormField>
            <FormField label="训练目标">
              <Select
                name="reading_training_goal"
                autoComplete="off"
                className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                value={material.goal}
                onChange={(event) => onGoalChange(event.target.value as ReadingTrainingGoal)}
              >
                {(Object.entries(READING_GOAL_LABELS) as Array<[ReadingTrainingGoal, string]>).map(([id, label]) => (
                  <option key={id} value={id}>{label}</option>
                ))}
              </Select>
            </FormField>
          </div>
        </div>
        <div className="mt-4">
          <FormField
            as="textarea"
            label="英文材料"
            name="reading_material_text"
            autoComplete="off"
            value={material.text}
            onChange={(event) => onTextChange(event.target.value)}
            placeholder="Paste an English paragraph here…"
            className="h-64 resize-y"
          />
        </div>
        <div className="mt-5 flex flex-wrap gap-3">
          <Button disabled={!canUseMaterial} onClick={() => onStartTraining(material.goal === 'intensive' ? 'intensive' : 'extensive')}>
            <BookOpenCheck className="h-4 w-4" />
            开始训练
          </Button>
          <Button
            variant="secondary"
            disabled={!canUseMaterial || saveStatus === 'saving'}
            onClick={onSaveMaterial}
          >
            {saveStatus === 'saved' ? <CheckCircle2 className="h-4 w-4" /> : <Save className="h-4 w-4" />}
            {saveStatusLabel[saveStatus]}
          </Button>
          <Button variant="secondary" onClick={onLoadSample}>
            <PencilLine className="h-4 w-4" />
            填入示例
          </Button>
        </div>
      </SurfaceCard>

      <Button
        variant="secondary"
        className="2xl:hidden"
        onClick={() => setIsHistoryOpen((current) => !current)}
        aria-expanded={isHistoryOpen}
        aria-controls={historyPanelId}
      >
        <PanelLeftOpen className="h-4 w-4" />
        {isHistoryOpen ? '收起材料历史' : '展开材料历史'}
      </Button>

      {isHistoryDrawer && isHistoryOpen ? (
        <button
          type="button"
          aria-label="收起材料历史"
          onClick={() => setIsHistoryOpen(false)}
          className="fixed inset-0 z-[110] bg-slate-950/30 transition-opacity duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary motion-reduce:transition-none 2xl:hidden"
        />
      ) : null}
      <div
        id={historyPanelId}
        ref={isHistoryDrawer ? historyPanelRef : undefined}
        role={isHistoryDrawer ? 'dialog' : undefined}
        aria-modal={isHistoryDrawer ? 'true' : undefined}
        aria-labelledby={isHistoryDrawer ? historyTitleId : undefined}
        tabIndex={isHistoryDrawer ? -1 : undefined}
        onKeyDown={isHistoryDrawer ? handleHistoryPanelKeyDown : undefined}
        className={isHistoryOpen
          ? 'fixed bottom-0 right-0 top-0 z-[120] w-[min(88vw,24rem)] overflow-y-auto overscroll-contain transition-[transform,opacity] duration-200 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-primary motion-reduce:transition-none 2xl:static 2xl:w-auto 2xl:overflow-visible'
          : 'hidden 2xl:block'
        }
      >
        <SurfaceCard className="flex min-h-full flex-col justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Layers3 className="h-5 w-5 text-success" />
              <h2 className="text-lg font-black text-slate-950">训练顺序</h2>
            </div>
            <div className="mt-5 space-y-3">
              <ModeStep title="泛读" text="先限制时间，判断主旨、态度和段落功能。" />
              <ModeStep title="精读" text="再选择难句，拆主干、修饰语和语法卡点。" />
              <ModeStep title="沉淀" text="最后留下本次材料、句子和去学过的语法点。" />
            </div>
          </div>
          <div className="mt-5 rounded-lg border border-primary/20 bg-primary/5 p-4 text-sm leading-6 text-primary">
            精读和泛读处理同一篇材料，但训练目标不同：泛读少看细节，精读少求速度。
          </div>

          <div className="mt-5 border-t border-slate-200 pt-5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <History className="h-5 w-5 text-primary" />
                <h2 id={historyTitleId} className="text-lg font-black text-slate-950">材料历史</h2>
              </div>
              <button
                type="button"
                aria-label="刷新历史记录"
                className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-slate-100 hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                onClick={onRefreshHistory}
                title="刷新历史记录"
              >
                <RotateCw className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-4 max-h-[420px] space-y-3 overflow-y-auto pr-1">
              {historyStatus === 'loading' ? (
                <p className="rounded-lg border border-dashed border-slate-200 p-3 text-sm text-muted-foreground">
                  正在加载历史材料…
                </p>
              ) : historyStatus === 'error' ? (
                <p className="rounded-lg border border-dashed border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                  历史材料暂时无法加载。
                </p>
              ) : historyItems.length > 0 ? (
                historyItems.map((item) => (
                  <HistoryItem
                    key={item.id}
                    item={item}
                    onRestore={() => {
                      onRestoreHistory(item)
                      setIsHistoryOpen(false)
                    }}
                  />
                ))
              ) : (
                <p className="rounded-lg border border-dashed border-slate-200 p-3 text-sm leading-6 text-muted-foreground">
                  还没有历史材料。开始训练或点击保存后会出现在这里。
                </p>
              )}
            </div>
          </div>
        </SurfaceCard>
      </div>
    </section>
  )
}

function ExtensiveWorkspace({
  material,
  canUseMaterial,
  estimatedMinutes,
  keywordCandidates,
  notes,
  wordCount,
  onNotesChange,
  onOpenWorkspace,
}: {
  material: ReadingMaterial
  canUseMaterial: boolean
  estimatedMinutes: number
  keywordCandidates: ReadingKeywordCandidate[]
  notes: ExtensiveNotes
  wordCount: number
  onNotesChange: (key: keyof ExtensiveNotes, value: string) => void
  onOpenWorkspace: (workspace: ReadingWorkspace) => void
}) {
  if (!canUseMaterial) {
    return <EmptyMaterialCard onOpenInput={() => onOpenWorkspace('input')} />
  }

  return (
    <section className="grid gap-5 2xl:grid-cols-[minmax(0,1fr)_390px]">
      <SurfaceCard>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-primary">Extensive Reading</p>
            <h2 className="mt-1 text-lg font-black text-slate-950">{material.title.trim() || '未命名阅读材料'}</h2>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm sm:w-56">
            <MetricTile label="词数" value={wordCount} />
            <MetricTile label="建议" value={`${estimatedMinutes} 分钟`} />
          </div>
        </div>

        <div className="mt-5 max-h-[560px] overflow-y-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-50 p-5 text-base leading-8 text-slate-700 sm:p-6 sm:text-lg sm:leading-9">
          {material.text}
        </div>
      </SurfaceCard>

      <div className="grid gap-5">
        <SurfaceCard>
          <div className="flex items-center gap-2">
            <Timer className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-black text-slate-950">泛读任务</h2>
          </div>
          <div className="mt-4 space-y-4">
            <FormField
              as="textarea"
              label="主旨判断"
              name="reading_gist_note"
              autoComplete="off"
              value={notes.gist}
              onChange={(event) => onNotesChange('gist', event.target.value)}
              placeholder="这段材料主要讲什么…"
            />
            <FormField
              label="作者态度"
              name="reading_attitude_note"
              autoComplete="off"
              value={notes.attitude}
              onChange={(event) => onNotesChange('attitude', event.target.value)}
              placeholder="支持 / 反对 / 中立，以及依据…"
            />
            <FormField
              label="段落功能"
              name="reading_paragraph_function_note"
              autoComplete="off"
              value={notes.paragraphFunction}
              onChange={(event) => onNotesChange('paragraphFunction', event.target.value)}
              placeholder="引入问题 / 解释原因 / 举例 / 总结…"
            />
            <FormField
              label="中心句"
              name="reading_central_sentence_note"
              autoComplete="off"
              value={notes.centralSentence}
              onChange={(event) => onNotesChange('centralSentence', event.target.value)}
              placeholder="哪一句最能概括段落中心…"
            />
          </div>
        </SurfaceCard>

        <SurfaceCard>
          <div className="flex items-center gap-2">
            <SearchCheck className="h-5 w-5 text-success" />
            <h2 className="text-lg font-black text-slate-950">关键词圈定</h2>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {keywordCandidates.length > 0 ? (
              keywordCandidates.map((keyword) => (
                <span key={keyword.word} className="rounded-md bg-success/10 px-2.5 py-1 text-xs font-bold text-success">
                  {keyword.word}
                  {keyword.count > 1 ? ` x${keyword.count}` : ''}
                </span>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">材料较短时，可先手动圈出重复出现的名词和动词。</p>
            )}
          </div>
          <Button className="mt-5 w-full" variant="secondary" onClick={() => onOpenWorkspace('intensive')}>
            <Highlighter className="h-4 w-4" />
            进入精读拆句
          </Button>
        </SurfaceCard>
      </div>
    </section>
  )
}

function IntensiveWorkspace({
  canUseMaterial,
  focusHints,
  learnerId,
  learnerLevel,
  notes,
  analysisResult,
  analysisFailure,
  analysisStatus,
  selectedSentence,
  selectedSentenceId,
  sentences,
  onNotesChange,
  onOpenWorkspace,
  onSelectSentence,
  onSubmitAnalysis,
  onReadingSelectionChange,
}: {
  canUseMaterial: boolean
  focusHints: ReadingSentenceHint[]
  learnerId: string
  learnerLevel: string | null
  notes: IntensiveNotes
  analysisResult: ReadingSentenceAnalysisResponse | null
  analysisFailure: SentenceAnalysisFailure | null
  analysisStatus: 'idle' | 'submitting' | 'error'
  selectedSentence: ReadingSentence | null
  selectedSentenceId: string | null
  sentences: ReadingSentence[]
  onNotesChange: (key: keyof IntensiveNotes, value: string) => void
  onOpenWorkspace: (workspace: ReadingWorkspace) => void
  onSelectSentence: (sentence: ReadingSentence) => void
  onSubmitAnalysis: (unableToAnalyze: boolean) => void
  onReadingSelectionChange: (text: string | null) => void
}) {
  const [mode, setMode] = useState<'sentence_list' | 'full_text'>('sentence_list')
  const [selection, setSelection] = useState<{ id: number; text: string; sentence: ReadingSentence } | null>(null)
  const [translation, setTranslation] = useState<{
    translation: string
    context_note: string
    source: 'base_dictionary' | 'model'
    build_version?: string | null
  } | null>(null)
  const [translationStatus, setTranslationStatus] = useState<'idle' | 'loading' | 'error'>('idle')
  const selectionSequenceRef = useRef(0)
  const selectionIdentityRef = useRef<number | null>(null)
  const translationRequestSequenceRef = useRef(0)
  const translationAbortControllerRef = useRef<AbortController | null>(null)
  const fullTextRef = useRef<HTMLDivElement>(null)
  const [isSentenceListOpen, setIsSentenceListOpen] = useState(false)
  const isSentenceListDrawer = useMediaQuery('(max-width: 1535px)')
  const sentenceListPanelId = useId()
  const sentenceListTitleId = useId()
  const { containerRef: sentenceListPanelRef, handleKeyDown: handleSentenceListPanelKeyDown } = useFocusTrap<HTMLDivElement>({
    isActive: isSentenceListDrawer && isSentenceListOpen,
    onEscape: () => setIsSentenceListOpen(false),
  })

  useEffect(() => () => translationAbortControllerRef.current?.abort(), [])

  if (!canUseMaterial) {
    return <EmptyMaterialCard onOpenInput={() => onOpenWorkspace('input')} />
  }

  const hasAnalysisAttempt = hasAnyIntensiveNote(notes)

  const clearTextSelection = () => {
    selectionIdentityRef.current = null
    translationRequestSequenceRef.current += 1
    translationAbortControllerRef.current?.abort()
    translationAbortControllerRef.current = null
    setSelection(null)
    setTranslation(null)
    setTranslationStatus('idle')
    onReadingSelectionChange(null)
  }

  const selectSentenceForAnalysis = (sentence: ReadingSentence) => {
    clearTextSelection()
    onSelectSentence(sentence)
  }

  const captureSelection = () => {
    const browserSelection = window.getSelection()
    const text = browserSelection?.toString().trim() ?? ''
    const range = browserSelection && browserSelection.rangeCount > 0 ? browserSelection.getRangeAt(0) : null
    if (!text || text.length > 200 || !range || !fullTextRef.current?.contains(range.commonAncestorContainer)) {
      clearTextSelection()
      return
    }
    const startSentenceId = findReadingSentenceId(range.startContainer)
    const endSentenceId = findReadingSentenceId(range.endContainer)
    const sentence = startSentenceId && startSentenceId === endSentenceId
      ? sentences.find((item) => item.id === startSentenceId)
      : null
    if (!sentence) {
      clearTextSelection()
      return
    }
    translationRequestSequenceRef.current += 1
    translationAbortControllerRef.current?.abort()
    translationAbortControllerRef.current = null
    const selectionId = ++selectionSequenceRef.current
    selectionIdentityRef.current = selectionId
    onSelectSentence(sentence)
    setSelection({ id: selectionId, text, sentence })
    onReadingSelectionChange(text)
    setTranslation(null)
    setTranslationStatus('idle')
  }

  const captureSelectionAfterPointer = () => {
    window.requestAnimationFrame(captureSelection)
  }

  const translateSelection = async () => {
    if (!selection) return
    translationAbortControllerRef.current?.abort()
    const controller = new AbortController()
    const requestSequence = ++translationRequestSequenceRef.current
    const selectionId = selection.id
    translationAbortControllerRef.current = controller
    const isCurrentRequest = () => (
      selectionIdentityRef.current === selectionId
      && translationRequestSequenceRef.current === requestSequence
      && !controller.signal.aborted
    )
    setTranslationStatus('loading')
    try {
      const response = await fetch(`/api/learners/${learnerId}/reading-workshop/selection-translation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          selection: selection.text,
          sentence: selection.sentence.text,
          learner_level: learnerLevel,
        }),
        signal: controller.signal,
      })
      if (!response.ok) throw new Error('Selection translation failed')
      const result = await response.json() as {
        translation: string
        context_note: string
        source: 'base_dictionary' | 'model'
        build_version?: string | null
      }
      if (!isCurrentRequest()) return
      setTranslation(result)
      setTranslationStatus('idle')
    } catch (error) {
      if (!isCurrentRequest()) return
      console.error('Reading selection translation error:', error)
      setTranslationStatus('error')
    } finally {
      if (translationAbortControllerRef.current === controller) {
        translationAbortControllerRef.current = null
      }
    }
  }

  return (
    <div className="grid gap-5">
      <SurfaceCard className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-primary">Intensive Mode</p>
          <h2 className="mt-1 text-lg font-black text-slate-950">选择你的精读方式</h2>
        </div>
        <div className="grid grid-cols-2 gap-2 rounded-xl border border-slate-200 bg-slate-50 p-1" role="group" aria-label="精读模式">
          <button type="button" aria-pressed={mode === 'sentence_list'} onClick={() => setMode('sentence_list')} className={`rounded-lg px-3 py-2 text-sm font-black transition-colors ${mode === 'sentence_list' ? 'bg-primary text-white shadow-sm' : 'text-slate-600 hover:bg-white'}`}>逐句精读</button>
          <button type="button" aria-pressed={mode === 'full_text'} onClick={() => setMode('full_text')} className={`rounded-lg px-3 py-2 text-sm font-black transition-colors ${mode === 'full_text' ? 'bg-primary text-white shadow-sm' : 'text-slate-600 hover:bg-white'}`}>全文选读</button>
        </div>
      </SurfaceCard>

      <section className={`grid gap-5 ${mode === 'sentence_list' ? '2xl:grid-cols-[340px_minmax(0,1fr)]' : '2xl:grid-cols-[minmax(0,1.1fr)_minmax(480px,0.9fr)]'}`}>
      {mode === 'sentence_list' ? <Button
        variant="secondary"
        className="2xl:hidden"
        onClick={() => setIsSentenceListOpen((current) => !current)}
        aria-expanded={isSentenceListOpen}
        aria-controls={sentenceListPanelId}
      >
        <PanelLeftOpen className="h-4 w-4" />
        {isSentenceListOpen ? '收起句子列表' : '展开句子列表'}
      </Button> : null}

      {mode === 'sentence_list' && isSentenceListDrawer && isSentenceListOpen ? (
        <button
          type="button"
          aria-label="收起句子列表"
          onClick={() => setIsSentenceListOpen(false)}
          className="fixed inset-0 z-[110] bg-slate-950/30 transition-opacity duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary motion-reduce:transition-none 2xl:hidden"
        />
      ) : null}
      {mode === 'sentence_list' ? <div
        id={sentenceListPanelId}
        ref={isSentenceListDrawer ? sentenceListPanelRef : undefined}
        role={isSentenceListDrawer ? 'dialog' : undefined}
        aria-modal={isSentenceListDrawer ? 'true' : undefined}
        aria-labelledby={isSentenceListDrawer ? sentenceListTitleId : undefined}
        tabIndex={isSentenceListDrawer ? -1 : undefined}
        onKeyDown={isSentenceListDrawer ? handleSentenceListPanelKeyDown : undefined}
        className={isSentenceListOpen
          ? 'fixed bottom-0 left-0 top-0 z-[120] w-[min(88vw,24rem)] overflow-y-auto overscroll-contain transition-[transform,opacity] duration-200 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-primary motion-reduce:transition-none 2xl:static 2xl:w-auto 2xl:overflow-visible'
          : 'hidden 2xl:block'
        }
      >
        <SurfaceCard className="min-h-full">
          <div className="flex items-center gap-2">
            <ListChecks className="h-5 w-5 text-primary" />
            <h2 id={sentenceListTitleId} className="text-lg font-black text-slate-950">选择精读句子</h2>
          </div>
          <div className="mt-4 max-h-[620px] space-y-2 overflow-y-auto pr-1">
            {sentences.map((sentence) => (
              <button
                key={sentence.id}
                type="button"
                aria-pressed={selectedSentenceId === sentence.id}
                onClick={() => {
                  selectSentenceForAnalysis(sentence)
                  setIsSentenceListOpen(false)
                }}
                className={`w-full rounded-lg border p-3 text-left text-sm leading-6 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
                  selectedSentenceId === sentence.id
                    ? 'border-primary bg-primary/5 text-primary'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-primary/30 hover:text-slate-950'
                }`}
              >
                <span className="mb-1 block text-xs font-black">Sentence {sentence.order}</span>
                {sentence.text}
              </button>
            ))}
          </div>
        </SurfaceCard>
      </div> : (
        <SurfaceCard>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.18em] text-primary">Full Text Selection</p>
              <h2 className="mt-1 text-lg font-black text-slate-950">全文自主选句</h2>
              <p className="mt-1 text-sm leading-6 text-slate-500">点击一句进入右侧精读；拖选单词或短语可查看语境翻译。</p>
            </div>
            <Languages className="size-5 shrink-0 text-primary" />
          </div>
          <div
            ref={fullTextRef}
            lang="en"
            tabIndex={0}
            onPointerUp={captureSelectionAfterPointer}
            onKeyUp={captureSelectionAfterPointer}
            className="mt-5 max-h-[70vh] select-text overflow-y-auto rounded-xl border border-slate-200 bg-slate-50 p-5 text-base leading-8 text-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary sm:p-7 sm:text-lg sm:leading-9"
          >
            {sentences.map((sentence) => (
              <span key={sentence.id} className="mr-1 inline">
                <span data-reading-sentence-id={sentence.id} className={`cursor-text select-text rounded px-1 ${selectedSentenceId === sentence.id ? 'bg-indigo-100 text-indigo-950' : ''}`}>
                  {sentence.text}
                </span>
                <button
                  type="button"
                  aria-label={`拆解第 ${sentence.order} 句`}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => selectSentenceForAnalysis(sentence)}
                  className="ml-0.5 mr-1 inline rounded bg-indigo-50 px-1.5 py-0.5 align-middle text-[10px] font-black leading-5 text-indigo-600 hover:bg-indigo-100 focus-visible:outline-2 focus-visible:outline-primary"
                >
                  拆句
                </button>
              </span>
            ))}
          </div>
          {selection ? (
            <div className="mt-4 rounded-xl border border-indigo-200 bg-indigo-50 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-xs font-black text-indigo-600">已选择</p>
                  <p className="mt-1 text-base font-black text-indigo-950">{selection.text}</p>
                </div>
                <Button disabled={translationStatus === 'loading'} onClick={() => void translateSelection()}>
                  <Languages className="size-4" />{translationStatus === 'loading' ? '正在翻译' : '划词翻译'}
                </Button>
              </div>
              {translation ? (
                <div className="mt-3 rounded-lg bg-white p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-base font-black text-slate-950">{translation.translation}</p>
                    {translation.source === 'base_dictionary' ? (
                      <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-black text-emerald-800">
                        基础词库
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-sm leading-6 text-slate-600">{translation.context_note}</p>
                  <Button
                    variant="secondary"
                    className="mt-3"
                    disabled={selectedSentenceId !== selection.sentence.id}
                    onClick={() => onNotesChange(
                      'phraseNotes',
                      [notes.phraseNotes, `${selection.text}：${translation.translation}（${translation.context_note}）`]
                        .filter(Boolean)
                        .join('\n')
                    )}
                  >
                    记入词组笔记
                  </Button>
                </div>
              ) : null}
              {translationStatus === 'error' ? <p className="mt-2 text-sm font-bold text-rose-700">翻译暂时失败，请重新选择后再试。</p> : null}
            </div>
          ) : null}
        </SurfaceCard>
      )}

      <div className="grid gap-5">
        <SurfaceCard>
          <div className="flex items-center gap-2">
            <Highlighter className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-black text-slate-950">当前句子拆解</h2>
          </div>
          {selectedSentence ? (
            <>
              <p className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-base leading-7 text-slate-800">
                {selectedSentence.text}
              </p>
              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                {focusHints.map((hint) => (
                  <div key={hint.id} className="rounded-lg border border-slate-200 p-3">
                    <p className="text-sm font-black text-slate-950">{hint.label}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-500">{hint.text}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 grid gap-4 lg:grid-cols-3">
                <FormField
                  as="textarea"
                  label="主干识别"
                  name="reading_main_structure"
                  autoComplete="off"
                  value={notes.mainStructure}
                  onChange={(event) => onNotesChange('mainStructure', event.target.value)}
                  placeholder="S + V + O/C…"
                />
                <FormField
                  as="textarea"
                  label="词组和搭配"
                  name="reading_phrase_notes"
                  autoComplete="off"
                  value={notes.phraseNotes}
                  onChange={(event) => onNotesChange('phraseNotes', event.target.value)}
                  placeholder="记录值得复用的短语…"
                />
                <FormField
                  as="textarea"
                  label="细节证据"
                  name="reading_evidence_note"
                  autoComplete="off"
                  value={notes.evidenceNote}
                  onChange={(event) => onNotesChange('evidenceNote', event.target.value)}
                  placeholder="这句话支持了哪一个细节…"
                />
              </div>
              <div className="mt-4 flex flex-col gap-3 rounded-xl border border-indigo-100 bg-indigo-50/60 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-black text-indigo-950">先交你的分析，再看系统拆解</p>
                  <p className="mt-1 text-sm leading-6 text-indigo-800">提交后才会评估掌握度、记录错误模式并动态映射 Can-Do。</p>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    disabled={analysisStatus === 'submitting'}
                    onClick={() => onSubmitAnalysis(true)}
                  >
                    我分析不出来
                  </Button>
                  <Button
                    disabled={!hasAnalysisAttempt || analysisStatus === 'submitting'}
                    onClick={() => onSubmitAnalysis(false)}
                  >
                    {analysisStatus === 'submitting' ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <SearchCheck className="h-4 w-4" />}
                    {analysisStatus === 'submitting' ? '正在评估' : '提交分析'}
                  </Button>
                </div>
              </div>
              {analysisStatus === 'error' ? (
                <div className="mt-3">
                  <StatusBanner tone="warning" title={analysisFailure?.title ?? '句子分析暂时失败'}>
                    {analysisFailure?.message ?? '你的作答仍保留在本地，可以直接重试。'}
                  </StatusBanner>
                </div>
              ) : null}
            </>
          ) : (
            <p className="mt-4 text-sm text-muted-foreground">材料中还没有可选择的句子。</p>
          )}
        </SurfaceCard>

        <SurfaceCard>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <ExternalLink className="h-5 w-5 text-success" />
              <h2 className="text-lg font-black text-slate-950">动态发现 Can-Do</h2>
            </div>
            <p className="text-xs text-muted-foreground">来自当前句子与真实作答，不使用固定知识点列表。</p>
          </div>
          {analysisResult ? (
            <div className="mt-4 grid gap-3">
              {analysisResult.can_do_points.length > 0 ? analysisResult.can_do_points.map((point) => (
                <div key={point.can_do_id} className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-white px-2 py-1 text-xs font-black text-emerald-800">{point.cefr_level}</span>
                    <span className="text-xs font-bold text-emerald-700">{point.category} · {point.subcategory}</span>
                  </div>
                  <p className="mt-2 text-sm font-black leading-6 text-slate-950">{point.statement}</p>
                </div>
              )) : <p className="text-sm leading-6 text-slate-500">当前句子没有可靠匹配到 Can-Do，系统没有据此更新掌握度。</p>}
              <Button variant="secondary" onClick={() => onOpenWorkspace('review')}>
                <ClipboardList className="h-4 w-4" />查看本句复盘
              </Button>
            </div>
          ) : (
            <p className="mt-4 text-sm leading-6 text-slate-500">提交自主拆解后，系统会从 Can-Do 目录召回候选，并只保留与本句和本次作答有证据关联的知识点。</p>
          )}
        </SurfaceCard>
      </div>
      </section>
    </div>
  )
}

function ReviewWorkspace({
  canComplete,
  completeStatus,
  completionResult,
  extensiveNotes,
  intensiveNotesBySentenceId,
  sentenceAnalysisBySentenceId,
  keywordCandidates,
  material,
  missingLabels,
  selectedSentences,
  sentences,
  sourceLabel,
  wordCount,
  onCompleteReading,
  onOpenWorkspace,
}: {
  canComplete: boolean
  completeStatus: MaterialCompleteStatus
  completionResult: ReadingMaterialCompleteResponse | null
  extensiveNotes: ExtensiveNotes
  intensiveNotesBySentenceId: IntensiveNotesBySentenceId
  sentenceAnalysisBySentenceId: Record<string, ReadingSentenceAnalysisResponse>
  keywordCandidates: ReadingKeywordCandidate[]
  material: ReadingMaterial
  missingLabels: string[]
  selectedSentences: ReadingSentence[]
  sentences: ReadingSentence[]
  sourceLabel: string | null
  wordCount: number
  onCompleteReading: () => void
  onOpenWorkspace: (workspace: ReadingWorkspace) => void
}) {
  const analyses = Object.values(sentenceAnalysisBySentenceId)
  const canDoPoints = Array.from(new Map(
    analyses
      .flatMap((result) => result.can_do_points)
      .map((point) => [point.can_do_id, point] as const)
  ).values())
  const errorPatterns = Array.from(new Map(
    analyses
      .flatMap((result) => result.error_patterns)
      .map((pattern) => [pattern.tag, pattern] as const)
  ).values())
  const recommendedDrills = uniqueList(
    analyses
      .flatMap((result) => result.error_patterns.map((pattern) => pattern.recommended_drill))
  )
  const needsSupportCount = analyses.filter((result) => result.outcome !== 'SUCCESS').length
  const masteryUpdateCount = canDoPoints.filter((point) => point.evidence_status === 'applied').length
  const primaryError = errorPatterns[0] ?? null
  const primaryDrill = recommendedDrills[0] ?? null
  return (
    <section className="grid items-start gap-5 2xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="grid gap-5">
        <SurfaceCard className="overflow-hidden border-indigo-200 bg-gradient-to-br from-white via-white to-indigo-50/80">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-primary">Review priority</p>
              <div className="mt-2 flex items-center gap-2">
                <ClipboardList className="h-5 w-5 text-primary" />
                <h2 className="text-xl font-black text-slate-950">本次最重要的收获</h2>
              </div>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
                {material.title.trim() || '未命名材料'} · {wordCount} 词 · {READING_GOAL_LABELS[material.goal]}
              </p>
            </div>
            <span className="w-fit rounded-full border border-indigo-200 bg-white px-3 py-1.5 text-xs font-black text-indigo-700">
              已复盘 {analyses.length}/{sentences.length} 句
            </span>
          </div>

          {analyses.length > 0 ? (
            <div className="mt-5 grid gap-3 lg:grid-cols-3">
              <ReviewPriorityItem
                index="01"
                label="先看结论"
                value={needsSupportCount > 0
                  ? `${needsSupportCount} 句需要纠错或教学支持`
                  : '已分析句子的主干与层级基本正确'}
                tone={needsSupportCount > 0 ? 'warning' : 'success'}
              />
              <ReviewPriorityItem
                index="02"
                label="关键卡点"
                value={primaryError?.description ?? '本次没有形成稳定错误模式'}
                tone={primaryError ? 'warning' : 'neutral'}
              />
              <ReviewPriorityItem
                index="03"
                label="下一步"
                value={primaryDrill ?? (masteryUpdateCount > 0
                  ? `已有 ${masteryUpdateCount} 个 Can-Do 获得掌握证据`
                  : '继续选择一个长句完成自主拆解')}
                tone="primary"
              />
            </div>
          ) : (
            <div className="mt-5 rounded-xl border border-dashed border-indigo-200 bg-white/80 p-4">
              <p className="text-sm font-black text-slate-950">还没有可归纳的精读结论</p>
              <p className="mt-1 text-sm leading-6 text-slate-600">先完成至少一个句子的自主分析或教学拆解，这里会提炼关键卡点与下一步。</p>
            </div>
          )}
        </SurfaceCard>

        {material.goal !== 'extensive' ? (
          <SurfaceCard>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.14em] text-primary">Sentence review</p>
                <h2 className="mt-1 text-lg font-black text-slate-950">逐句精读复盘</h2>
                <p className="mt-1 text-sm leading-6 text-slate-600">每句先看结论和关键纠错，需要时再展开完整拆解与原作答。</p>
              </div>
              <span className="text-xs font-bold text-slate-500">按句子顺序排列</span>
            </div>
            <div className="mt-5 grid gap-4">
              {selectedSentences.length > 0 ? selectedSentences.map((sentence) => (
                <SentenceReviewBlock
                  key={sentence.id}
                  sentence={sentence}
                  notes={intensiveNotesBySentenceId[sentence.id] ?? EMPTY_INTENSIVE_NOTES}
                  analysis={sentenceAnalysisBySentenceId[sentence.id]}
                />
              )) : (
                <div className="rounded-xl border border-dashed border-slate-200 p-5 text-sm leading-6 text-muted-foreground">
                  还没有完成可沉淀的精读句。回到精读模式，先提交自己的拆解或选择“我分析不出来”。
                </div>
              )}
            </div>
          </SurfaceCard>
        ) : null}

        {material.goal !== 'intensive' ? (
          <SurfaceCard>
            <div className="flex items-center gap-2">
              <Gauge className="h-5 w-5 text-primary" />
              <h2 className="text-lg font-black text-slate-950">泛读理解</h2>
            </div>
            <div className="mt-4">
              <ReviewBlock
                title="本次泛读记录"
                items={[
                  ['主旨', extensiveNotes.gist],
                  ['作者态度', extensiveNotes.attitude],
                  ['段落功能', extensiveNotes.paragraphFunction],
                  ['中心句', extensiveNotes.centralSentence],
                ]}
              />
            </div>
          </SurfaceCard>
        ) : null}

        <SurfaceCard>
          <details className="group">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">Supporting data</p>
                <h2 className="mt-1 text-lg font-black text-slate-950">学习过程数据</h2>
                <p className="mt-1 text-sm leading-6 text-slate-600">关键词、句子难度、流程进度与正文覆盖属于辅助证据，按需展开查看。</p>
              </div>
              <span className="shrink-0 rounded-full bg-slate-100 px-3 py-1.5 text-xs font-black text-slate-600 group-open:bg-primary/10 group-open:text-primary">
                展开数据
              </span>
            </summary>
            <div className="mt-5 border-t border-slate-100 pt-5">
              <div className="grid gap-3 md:grid-cols-3">
                <MetricTile label="材料" value={material.title.trim() || '未命名'} />
                <MetricTile label="词数 / 句子" value={`${wordCount} / ${sentences.length}`} />
                <MetricTile label="目标" value={READING_GOAL_LABELS[material.goal]} />
              </div>
              <div className="mt-4 grid gap-4 2xl:grid-cols-3">
                <KeywordFrequencyChart keywords={keywordCandidates.slice(0, 8)} />
                <SentenceDifficultyHeatmap sentences={sentences} selectedSentences={selectedSentences} />
                <SentenceAnalysisOutcomeChart analyses={sentenceAnalysisBySentenceId} />
              </div>
              <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
                <ReadingFlowProgress
                  extensiveNotes={extensiveNotes}
                  goal={material.goal}
                  isRecorded={completeStatus === 'completed'}
                  selectedSentences={selectedSentences}
                  sentences={sentences}
                />
                <ReadingCoveragePanel selectedSentences={selectedSentences} sentences={sentences} />
              </div>
            </div>
          </details>
        </SurfaceCard>
      </div>

      <div className="grid gap-5 2xl:sticky 2xl:top-6">
        <SurfaceCard className="border-indigo-200 bg-indigo-50/50">
          <div className="flex items-center gap-2">
            <ListChecks className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-black text-slate-950">下一步练什么</h2>
          </div>
          <div className="mt-4 grid gap-3">
            {recommendedDrills.length > 0 ? (
              recommendedDrills.map((drill, index) => (
                <div key={drill} className="flex gap-3 rounded-xl border border-indigo-100 bg-white p-3">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-black text-primary-foreground">
                    {index + 1}
                  </span>
                  <p className="text-sm font-bold leading-6 text-slate-800">{drill}</p>
                </div>
              ))
            ) : (
              <div className="rounded-xl border border-emerald-100 bg-white p-3">
                <p className="text-sm font-black text-emerald-800">本次没有新增错误模式</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">可以继续精读下一句，积累更多真实作答证据。</p>
              </div>
            )}
          </div>
          <div className="mt-4 grid gap-2">
            <Button onClick={() => onOpenWorkspace('intensive')}>
              <Highlighter className="h-4 w-4" />继续精读句子
            </Button>
            {material.goal !== 'intensive' ? (
              <Button variant="secondary" onClick={() => onOpenWorkspace('extensive')}>
                <Gauge className="h-4 w-4" />回到泛读任务
              </Button>
            ) : null}
          </div>
        </SurfaceCard>

        <SurfaceCard>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-success" />
            <h2 className="text-lg font-black text-slate-950">Can-Do 与掌握证据</h2>
          </div>
          <div className="mt-4 space-y-3">
            {canDoPoints.length > 0 ? (
              canDoPoints.map((point) => {
                const before = Math.round((point.mastery_before ?? 0) * 100)
                const after = Math.round((point.mastery_after ?? 0) * 100)
                return (
                  <div key={point.can_do_id} className="rounded-xl border border-slate-200 p-3">
                    <p className="text-xs font-black text-primary">{point.cefr_level} · {point.category}</p>
                    <p className="mt-1 text-sm font-black leading-6 text-slate-950">{point.statement}</p>
                    {point.evidence_status === 'applied' ? (
                      <div className="mt-3">
                        <div className="flex items-center justify-between text-xs font-bold text-slate-500">
                          <span>掌握度变化</span>
                          <span>{before}% → {after}%</span>
                        </div>
                        <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
                          <div className="h-full rounded-full bg-success" style={{ width: `${after}%` }} />
                        </div>
                      </div>
                    ) : (
                      <p className="mt-2 text-xs leading-5 text-slate-500">本次仅作为教学线索，没有更新掌握度。</p>
                    )}
                  </div>
                )
              })
            ) : (
              <p className="text-sm leading-6 text-muted-foreground">暂无可靠 Can-Do 映射；系统不会用不确定匹配更新掌握度。</p>
            )}
          </div>
        </SurfaceCard>

        <SurfaceCard>
          <div className="flex items-center gap-2">
            <BookOpenCheck className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-black text-slate-950">保存本次阅读证据</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            {sourceLabel ? `${sourceLabel} · ` : ''}投入值只反映材料长度与精读覆盖，不代表正确率或能力分。
          </p>
          <div className="mt-4">
            {completionResult ? (
              <StatusBanner tone="success" title="阅读练习证据已保存">本次阅读投入值 +{completionResult.reading_value}。</StatusBanner>
            ) : completeStatus === 'error' ? (
              <StatusBanner tone="warning" title="记录保存失败">请检查网络后重试；当前笔记仍保留在页面中。</StatusBanner>
            ) : !canComplete ? (
              <StatusBanner tone="warning" title="还差一点才能沉淀">请先{missingLabels.join('、')}。</StatusBanner>
            ) : (
              <StatusBanner title="已达到沉淀条件">确认后会写入本次阅读证据。</StatusBanner>
            )}
          </div>
          <Button
            className="mt-5 w-full"
            disabled={!canComplete || completeStatus === 'saving' || completeStatus === 'completed'}
            onClick={onCompleteReading}
          >
            <CheckCircle2 className="h-4 w-4" />
            {completeStatus === 'saving' ? '正在记录' : completeStatus === 'completed' ? '已完成阅读' : '完成阅读'}
          </Button>
        </SurfaceCard>
      </div>
    </section>
  )
}

function ReviewPriorityItem({
  index,
  label,
  tone,
  value,
}: {
  index: string
  label: string
  tone: 'neutral' | 'primary' | 'success' | 'warning'
  value: string
}) {
  const toneClass = {
    neutral: 'border-slate-200 bg-white text-slate-700',
    primary: 'border-indigo-200 bg-indigo-50 text-indigo-900',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-900',
    warning: 'border-amber-200 bg-amber-50 text-amber-950',
  }[tone]
  return (
    <div className={`rounded-xl border p-4 ${toneClass}`}>
      <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[0.12em] opacity-70">
        <span>{index}</span>
        <span>{label}</span>
      </div>
      <p className="mt-2 text-sm font-black leading-6">{value}</p>
    </div>
  )
}

function ReadingFlowProgress({
  extensiveNotes,
  goal,
  isRecorded,
  selectedSentences,
  sentences,
}: {
  extensiveNotes: ExtensiveNotes
  goal: ReadingTrainingGoal
  isRecorded: boolean
  selectedSentences: ReadingSentence[]
  sentences: ReadingSentence[]
}) {
  const steps = [
    { label: '阅读材料', done: sentences.length > 0 },
    ...(goal !== 'intensive' ? [{
      label: '泛读证据',
      done: Boolean(extensiveNotes.gist.trim() && extensiveNotes.centralSentence.trim()),
    }] : []),
    ...(goal !== 'extensive' ? [{
      label: '精读句',
      done: selectedSentences.length > 0,
    }] : []),
    { label: '沉淀记录', done: isRecorded },
  ]
  const completed = steps.filter((step) => step.done).length
  const percent = steps.length > 0 ? Math.round((completed / steps.length) * 100) : 0
  const sentenceCoverage = sentences.length > 0 ? Math.round((selectedSentences.length / sentences.length) * 100) : 0

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-black text-slate-950">阅读流程进度</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            按当前训练目标计算，只有留下有效证据才会记为完成。
          </p>
        </div>
        <span className="text-2xl font-black text-slate-950">{percent}%</span>
      </div>
      <div className="mt-4 h-3 overflow-hidden rounded-full bg-white">
        <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${percent}%` }} />
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        {steps.map((step) => (
          <div
            key={step.label}
            className={`rounded-lg border px-3 py-2 text-xs font-bold ${
              step.done
                ? 'border-success/20 bg-success/10 text-success'
                : 'border-slate-200 bg-white text-slate-500'
            }`}
          >
            {step.done ? '已完成' : '待补'} · {step.label}
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs font-semibold text-muted-foreground">
        {goal === 'extensive'
          ? '本次为泛读目标，精读句不计入完成条件。'
          : `精读覆盖 ${selectedSentences.length}/${sentences.length} 句，约 ${sentenceCoverage}%。`}
      </p>
    </div>
  )
}

function ReadingCoveragePanel({
  selectedSentences,
  sentences,
}: {
  selectedSentences: ReadingSentence[]
  sentences: ReadingSentence[]
}) {
  const selectedIds = new Set(selectedSentences.map((sentence) => sentence.id))
  const percent = sentences.length > 0 ? Math.round((selectedSentences.length / sentences.length) * 100) : 0
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-black text-slate-950">正文高亮覆盖</p>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">
        深色块表示已经进入精读的句子位置。
      </p>
      <div className="mt-4 flex h-12 overflow-hidden rounded-xl border border-slate-200 bg-white p-1">
        {sentences.length > 0 ? (
          sentences.map((sentence) => {
            const isSelected = selectedIds.has(sentence.id)
            return (
              <span
                key={sentence.id}
                className={`mx-0.5 flex min-w-3 flex-1 items-center justify-center rounded-lg text-[10px] font-black transition-colors ${
                  isSelected ? 'bg-primary text-primary-foreground' : 'bg-slate-100 text-slate-400'
                }`}
                title={`Sentence ${sentence.order}${isSelected ? '，已精读' : '，未精读'}`}
              >
                {sentence.order}
              </span>
            )
          })
        ) : (
          <span className="flex flex-1 items-center justify-center text-xs font-semibold text-slate-400">
            还没有可分析的句子
          </span>
        )}
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <MetricTile label="覆盖率" value={`${percent}%`} />
        <MetricTile label="已精读" value={`${selectedSentences.length}/${sentences.length}`} />
      </div>
    </div>
  )
}

function EmptyMaterialCard({ onOpenInput }: { onOpenInput: () => void }) {
  return (
    <SurfaceCard className="min-h-[360px]">
      <div className="flex h-full flex-col items-center justify-center text-center">
        <FileText className="h-10 w-10 text-muted-foreground" />
        <h2 className="mt-4 text-lg font-black text-slate-950">先添加一段英文材料</h2>
        <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
          粘贴材料后再进入泛读或精读，工作区会自动分句并生成本地训练提示。
        </p>
        <Button className="mt-5" onClick={onOpenInput}>
          返回材料输入
        </Button>
      </div>
    </SurfaceCard>
  )
}

function MetricTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 truncate text-base font-black text-slate-950">{value}</p>
    </div>
  )
}

function KeywordFrequencyChart({ keywords }: { keywords: ReadingKeywordCandidate[] }) {
  const maxCount = Math.max(...keywords.map((keyword) => keyword.count), 1)
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <h3 className="text-sm font-black text-slate-950">关键词频次</h3>
      <div className="mt-3 space-y-2">
        {keywords.length > 0 ? (
          keywords.map((keyword) => (
            <div key={keyword.word} className="grid grid-cols-[80px_minmax(0,1fr)_28px] items-center gap-2">
              <span className="truncate text-xs font-bold text-slate-600">{keyword.word}</span>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-500"
                  style={{ width: `${(keyword.count / maxCount) * 100}%` }}
                />
              </div>
              <span className="text-right text-xs font-black text-slate-500">{keyword.count}</span>
            </div>
          ))
        ) : (
          <p className="text-sm leading-6 text-slate-500">材料较短，暂未形成关键词频次。</p>
        )}
      </div>
    </div>
  )
}

function SentenceDifficultyHeatmap({
  selectedSentences,
  sentences,
}: {
  selectedSentences: ReadingSentence[]
  sentences: ReadingSentence[]
}) {
  const selectedIds = new Set(selectedSentences.map((sentence) => sentence.id))
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-black text-slate-950">句子难度热力图</h3>
        <span className="text-xs font-bold text-slate-500">按词数估算</span>
      </div>
      <div className="mt-3 grid grid-cols-8 gap-2 sm:grid-cols-10">
        {sentences.length > 0 ? (
          sentences.map((sentence) => {
            const wordCount = countEnglishWords(sentence.text)
            const intensity = Math.min(1, 0.18 + wordCount / 28)
            const isSelected = selectedIds.has(sentence.id)
            return (
              <span
                key={sentence.id}
                className={`flex aspect-square items-center justify-center rounded-[4px] text-[10px] font-black ring-1 ring-inset ${
                  isSelected ? 'text-indigo-950 ring-indigo-500' : 'text-slate-600 ring-slate-200'
                }`}
                style={{ backgroundColor: `rgb(99 102 241 / ${intensity.toFixed(2)})` }}
                title={`Sentence ${sentence.order}: ${wordCount} words${isSelected ? '，已精读' : ''}`}
              >
                {sentence.order}
              </span>
            )
          })
        ) : (
          <span className="col-span-full text-sm leading-6 text-slate-500">添加材料后会显示句子难度。</span>
        )}
      </div>
      <p className="mt-3 text-xs font-semibold text-slate-500">深色代表句子更长；描边代表你在精读中选中过。</p>
    </div>
  )
}

function SentenceAnalysisOutcomeChart({
  analyses,
}: {
  analyses: Record<string, ReadingSentenceAnalysisResponse>
}) {
  const values = Object.values(analyses)
  const rows = [
    { label: '自主分析正确', value: values.filter((item) => item.outcome === 'SUCCESS').length, tone: 'bg-success' },
    { label: '分析后纠错', value: values.filter((item) => item.outcome === 'UNSUCCESSFUL').length, tone: 'bg-amber-500' },
    { label: '教学拆解', value: values.filter((item) => item.outcome === 'NO_ATTEMPT').length, tone: 'bg-primary' },
  ].filter((row) => row.value > 0)
  const maxValue = Math.max(...rows.map((row) => row.value), 1)

  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-black text-slate-950">句子分析结果</h3>
        <span className="text-xs font-bold text-slate-500">真实提交</span>
      </div>
      <div className="mt-3 space-y-2">
        {rows.length > 0 ? (
          rows.map((row) => (
            <div key={row.label}>
              <div className="flex justify-between gap-3 text-xs font-bold text-slate-500">
                <span className="truncate">{row.label}</span>
                <span>{row.value}</span>
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className={`h-full rounded-full transition-[width] duration-500 ${row.tone}`}
                  style={{ width: `${(row.value / maxValue) * 100}%` }}
                />
              </div>
            </div>
          ))
        ) : (
          <p className="text-sm leading-6 text-slate-500">提交精读句子分析后，这里会显示评估分布。</p>
        )}
      </div>
    </div>
  )
}

function HistoryItem({ item, onRestore }: { item: ReadingMaterialHistoryItem; onRestore: () => void }) {
  const title = item.title?.trim() || '未命名阅读材料'
  const preview = item.text.length > 118 ? `${item.text.slice(0, 118)}…` : item.text

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-black text-slate-950">{title}</p>
          <p className="mt-1 text-xs text-slate-500">{formatHistoryTime(item.updated_at)}</p>
        </div>
        <Button className="shrink-0 px-3 py-2 text-xs" variant="secondary" onClick={onRestore}>
          恢复
        </Button>
      </div>
      <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-500">{preview}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-bold text-slate-600">
          {item.word_count} 词
        </span>
        <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-bold text-slate-600">
          {item.sentence_count} 句
        </span>
        <span className="rounded-md bg-primary/10 px-2 py-1 text-xs font-bold text-primary">
          {READING_LEVEL_LABELS[item.level]}
        </span>
        <span className="rounded-md bg-success/10 px-2 py-1 text-xs font-bold text-success">
          {READING_GOAL_LABELS[item.goal]}
        </span>
      </div>
    </div>
  )
}

function ModeStep({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <p className="text-sm font-black text-slate-950">{title}</p>
      <p className="mt-1 text-sm leading-6 text-slate-500">{text}</p>
    </div>
  )
}

function formatHistoryTime(value: string) {
  const time = new Date(value)
  if (Number.isNaN(time.getTime())) return '时间未知'
  return time.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function SentenceReviewBlock({
  analysis,
  notes,
  sentence,
}: {
  analysis: ReadingSentenceAnalysisResponse
  notes: IntensiveNotes
  sentence: ReadingSentence
}) {
  const isSuccess = analysis.outcome === 'SUCCESS'
  const isNoAttempt = analysis.outcome === 'NO_ATTEMPT'
  const primaryError = analysis.error_patterns[0] ?? null
  const outcomeLabel = isSuccess ? '基本掌握' : isNoAttempt ? '教学复盘' : '需要纠错'
  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <div className="border-b border-slate-100 px-4 py-4 sm:px-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-950 text-xs font-black text-white">{sentence.order}</span>
            <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">Sentence review</p>
          </div>
          <div className="flex items-center gap-2">
            {!isNoAttempt ? (
              <span className="text-xs font-bold text-slate-500">{Math.round(analysis.score * 100)} 分</span>
            ) : null}
            <span className={`rounded-full px-2.5 py-1 text-xs font-black ${
              isSuccess
                ? 'bg-emerald-100 text-emerald-800'
                : isNoAttempt
                  ? 'bg-indigo-100 text-indigo-800'
                  : 'bg-amber-100 text-amber-900'
            }`}>
              {outcomeLabel}
            </span>
          </div>
        </div>
        <p lang="en" className="mt-3 text-base font-bold leading-7 text-slate-900">{sentence.text}</p>
      </div>

      <div className="grid gap-4 p-4 sm:p-5">
        <div className={`rounded-xl border p-4 ${
          isSuccess ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50'
        }`}>
          <p className="text-xs font-black uppercase tracking-[0.12em] text-slate-500">本句结论</p>
          <p className="mt-2 text-sm font-black leading-6 text-slate-950">{analysis.feedback}</p>
        </div>

        {primaryError ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
            <p className="text-xs font-black uppercase tracking-[0.12em] text-rose-700">最需要纠正</p>
            <p className="mt-2 text-sm font-black leading-6 text-rose-950">{primaryError.description}</p>
            <p className="mt-2 text-sm leading-6 text-rose-800">针对练习：{primaryError.recommended_drill}</p>
          </div>
        ) : null}

        <div className="grid gap-3 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-black uppercase tracking-[0.12em] text-slate-500">正确主干</p>
            <p className="mt-2 text-sm font-black leading-6 text-slate-950">{analysis.correct_analysis.main_structure}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-black uppercase tracking-[0.12em] text-slate-500">整句含义</p>
            <p className="mt-2 text-sm leading-6 text-slate-800">{analysis.correct_analysis.sentence_meaning}</p>
          </div>
        </div>

        {analysis.teaching.required ? (
          <div className="rounded-xl border border-indigo-200 bg-indigo-50/70 p-4">
            <p className="text-sm font-black text-indigo-950">下次按这个顺序拆</p>
            {analysis.teaching.explanation ? (
              <p className="mt-1 text-sm leading-6 text-indigo-800">{analysis.teaching.explanation}</p>
            ) : null}
            <ol className="mt-3 grid gap-2">
              {analysis.teaching.steps.map((step, index) => (
                <li key={step} className="flex gap-3 rounded-lg bg-white/80 p-2.5 text-sm leading-6 text-slate-800">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs font-black text-white">{index + 1}</span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
            <p className="mt-3 rounded-lg border border-indigo-200 bg-white px-3 py-2 text-sm font-bold text-indigo-800">
              自检：{analysis.teaching.checkpoint}
            </p>
          </div>
        ) : null}

        <details className="group rounded-xl border border-slate-200">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-black text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30">
            <span>查看完整拆解与我的作答</span>
            <span className="text-xs text-slate-400 group-open:text-primary">展开</span>
          </summary>
          <div className="grid gap-4 border-t border-slate-100 p-4 lg:grid-cols-2">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.12em] text-slate-500">我的作答</p>
              <div className="mt-3 grid gap-3">
                {[
                  ['主干', notes.mainStructure],
                  ['词组搭配', notes.phraseNotes],
                  ['细节证据', notes.evidenceNote],
                ].map(([label, value]) => (
                  <div key={label}>
                    <p className="text-xs font-bold text-slate-500">{label}</p>
                    <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-700">{value.trim() || '未填写'}</p>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p className="text-xs font-black uppercase tracking-[0.12em] text-slate-500">完整结构</p>
              <div className="mt-3 grid gap-3">
                <div>
                  <p className="text-xs font-bold text-slate-500">从句层级</p>
                  {analysis.correct_analysis.clause_layers.length > 0 ? (
                    <ul className="mt-1 space-y-1 text-sm leading-6 text-slate-700">
                      {analysis.correct_analysis.clause_layers.map((layer) => <li key={layer}>• {layer}</li>)}
                    </ul>
                  ) : <p className="mt-1 text-sm text-slate-500">本句没有需要单独标出的从句层级。</p>}
                </div>
                <div>
                  <p className="text-xs font-bold text-slate-500">重点短语</p>
                  {analysis.correct_analysis.phrases.length > 0 ? (
                    <div className="mt-2 grid gap-2">
                      {analysis.correct_analysis.phrases.map((phrase) => (
                        <div key={`${phrase.text}-${phrase.role}`} className="rounded-lg bg-slate-50 p-2.5">
                          <p className="text-sm font-black text-slate-900">{phrase.text}</p>
                          <p className="mt-1 text-xs leading-5 text-slate-500">{phrase.role} · {phrase.meaning}</p>
                        </div>
                      ))}
                    </div>
                  ) : <p className="mt-1 text-sm text-slate-500">本句没有额外标出的重点短语。</p>}
                </div>
              </div>
            </div>
          </div>
        </details>
      </div>
    </article>
  )
}

function ReviewBlock({ title, items }: { title: string; items: Array<[string, string]> }) {
  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <h3 className="text-sm font-black text-slate-950">{title}</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {items.map(([label, value]) => (
          <div key={label} className="rounded-lg bg-slate-50 p-3">
            <p className="text-xs font-bold text-slate-500">{label}</p>
            <p className="mt-1 min-h-6 text-sm font-semibold leading-6 text-slate-700">{value.trim() || '未填写'}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function isReadingMaterialHistoryItem(
  value: ReadingMaterial | ReadingMaterialHistoryItem | undefined
): value is ReadingMaterialHistoryItem {
  return Boolean(value && 'id' in value && typeof value.id === 'string')
}

function hasAnyIntensiveNote(notes: IntensiveNotes): boolean {
  return Boolean(notes.mainStructure.trim() || notes.phraseNotes.trim() || notes.evidenceNote.trim())
}

function getPendingMaterialDialogCopy(pending: PendingMaterialSwitch | null): {
  title: string
  description: string
  confirmLabel: string
} {
  switch (pending?.kind) {
    case 'edit':
      return {
        title: '修改材料并重置进度？',
        description: '当前的泛读、精读笔记和阅读助手记录会被清空；新文本会保留为未保存状态。',
        confirmLabel: '重置并修改',
      }
    case 'generate':
      return {
        title: '生成新材料并替换当前进度？',
        description: '材料生成成功后才会切换；当前笔记和阅读助手记录会一直保留到那时。',
        confirmLabel: '生成并切换',
      }
    case 'generated':
      return {
        title: '新材料已生成，是否切换？',
        description: '生成期间检测到新的阅读记录，因此没有自动替换。切换会清空当前笔记和阅读助手记录。',
        confirmLabel: '切换到新材料',
      }
    case 'back':
    case 'external-navigation':
      return {
        title: '离开本次阅读？',
        description: '未保存材料、阅读笔记或助手草稿会从当前工作区移除；已保存材料仍可从历史中找回。',
        confirmLabel: '确认离开',
      }
    default:
      return {
        title: '切换阅读材料？',
        description: '当前的未保存材料、泛读与精读笔记和阅读助手记录会被清空。',
        confirmLabel: '切换材料',
      }
  }
}

function getReadingLiveStatusMessage({
  coachStatus,
  completeStatus,
  generationStatus,
  saveStatus,
}: {
  coachStatus: 'idle' | 'sending' | 'error'
  completeStatus: MaterialCompleteStatus
  generationStatus: 'idle' | 'generating' | 'error'
  saveStatus: MaterialSaveStatus
}): string {
  if (completeStatus === 'saving') return '正在记录阅读证据。'
  if (completeStatus === 'completed') return '阅读练习证据已保存。'
  if (completeStatus === 'error') return '阅读证据记录失败，请重试。'
  if (generationStatus === 'generating') return '正在生成个性化阅读材料。'
  if (generationStatus === 'error') return '个性化阅读材料生成失败，请重试。'
  if (saveStatus === 'saving') return '正在保存阅读材料。'
  if (saveStatus === 'saved') return '阅读材料已保存。'
  if (saveStatus === 'error') return '阅读材料保存失败，请重试。'
  if (coachStatus === 'sending') return '阅读助手正在回复。'
  if (coachStatus === 'error') return '阅读助手回复失败，问题已保留。'
  return ''
}

function findReadingSentenceId(node: Node): string | null {
  const element = node.nodeType === Node.ELEMENT_NODE
    ? node as Element
    : node.parentElement
  return element?.closest<HTMLElement>('[data-reading-sentence-id]')?.dataset.readingSentenceId ?? null
}
