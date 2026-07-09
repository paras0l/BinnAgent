import { AlertCircle, ArrowRight, BookCheck, BookMarked, BookOpen, BookOpenCheck, CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, Clock3, Dumbbell, FileText, GraduationCap, Languages, Layers3, LibraryBig, ListChecks, ListTree, LoaderCircle, Send, Sparkles, Trash2, UploadCloud, X } from 'lucide-react'
import { useCallback, useEffect, useId, useMemo, useState, type KeyboardEventHandler, type ReactNode, type Ref } from 'react'
import type { CapabilityRecommendation } from '@/components/learning/CapabilityRecommendationCard'
import { PageShell } from '@/components/layout/PageShell'
import { CurriculumRail } from '@/components/knowledge/CurriculumRail'
import { ExerciseSessionDialog } from '@/components/knowledge/ExerciseSessionDialog'
import { KnowledgeContextPanel } from '@/components/knowledge/KnowledgeContextPanel'
import { LessonSessionDialog } from '@/components/knowledge/LessonSessionDialog'
import { UploadTextbookDialog } from '@/components/knowledge/UploadTextbookDialog'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { IconButton } from '@/components/ui/IconButton'
import { Select } from '@/components/ui/Select'
import { StatusBanner } from '@/components/ui/StatusBanner'
import { useFocusTrap } from '@/hooks/useFocusTrap'
import { useToast } from '@/hooks/useToast'
import { GrammarPage } from '@/pages/GrammarPage'
import { ReadingWorkshopPage } from '@/pages/ReadingWorkshopPage'
import { deleteKnowledgeSource } from '@/api/knowledge'
import {
  READING_MATERIAL_LENGTH_LABELS,
  READING_MATERIAL_TYPE_LABELS,
  type ReadingMaterial,
  type ReadingMaterialGenerationResponse,
  type ReadingMaterialLength,
  type ReadingMaterialType,
} from '@/data/readingWorkshop'
import { exploreCapabilityEventUrl } from '@/services/exploreCapabilityApi'
import {
  formatFailedIngestMessage,
  hasScannedPdfSignal,
  normalizeBlockingReasons,
} from '@/utils/knowledgeIngest'
import type {
  ExerciseSession,
  FailedKnowledgeSourceDetail,
  KnowledgeAttemptResult,
  KnowledgeBaseOverview,
  KnowledgeIngestResult,
  KnowledgeIngestStatus,
  KnowledgeLessonCompleteResult,
  KnowledgeLessonSession,
  KnowledgeUploadResult,
  Learner,
  PronunciationWorkspace,
  UnitLearningWorkspace,
  UnitWorkspaceActionType,
  UnitWorkspaceItem,
  UnitWorkspaceSection,
  UnitVocabularySummary,
} from '@/types'
import type { VocabularyPracticeMode } from '@/pages/VocabularyPracticePage'

interface KnowledgeBasePageProps {
  learner: Learner
  onBack: () => void
  onStartVocabularyPractice: (mode: VocabularyPracticeMode, nodeId: string, sourceLabel: string) => void
  onOpenPronunciationWorkspace: (workspace: PronunciationWorkspace) => void
}

interface KnowledgeOverviewError {
  detail?: string | {
    message?: string
    failed_source?: FailedKnowledgeSourceDetail | null
  }
}

interface DailyLessonRuntime {
  episode_id: string
  status: string
  answer_required: boolean
  checkpoint_id?: string | null
  checkpoint_status?: string | null
  resume_from?: string | null
  prompt?: string | null
  initial_payload?: Record<string, unknown>
  feedback?: unknown
  grading_result?: unknown
  mastery_update?: unknown
  memory_updates?: unknown
  review_schedule?: unknown
  verification_status?: string | null
  next_capability_recommendations?: CapabilityRecommendation[]
}

interface DailyLessonStatusResponse {
  episode_id: string
  episode_status: string
  checkpoint?: {
    checkpoint_id: string
    status: string
    resume_from?: string | null
    answer_required?: boolean
    prompt_payload?: Record<string, unknown> | null
    created_at?: string | null
    consumed_at?: string | null
  } | null
  trace_summary?: {
    event_count: number
    tool_call_count: number
    verification_status?: string | null
  }
}

interface DeleteSourceTarget {
  sourceId: string
  title: string
}

type KnowledgeWorkspace = 'today' | 'unit' | 'exercises'

interface ReadingWorkshopSeed {
  material: ReadingMaterial
  materialId: string
  sourceLabel: string
}

const KNOWLEDGE_WORKSPACES: ReadonlyArray<{ id: KnowledgeWorkspace; label: string }> = [
  { id: 'today', label: '今日任务' },
  { id: 'unit', label: '本单元材料' },
  { id: 'exercises', label: '教材练习' },
]

function readFailedSource(detail: KnowledgeOverviewError | null) {
  const payload = detail?.detail
  if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
    return payload.failed_source ?? null
  }
  return null
}

function ingestResultToStatus(result: KnowledgeIngestResult): KnowledgeIngestStatus {
  return {
    source_id: result.source_id,
    parser_run_id: result.parser_run_id,
    processing_status: result.processing_status ?? result.status,
    parse_quality_status: result.parse_quality_status,
    stage: result.processing_status ?? result.status,
    progress: 0,
    quality_status: result.quality_status,
    availability_status: result.availability_status ?? 'unavailable',
    blocking_reasons: result.blocking_reasons ?? [],
    warnings: [],
    parser_report_summary: result.parser_report_summary ?? {},
    quality_summary: result.quality_summary ?? {},
    selected_engine: result.selected_engine,
    attempted_engines: result.attempted_engines ?? [],
    fallback_used: result.fallback_used ?? false,
    error_message: null,
    can_open_knowledge_base: false,
    next_action: 'wait',
    message: result.message,
  }
}

export function KnowledgeBasePage({ learner, onBack, onStartVocabularyPractice, onOpenPronunciationWorkspace }: KnowledgeBasePageProps) {
  const { showToast } = useToast()
  const [overview, setOverview] = useState<KnowledgeBaseOverview | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [failedSource, setFailedSource] = useState<FailedKnowledgeSourceDetail | null>(null)
  const [ingestStatus, setIngestStatus] = useState<KnowledgeIngestStatus | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null)
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [deleteSourceTarget, setDeleteSourceTarget] = useState<DeleteSourceTarget | null>(null)
  const [isDeletingSource, setIsDeletingSource] = useState(false)
  const [lessonSession, setLessonSession] = useState<KnowledgeLessonSession | null>(null)
  const [lessonNodeId, setLessonNodeId] = useState<string | null>(null)
  const [isStartingLesson, setIsStartingLesson] = useState(false)
  const [unitVocabulary, setUnitVocabulary] = useState<UnitVocabularySummary | null>(null)
  const [grammarTopic, setGrammarTopic] = useState<string | null>(null)
  const [exerciseSession, setExerciseSession] = useState<ExerciseSession | null>(null)
  const [isStartingExercise, setIsStartingExercise] = useState(false)
  const [dailyLesson, setDailyLesson] = useState<DailyLessonRuntime | null>(null)
  const [dailyAnswer, setDailyAnswer] = useState('')
  const [isStartingDailyLesson, setIsStartingDailyLesson] = useState(false)
  const [readingMaterialType, setReadingMaterialType] = useState<ReadingMaterialType>('passage')
  const [readingMaterialLength, setReadingMaterialLength] = useState<ReadingMaterialLength>('short')
  const [isGeneratingReadingMaterial, setIsGeneratingReadingMaterial] = useState(false)
  const [readingWorkshopSeed, setReadingWorkshopSeed] = useState<ReadingWorkshopSeed | null>(null)
  const [unitReadingMaterials, setUnitReadingMaterials] = useState<ReadingMaterialGenerationResponse['material'][]>([])
  const [isLoadingUnitReadingMaterials, setIsLoadingUnitReadingMaterials] = useState(false)
  const [isCurriculumRailOpen, setIsCurriculumRailOpen] = useState(false)
  const [isContextPanelOpen, setIsContextPanelOpen] = useState(false)
  const [isCapabilityDrawerOpen, setIsCapabilityDrawerOpen] = useState(false)
  const [isSourceManagerOpen, setIsSourceManagerOpen] = useState(false)
  const [isSubmittingDailyAnswer, setIsSubmittingDailyAnswer] = useState(false)
  const [dismissedDailyRecommendationIds, setDismissedDailyRecommendationIds] = useState<Set<string>>(() => new Set())
  const [busyDailyRecommendationId, setBusyDailyRecommendationId] = useState<string | null>(null)
  const curriculumPanelId = useId()
  const curriculumTitleId = useId()
  const contextPanelId = useId()
  const contextTitleId = useId()
  const capabilityDrawerTitleId = useId()
  const { containerRef: curriculumPanelRef, handleKeyDown: handleCurriculumPanelKeyDown } = useFocusTrap<HTMLElement>({
    isActive: isCurriculumRailOpen,
    onEscape: () => setIsCurriculumRailOpen(false),
  })
  const { containerRef: contextPanelRef, handleKeyDown: handleContextPanelKeyDown } = useFocusTrap<HTMLElement>({
    isActive: isContextPanelOpen,
    onEscape: () => setIsContextPanelOpen(false),
  })
  const { containerRef: capabilityDrawerRef, handleKeyDown: handleCapabilityDrawerKeyDown } = useFocusTrap<HTMLElement>({
    isActive: isCapabilityDrawerOpen,
    onEscape: () => setIsCapabilityDrawerOpen(false),
  })

  const loadOverview = useCallback(async (sourceId?: string | null, nodeId?: string | null) => {
    setIsLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (sourceId) params.set('source_id', sourceId)
      if (nodeId) params.set('node_id', nodeId)
      const query = params.toString() ? `?${params.toString()}` : ''
      const response = await fetch(`/api/learners/${learner.id}/knowledge-base${query}`)
      if (!response.ok) {
        const detail = await response.json().catch(() => null) as KnowledgeOverviewError | null
        const nextFailedSource = readFailedSource(detail)
        setFailedSource(nextFailedSource)
        throw new Error(nextFailedSource ? '最近上传的教材还不能用于学习。' : '知识库暂时无法加载。')
      }
      const data = await response.json() as KnowledgeBaseOverview
      setOverview(data)
      setFailedSource(null)
      setSelectedNodeId(data.current_node_id)
      setSelectedSourceId(data.source.id)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : '知识库暂时无法加载。')
    } finally {
      setIsLoading(false)
    }
  }, [learner.id])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadOverview(), 0)
    return () => window.clearTimeout(timer)
  }, [loadOverview])

  useEffect(() => {
    const nodeId = overview?.current_unit.id
    if (!nodeId) return
    const controller = new AbortController()
    fetch(`/api/learners/${learner.id}/vocabulary/units/${nodeId}/summary`, { signal: controller.signal })
      .then((response) => response.ok ? response.json() as Promise<UnitVocabularySummary> : null)
      .then((data) => setUnitVocabulary(data))
      .catch((fetchError: unknown) => {
        if (!(fetchError instanceof DOMException && fetchError.name === 'AbortError')) setUnitVocabulary(null)
      })
    return () => controller.abort()
  }, [learner.id, overview?.current_unit.id])

  useEffect(() => {
    const nodeId = overview?.current_unit.id
    if (!nodeId) return
    const controller = new AbortController()
    fetch(
      `/api/learners/${learner.id}/reading-workshop/materials?curriculum_node_id=${encodeURIComponent(nodeId)}&limit=6`,
      { signal: controller.signal },
    )
      .then((response) => response.ok ? response.json() as Promise<ReadingMaterialGenerationResponse['material'][]> : [])
      .then((items) => setUnitReadingMaterials(items))
      .catch((fetchError: unknown) => {
        if (!(fetchError instanceof DOMException && fetchError.name === 'AbortError')) setUnitReadingMaterials([])
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingUnitReadingMaterials(false)
      })
    return () => controller.abort()
  }, [learner.id, overview?.current_unit.id])

  const dailyLessonStorageKey = useMemo(() => `binnagent:daily-lesson:${learner.id}`, [learner.id])

  useEffect(() => {
    const episodeId = window.localStorage.getItem(dailyLessonStorageKey)
    if (!episodeId) return
    const controller = new AbortController()
    fetch(`/api/learners/${learner.id}/daily-lessons/${episodeId}`, { signal: controller.signal })
      .then((response) => response.ok ? response.json() as Promise<DailyLessonStatusResponse> : null)
      .then((data) => {
        if (!data?.checkpoint || data.checkpoint.status !== 'waiting_user') {
          window.localStorage.removeItem(dailyLessonStorageKey)
          return
        }
        setDailyLesson({
          episode_id: data.episode_id,
          status: data.episode_status,
          answer_required: true,
          checkpoint_id: data.checkpoint.checkpoint_id,
          checkpoint_status: data.checkpoint.status,
          resume_from: data.checkpoint.resume_from,
          prompt: readPrompt(data.checkpoint.prompt_payload),
          initial_payload: data.checkpoint.prompt_payload ?? {},
        })
      })
      .catch((restoreError: unknown) => {
        if (!(restoreError instanceof DOMException && restoreError.name === 'AbortError')) {
          window.localStorage.removeItem(dailyLessonStorageKey)
        }
      })
    return () => controller.abort()
  }, [dailyLessonStorageKey, learner.id])

  const handleUpload = async (file: File) => {
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      throw new Error('仅支持 PDF 文件。')
    }
    if (file.size > 50 * 1024 * 1024) throw new Error('文件不能超过 50 MB。')

    const response = await fetch(
      `/api/knowledge/sources/uploads?learner_id=${encodeURIComponent(learner.id)}&filename=${encodeURIComponent(file.name)}`,
      { method: 'POST', headers: { 'Content-Type': 'application/pdf' }, body: file }
    )
    if (!response.ok) {
      const detail = await response.json().catch(() => null) as { detail?: string } | null
      throw new Error(detail?.detail ?? '上传失败，请稍后重试。')
    }
    const result = await response.json() as KnowledgeUploadResult
    const ingestResponse = await fetch(
      `/api/knowledge/sources/${result.source_id}/ingest?learner_id=${encodeURIComponent(learner.id)}`,
      { method: 'POST' }
    )
    if (!ingestResponse.ok) {
      const detail = await ingestResponse.json().catch(() => null) as { detail?: string } | null
      throw new Error(detail?.detail ?? '教材已上传，但解析暂时失败。')
    }
    const ingestResult = await ingestResponse.json() as KnowledgeIngestResult
    const initialStatus = ingestResultToStatus(ingestResult)
    setIngestStatus(initialStatus)
    setSelectedSourceId(result.source_id)
    if (ingestResult.quality_status === 'failed') {
      setFailedSource({
        source_id: ingestResult.source_id,
        status: ingestResult.status,
        quality_status: ingestResult.quality_status,
        blocking_reasons: ingestResult.blocking_reasons ?? [],
        parser_report_summary: ingestResult.parser_report_summary,
      })
      throw new Error(formatFailedIngestMessage(ingestResult))
    }
    showToast(ingestResult.message, { variant: 'info', duration: 6000 })
  }

  useEffect(() => {
    if (!ingestStatus || ingestStatus.next_action !== 'wait') return
    const sourceId = ingestStatus.source_id
    const poll = async () => {
      try {
        const response = await fetch(
          `/api/knowledge/sources/${sourceId}/ingest-status?learner_id=${encodeURIComponent(learner.id)}`,
        )
        if (!response.ok) throw new Error('解析进度暂时无法读取。')
        const nextStatus = await response.json() as KnowledgeIngestStatus
        setIngestStatus(nextStatus)
        if (nextStatus.can_open_knowledge_base) {
          showToast(nextStatus.message, { variant: 'success', duration: 5000 })
          await loadOverview(sourceId)
          const needsOcr = nextStatus.parse_quality_status === 'needs_ocr' || nextStatus.quality_summary?.needs_ocr === true
          if (!needsOcr) setIngestStatus(null)
        } else if (nextStatus.next_action === 'upload_text_pdf') {
          setFailedSource({
            source_id: nextStatus.source_id,
            status: nextStatus.processing_status,
            quality_status: nextStatus.quality_status,
            blocking_reasons: nextStatus.blocking_reasons,
            parser_report_summary: nextStatus.parser_report_summary,
          })
          setError('最近上传的教材还不能用于学习。')
        }
      } catch (pollError) {
        console.error('Ingest status polling failed:', pollError)
      }
    }
    void poll()
    const timer = window.setInterval(() => void poll(), 2000)
    return () => window.clearInterval(timer)
  }, [ingestStatus, learner.id, loadOverview, showToast])

  const handleStartLesson = async () => {
    const nodeId = overview?.current_unit.id
    if (!nodeId) return
    setIsStartingLesson(true)
    try {
      const response = await fetch(
        `/api/learners/${learner.id}/knowledge-base/lessons/${nodeId}/start`,
        { method: 'POST' }
      )
      if (!response.ok) throw new Error('今日课程暂时无法开始。')
      setLessonNodeId(nodeId)
      setLessonSession(await response.json() as KnowledgeLessonSession)
    } catch (startError) {
      showToast(startError instanceof Error ? startError.message : '今日课程暂时无法开始。', { variant: 'error' })
    } finally {
      setIsStartingLesson(false)
    }
  }

  const handleSelectNode = (nodeId: string) => {
    if (nodeId === selectedNodeId) return
    setSelectedNodeId(nodeId)
    setUnitReadingMaterials([])
    setIsLoadingUnitReadingMaterials(true)
    void loadOverview(selectedSourceId ?? overview?.source.id, nodeId)
  }

  const handleSelectSource = (sourceId: string) => {
    if (sourceId === selectedSourceId) return
    setSelectedSourceId(sourceId)
    setSelectedNodeId(null)
    setUnitVocabulary(null)
    setUnitReadingMaterials([])
    setIsLoadingUnitReadingMaterials(true)
    void loadOverview(sourceId)
  }

  const handleRequestDeleteCurrentSource = () => {
    if (!overview?.source.can_delete) return
    setDeleteSourceTarget({
      sourceId: overview.source.id,
      title: overview.source.title || overview.source.filename || '当前教材',
    })
  }

  const handleRequestDeleteFailedSource = () => {
    if (!failedSource?.source_id || failedSource.can_delete === false) return
    setDeleteSourceTarget({
      sourceId: failedSource.source_id,
      title: failedSource.title || failedSource.filename || '最近上传的教材',
    })
  }

  const handleConfirmDeleteSource = async () => {
    if (!deleteSourceTarget) return
    setIsDeletingSource(true)
    try {
      const result = await deleteKnowledgeSource(deleteSourceTarget.sourceId, learner.id)
      showToast(result.message, { variant: 'success' })
      setDeleteSourceTarget(null)
      if (ingestStatus?.source_id === result.source_id) setIngestStatus(null)
      if (failedSource?.source_id === result.source_id) setFailedSource(null)
      if (overview?.source.id === result.source_id) {
        setOverview(null)
        setSelectedSourceId(null)
        setSelectedNodeId(null)
        await loadOverview()
      } else {
        await loadOverview(selectedSourceId ?? overview?.source.id, selectedNodeId)
      }
    } catch (deleteError) {
      showToast(deleteError instanceof Error ? deleteError.message : '教材删除失败，请重试。', { variant: 'error' })
    } finally {
      setIsDeletingSource(false)
    }
  }

  const handleAttempt = async (knowledgePointId: string, correct: boolean) => {
    if (!lessonSession) throw new Error('课程会话已经结束。')
    const response = await fetch(`/api/learners/${learner.id}/knowledge-base/attempts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        knowledge_point_id: knowledgePointId,
        session_id: lessonSession.session_id,
        correct,
        hint_count: 0,
      }),
    })
    if (!response.ok) throw new Error('学习记录保存失败，请重试。')
    return await response.json() as KnowledgeAttemptResult
  }

  const handleCompleteLesson = async () => {
    if (!lessonSession) throw new Error('课程会话已经结束。')
    const response = await fetch(
      `/api/learners/${learner.id}/knowledge-base/lessons/${lessonSession.session_id}/complete`,
      { method: 'POST' },
    )
    if (!response.ok) throw new Error('课程完成状态保存失败，请重试。')
    await response.json() as KnowledgeLessonCompleteResult
    const completedNodeId = lessonNodeId ?? selectedNodeId ?? overview?.current_unit.id
    setLessonSession(null)
    setLessonNodeId(null)
    showToast('单元导学已记录，当前单元进度已更新。', { variant: 'success', duration: 5000 })
    await loadOverview(selectedSourceId ?? overview?.source.id, completedNodeId)
  }

  const handleStartDailyLesson = async () => {
    if (!overview?.current_unit.id) return
    setIsStartingDailyLesson(true)
    try {
      const response = await fetch(`/api/learners/${learner.id}/daily-lessons/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_curriculum_node_id: overview.current_unit.id,
          time_budget_minutes: overview.daily_lesson.estimated_minutes,
          mode_hint: 'textbook_guided',
        }),
      })
      if (!response.ok) throw new Error('AI 每日题暂时无法开始。')
      const started = await response.json() as DailyLessonRuntime
      if (started.answer_required && started.episode_id) {
        window.localStorage.setItem(dailyLessonStorageKey, started.episode_id)
        setDailyAnswer('')
        setDailyLesson(started)
      } else {
        showToast(started.initial_payload?.reason ? String(started.initial_payload.reason) : '当前没有可用的 AI 每日题。', { variant: 'warning' })
      }
    } catch (startError) {
      showToast(startError instanceof Error ? startError.message : 'AI 每日题暂时无法开始。', { variant: 'error' })
    } finally {
      setIsStartingDailyLesson(false)
    }
  }

  const openReadingMaterial = (material: ReadingMaterialGenerationResponse['material']) => {
    if (!overview) return
    setReadingWorkshopSeed({
      material: {
        title: material.title ?? '',
        text: material.text,
        level: material.level,
        goal: material.goal,
        material_type: material.material_type,
      },
      materialId: material.id,
      sourceLabel: `${overview.current_unit.title} · ${overview.current_unit.subtitle || '阅读语感'}`,
    })
  }

  const handleGenerateReadingMaterial = async () => {
    if (!overview?.current_unit.id) return
    setIsGeneratingReadingMaterial(true)
    try {
      const response = await fetch(`/api/learners/${learner.id}/reading-workshop/generated-materials`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          curriculum_node_id: overview.current_unit.id,
          material_type: readingMaterialType,
          length: readingMaterialLength,
          goal: 'mixed',
        }),
      })
      if (!response.ok) throw new Error('阅读材料暂时生成失败。')
      const result = await response.json() as ReadingMaterialGenerationResponse
      setUnitReadingMaterials((current) => [
        result.material,
        ...current.filter((item) => item.id !== result.material.id),
      ].slice(0, 6))
      openReadingMaterial(result.material)
      showToast('阅读材料已生成，已打开精读与泛读工作区。', { variant: 'success' })
    } catch (generateError) {
      showToast(generateError instanceof Error ? generateError.message : '阅读材料暂时生成失败。', { variant: 'error' })
    } finally {
      setIsGeneratingReadingMaterial(false)
    }
  }

  const handleSubmitDailyAnswer = async (answerOverride?: string) => {
    const submittedAnswer = (answerOverride ?? dailyAnswer).trim()
    if (!dailyLesson || !submittedAnswer) {
      showToast('请先填写答案。', { variant: 'warning' })
      return
    }
    setIsSubmittingDailyAnswer(true)
    try {
      const response = await fetch(
        `/api/learners/${learner.id}/daily-lessons/${dailyLesson.episode_id}/answer`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ answer: submittedAnswer, metadata: {} }),
        },
      )
      if (response.status === 409) {
        window.localStorage.removeItem(dailyLessonStorageKey)
        setDailyLesson(null)
        showToast('这道每日题已过期，已为你清理。请重新开始。', { variant: 'warning' })
        return
      }
      if (!response.ok) throw new Error('答案提交失败，请重试。')
      const result = await response.json() as DailyLessonRuntime
      window.localStorage.removeItem(dailyLessonStorageKey)
      setDailyLesson({ ...dailyLesson, ...result, status: result.status ?? 'completed', answer_required: false })
      showToast('AI 每日题已完成。', { variant: 'success' })
    } catch (submitError) {
      showToast(submitError instanceof Error ? submitError.message : '答案提交失败，请重试。', { variant: 'error' })
    } finally {
      setIsSubmittingDailyAnswer(false)
    }
  }

  const recordDailyCapabilityEvent = async (
    recommendation: CapabilityRecommendation,
    eventType: 'clicked' | 'dismissed',
  ) => {
    const response = await fetch(exploreCapabilityEventUrl(learner.id, recommendation.capability_id), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_type: eventType,
        episode_id: dailyLesson?.episode_id,
        recommendation_id: recommendation.recommendation_id,
        reason: recommendation.reason,
        evidence_refs: recommendation.evidence_refs ?? [],
        metadata: {
          source: 'daily_lesson_feedback',
          reason: recommendation.reason,
          priority_score: recommendation.priority_score,
        },
      }),
    })
    if (!response.ok) throw new Error('推荐事件记录失败。')
  }

  const handleOpenCapabilityRecommendation = async (recommendation: CapabilityRecommendation) => {
    setBusyDailyRecommendationId(recommendation.recommendation_id)
    try {
      if (recommendation.source !== 'fallback') {
        await recordDailyCapabilityEvent(recommendation, 'clicked')
      }
      setDailyLesson(null)
      setIsCapabilityDrawerOpen(false)
      if (recommendation.tool_target === 'grammar') {
        setGrammarTopic(readRecommendationTarget(recommendation) ?? 'grammar')
      } else if (recommendation.tool_target === 'pronunciation') {
        onOpenPronunciationWorkspace('phonetic')
      } else if (recommendation.tool_target === 'reading-workshop') {
        showToast('请在探索页打开精读与泛读入口。', { variant: 'info' })
      } else if (recommendation.tool_target === 'writing-phrasebook') {
        showToast('请在探索页打开好句收藏馆入口。', { variant: 'info' })
      } else if (recommendation.tool_target === 'word-parts') {
        showToast('请在探索页打开词根与词缀入口。', { variant: 'info' })
      } else if (recommendation.action === 'vocabulary-detail' || recommendation.tool_target === 'vocabulary-detail') {
        showToast('请在探索页打开词汇详解入口。', { variant: 'info' })
      } else {
        showToast('已记录你的选择，可从探索页继续打开该学习入口。', { variant: 'success' })
      }
    } catch (eventError) {
      showToast(eventError instanceof Error ? eventError.message : '推荐事件记录失败。', { variant: 'error' })
    } finally {
      setBusyDailyRecommendationId(null)
    }
  }

  const handleDismissDailyCapabilityRecommendation = async (recommendation: CapabilityRecommendation) => {
    setDismissedDailyRecommendationIds((current) => new Set(current).add(recommendation.recommendation_id))
    setBusyDailyRecommendationId(recommendation.recommendation_id)
    try {
      if (recommendation.source !== 'fallback') {
        await recordDailyCapabilityEvent(recommendation, 'dismissed')
      }
    } catch (eventError) {
      console.error('Daily capability dismiss event failed:', eventError)
    } finally {
      setBusyDailyRecommendationId(null)
    }
  }

  const handleStartExercise = async () => {
    setIsStartingExercise(true)
    try {
      const response = await fetch(
        `/api/learners/${learner.id}/knowledge-base/units/${overview?.current_unit.id}/exercises`,
        { method: 'POST' },
      )
      if (!response.ok) throw new Error('本单元练习暂时无法开始。')
      const session = await response.json() as ExerciseSession
      if (!session.questions.length) throw new Error('本单元还没有可用练习题。')
      setExerciseSession(session)
    } catch (exerciseError) {
      showToast(exerciseError instanceof Error ? exerciseError.message : '本单元练习暂时无法开始。', { variant: 'error' })
    } finally {
      setIsStartingExercise(false)
    }
  }

  if (isLoading && !overview) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-white text-sm text-slate-500">
        <LoaderCircle className="mr-2 size-4 animate-spin text-indigo-600" />
        正在打开每日学习…
      </div>
    )
  }

  if (!overview && ingestStatus) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-white p-6">
        <IngestStatusPanel status={ingestStatus} />
      </div>
    )
  }

  if (!overview || error) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-white p-6">
        <div className="w-full max-w-lg text-center">
          <div className="mx-auto flex size-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
            <UploadCloud className="size-6" />
          </div>
          <h1 className="mt-4 text-xl font-extrabold text-slate-950">上传教材，生成知识库</h1>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            {failedSource ? '最近上传的教材暂时不可用，可以重新上传一份可复制文字的 PDF。' : '当前还没有可用教材。上传 PDF 后会进入后台解析，并在这里显示解析进度。'}
          </p>
          {ingestStatus ? <div className="mt-5"><IngestStatusPanel status={ingestStatus} compact /></div> : null}
          {failedSource ? (
            <FailedSourceSummary
              source={failedSource}
              onDelete={failedSource.source_id && failedSource.can_delete !== false ? handleRequestDeleteFailedSource : undefined}
            />
          ) : null}
          {error && !failedSource ? (
            <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm font-semibold leading-6 text-amber-800">
              <AlertCircle className="mr-1 inline size-4 align-[-2px]" />
              {error}
            </div>
          ) : null}
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <Button
              onClick={() => setIsUploadOpen(true)}
            >
              <UploadCloud className="size-4" />
              上传教材
            </Button>
            <Button
              variant="secondary"
              onClick={() => void loadOverview(selectedSourceId)}
            >
              重新加载
            </Button>
          </div>
          <UploadTextbookDialog open={isUploadOpen} onClose={() => setIsUploadOpen(false)} onUpload={handleUpload} />
          <ConfirmDialog
            open={Boolean(deleteSourceTarget)}
            title="删除这本教材？"
            description={deleteSourceTarget ? `删除后会移除「${deleteSourceTarget.title}」及其解析出的目录、知识点、练习和索引。之后可以重新上传 PDF 生成新的知识库。` : ''}
            confirmLabel="删除教材"
            isBusy={isDeletingSource}
            danger
            onCancel={() => setDeleteSourceTarget(null)}
            onConfirm={() => void handleConfirmDeleteSource()}
          />
        </div>
      </div>
    )
  }

  const activeUnitVocabulary = unitVocabulary?.unit_id === overview.current_unit.id ? unitVocabulary : null
  const currentSourceLabel = `${overview.source.title} · ${overview.current_unit.title}`
  const activeWorkspace = KNOWLEDGE_WORKSPACES[0]
  const unitWorkspace = overview.unit_workspace ?? fallbackUnitWorkspace(overview)
  const unitProgressPercent = normalizePercent(unitWorkspace.mastery_summary.average)
  const capabilityRecommendations = buildCapabilityRecommendations(
    overview,
    dailyLesson?.next_capability_recommendations ?? [],
    dismissedDailyRecommendationIds,
  )
  const curriculumRailClassName = isCurriculumRailOpen
    ? 'fixed bottom-0 left-0 top-16 z-40 w-[min(88vw,22rem)] min-h-0 overflow-y-auto shadow-2xl transition-[transform,opacity] duration-200 motion-reduce:transition-none'
    : 'hidden'
  const contextPanelClassName = isContextPanelOpen
    ? 'fixed bottom-0 right-0 top-16 z-40 w-[min(90vw,24rem)] overflow-y-auto shadow-2xl transition-[transform,opacity] duration-200 motion-reduce:transition-none'
    : 'hidden'

  if (readingWorkshopSeed) {
    return (
      <ReadingWorkshopPage
        learner={learner}
        initialMaterial={readingWorkshopSeed.material}
        initialMaterialId={readingWorkshopSeed.materialId}
        initialSourceLabel={readingWorkshopSeed.sourceLabel}
        onBack={() => setReadingWorkshopSeed(null)}
      />
    )
  }

  if (grammarTopic) {
    return (
      <GrammarPage
        learner={learner}
        initialTopic={grammarTopic}
        onBack={() => setGrammarTopic(null)}
        backLabel="返回单元知识"
      />
    )
  }

  return (
    <PageShell variant="full" className="bg-white">
      <div className="-mx-4 -my-6 min-h-[calc(100vh-4rem)] bg-white sm:-mx-6 lg:-mx-8">
        <div className="flex h-12 items-center border-b border-slate-200 px-4 text-sm text-slate-500 sm:px-6">
          <button
            type="button"
            onClick={onBack}
            className="inline-flex items-center gap-1 font-semibold transition-colors hover:text-indigo-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
          >
            <ChevronLeft className="size-4" />
            学习中心
          </button>
          <span className="mx-2 text-slate-300">/</span>
          <span>{activeWorkspace.label}</span>
          <span className="mx-2 text-slate-300">/</span>
          <span className="hidden sm:inline">{overview.current_unit.title} · {overview.current_unit.subtitle}</span>
        </div>
        <div className="knowledge-shell min-h-[calc(100vh-7rem)] bg-slate-50/70">
      {isCurriculumRailOpen ? (
        <button
          type="button"
          aria-label="收起教材目录"
          onClick={() => setIsCurriculumRailOpen(false)}
          className="fixed inset-x-0 bottom-0 top-16 z-30 bg-slate-950/25 transition-opacity duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 motion-reduce:transition-none"
        />
      ) : null}
      <CurriculumRail
        panelId={curriculumPanelId}
        titleId={curriculumTitleId}
        panelRef={curriculumPanelRef}
        role="dialog"
        ariaModal
        ariaLabelledby={curriculumTitleId}
        tabIndex={-1}
        onKeyDown={handleCurriculumPanelKeyDown}
        nodes={overview.curriculum}
        currentNodeId={selectedNodeId ?? overview.current_node_id}
        sourceTitle={overview.source.title}
        sources={overview.sources}
        currentSourceId={overview.source.id}
        progress={overview.source.progress}
        className={curriculumRailClassName}
        canDelete={overview.source.can_delete}
        onSourceChange={(sourceId) => {
          handleSelectSource(sourceId)
          setIsCurriculumRailOpen(false)
        }}
        onSelect={(nodeId) => {
          handleSelectNode(nodeId)
          setIsCurriculumRailOpen(false)
        }}
        onManage={() => {
          setIsCurriculumRailOpen(false)
          setIsUploadOpen(true)
        }}
        onDelete={() => {
          setIsCurriculumRailOpen(false)
          handleRequestDeleteCurrentSource()
        }}
      />

      <main className="min-w-0 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="mx-auto max-w-6xl space-y-6">
          {ingestStatus ? <IngestStatusPanel status={ingestStatus} compact /> : null}
          {overview.review.requires_review || overview.review.warning_count > 0 ? (
            <StatusBanner tone="warning" title="教材内容需要留意">
              已发现 {overview.review.pending_count} 个待确认项、{overview.review.warning_count} 条提醒；当前不影响继续学习。
            </StatusBanner>
          ) : null}

          <CourseHero
            overview={overview}
            workspace={unitWorkspace}
            vocabulary={activeUnitVocabulary}
            progressPercent={unitProgressPercent}
            capabilityCount={capabilityRecommendations.length}
            isStartingLesson={isStartingLesson}
            onBack={onBack}
            onStartLesson={() => void handleStartLesson()}
            onViewMaterials={() => document.getElementById('unit-materials')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
            onOpenCapabilities={() => setIsCapabilityDrawerOpen(true)}
            onOpenCurriculum={() => {
              setIsContextPanelOpen(false)
              setIsCurriculumRailOpen(true)
            }}
            onOpenContext={() => {
              setIsCurriculumRailOpen(false)
              setIsContextPanelOpen(true)
            }}
          />

          <TodayCourseTasks
            overview={overview}
            vocabulary={activeUnitVocabulary}
            isStartingLesson={isStartingLesson}
            isStartingExercise={isStartingExercise}
            isStartingDailyLesson={isStartingDailyLesson}
            isGeneratingReadingMaterial={isGeneratingReadingMaterial}
            isLoadingReadingMaterials={isLoadingUnitReadingMaterials}
            readingMaterialType={readingMaterialType}
            readingMaterialLength={readingMaterialLength}
            readingMaterials={unitReadingMaterials}
            onStartLesson={() => void handleStartLesson()}
            onStartVocabulary={(mode) => onStartVocabularyPractice(mode, overview.current_unit.id, currentSourceLabel)}
            onStartExercise={() => void handleStartExercise()}
            onStartDailyLesson={() => void handleStartDailyLesson()}
            onGenerateReadingMaterial={() => void handleGenerateReadingMaterial()}
            onReadingMaterialTypeChange={setReadingMaterialType}
            onReadingMaterialLengthChange={setReadingMaterialLength}
          />

          <UnitMaterialsSection
            overview={overview}
            workspace={unitWorkspace}
            vocabulary={activeUnitVocabulary}
            isGeneratingReadingMaterial={isGeneratingReadingMaterial}
            readingMaterials={unitReadingMaterials}
            onStartVocabulary={(mode) => onStartVocabularyPractice(mode, overview.current_unit.id, currentSourceLabel)}
            onStartDailyLesson={() => void handleStartDailyLesson()}
            onStartExercise={() => void handleStartExercise()}
            onGenerateReadingMaterial={() => void handleGenerateReadingMaterial()}
            onOpenReadingMaterial={openReadingMaterial}
            onStartGrammar={setGrammarTopic}
          />

          <details
            open={isSourceManagerOpen}
            onToggle={(event) => setIsSourceManagerOpen(event.currentTarget.open)}
            className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_4px_14px_rgba(15,23,42,0.05)]"
          >
            <summary className="flex cursor-pointer items-center gap-2 text-sm font-black text-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500">
              {isSourceManagerOpen ? <ChevronDown className="size-4 text-slate-500" /> : <ChevronRight className="size-4 text-slate-500" />}
              教材管理
            </summary>
            <LearningSourceTiles
              sources={overview.sources}
              currentSourceId={overview.source.id}
              onSourceChange={handleSelectSource}
              onManage={() => setIsUploadOpen(true)}
            />
          </details>

        </div>
      </main>

      {!isCapabilityDrawerOpen ? (
        <button
          type="button"
          onClick={() => setIsCapabilityDrawerOpen(true)}
          className="fixed right-0 top-1/2 z-20 hidden -translate-y-1/2 rounded-l-lg border border-r-0 border-indigo-200 bg-white px-3 py-4 text-sm font-black text-indigo-700 shadow-lg transition hover:bg-indigo-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 lg:inline-flex [writing-mode:vertical-rl]"
        >
          能力加练
        </button>
      ) : null}

      {isContextPanelOpen ? (
        <button
          type="button"
          aria-label="收起学习概览"
          onClick={() => setIsContextPanelOpen(false)}
          className="fixed inset-x-0 bottom-0 top-16 z-30 bg-slate-950/25 transition-opacity duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 motion-reduce:transition-none"
        />
      ) : null}
      <KnowledgeContextPanel
        overview={overview}
        panelId={contextPanelId}
        titleId={contextTitleId}
        panelRef={contextPanelRef}
        role="dialog"
        ariaModal
        ariaLabelledby={contextTitleId}
        tabIndex={-1}
        onKeyDown={handleContextPanelKeyDown}
        className={contextPanelClassName}
        onUpload={() => {
          setIsContextPanelOpen(false)
          setIsUploadOpen(true)
        }}
      />
      <CapabilityBoosterDrawer
        open={isCapabilityDrawerOpen}
        titleId={capabilityDrawerTitleId}
        drawerRef={capabilityDrawerRef}
        onKeyDown={handleCapabilityDrawerKeyDown}
        recommendations={capabilityRecommendations}
        busyRecommendationId={busyDailyRecommendationId}
        onOpenRecommendation={(item) => void handleOpenCapabilityRecommendation(item)}
        onDismissRecommendation={(item) => void handleDismissDailyCapabilityRecommendation(item)}
        onClose={() => setIsCapabilityDrawerOpen(false)}
        onExploreMore={() => {
          setIsCapabilityDrawerOpen(false)
          showToast('更多能力入口可以从顶部「探索」页打开。', { variant: 'info' })
        }}
      />
      <UploadTextbookDialog open={isUploadOpen} onClose={() => setIsUploadOpen(false)} onUpload={handleUpload} />
      <ConfirmDialog
        open={Boolean(deleteSourceTarget)}
        title="删除这本教材？"
        description={deleteSourceTarget ? `删除后会移除「${deleteSourceTarget.title}」及其解析出的目录、知识点、练习和索引。之后可以重新上传 PDF 生成新的知识库。` : ''}
        confirmLabel="删除教材"
        isBusy={isDeletingSource}
        danger
        onCancel={() => setDeleteSourceTarget(null)}
        onConfirm={() => void handleConfirmDeleteSource()}
      />
      <LessonSessionDialog
        key={lessonSession?.session_id ?? 'closed-lesson'}
        session={lessonSession}
        onClose={() => {
          const currentLessonNodeId = lessonNodeId ?? selectedNodeId ?? overview.current_unit.id
          setLessonSession(null)
          setLessonNodeId(null)
          void loadOverview(selectedSourceId ?? overview.source.id, currentLessonNodeId)
        }}
        onAttempt={handleAttempt}
        onComplete={handleCompleteLesson}
      />
      <DailyLessonRuntimeDialog
        key={dailyLesson?.episode_id ?? 'closed-daily-lesson'}
        lesson={dailyLesson}
        answer={dailyAnswer}
        isSubmitting={isSubmittingDailyAnswer}
        dismissedRecommendationIds={dismissedDailyRecommendationIds}
        busyRecommendationId={busyDailyRecommendationId}
        onAnswerChange={setDailyAnswer}
        onSubmit={(value) => void handleSubmitDailyAnswer(value)}
        boosterCount={capabilityRecommendations.length}
        onOpenBoosterDrawer={() => setIsCapabilityDrawerOpen(true)}
        onDismissRecommendation={(item) => void handleDismissDailyCapabilityRecommendation(item)}
        onClose={() => setDailyLesson(null)}
      />
      <ExerciseSessionDialog
        key={exerciseSession?.curriculum_node_id ?? 'closed-exercise'}
        session={exerciseSession}
        learnerId={learner.id}
        onClose={() => setExerciseSession(null)}
      />
        </div>
      </div>
    </PageShell>
  )
}

function CourseHero({
  overview,
  workspace,
  vocabulary,
  progressPercent,
  capabilityCount,
  isStartingLesson,
  onBack,
  onStartLesson,
  onViewMaterials,
  onOpenCapabilities,
  onOpenCurriculum,
  onOpenContext,
}: {
  overview: KnowledgeBaseOverview
  workspace: UnitLearningWorkspace
  vocabulary: UnitVocabularySummary | null
  progressPercent: number
  capabilityCount: number
  isStartingLesson: boolean
  onBack: () => void
  onStartLesson: () => void
  onViewMaterials: () => void
  onOpenCapabilities: () => void
  onOpenCurriculum: () => void
  onOpenContext: () => void
}) {
  const objectives = workspace.overview.objectives.length
    ? workspace.overview.objectives.slice(0, 3)
    : [`完成 ${overview.current_unit.title} 的导学与练习`, '掌握本单元核心词汇和语法', '用教材题检查薄弱点']

  return (
    <section className="overflow-hidden rounded-2xl border border-indigo-100 bg-gradient-to-br from-white via-white to-sky-50 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
      <div className="grid gap-6 p-5 sm:p-6 lg:grid-cols-[220px_minmax(0,1fr)] lg:p-8">
        <TextbookCover overview={overview} />
        <div className="min-w-0">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-black uppercase tracking-wide text-indigo-600">{overview.source.publisher || '教材来源'} · {overview.source.title}</p>
              <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">
                {workspace.unit.title}
              </h1>
              {workspace.unit.subtitle ? <p className="mt-2 text-lg font-bold text-slate-600">{workspace.unit.subtitle}</p> : null}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onOpenCurriculum}
                aria-label="打开教材目录"
                className="inline-flex size-10 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
                title="教材目录"
              >
                <ListTree className="size-4" />
              </button>
              <button
                type="button"
                onClick={onOpenContext}
                aria-label="打开学习概览"
                className="inline-flex size-10 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
                title="学习概览"
              >
                <Layers3 className="size-4" />
              </button>
            </div>
          </div>

          <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-600">
            {workspace.overview.summary || `${overview.current_unit.title} ${overview.current_unit.subtitle}`.trim()}
          </p>

          <div className="mt-5 grid gap-2 sm:grid-cols-3">
            {objectives.map((objective) => (
              <div key={objective} className="rounded-lg border border-slate-200 bg-white/80 px-3 py-2 text-sm font-bold leading-6 text-slate-700">
                <CheckCircle2 className="mr-2 inline size-4 align-[-3px] text-emerald-600" />
                {objective}
              </div>
            ))}
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_180px] lg:items-end">
            <div>
              <div className="flex items-center justify-between gap-3 text-sm font-bold text-slate-600">
                <span>当前单元进度</span>
                <span>{progressPercent}%</span>
              </div>
              <UnitProgressBar value={progressPercent} />
              <p className="mt-2 text-xs font-semibold text-slate-500">
                {vocabulary ? unitVocabularySummaryText(vocabulary) : `${overview.knowledge_points.length} 个知识点已整理`}
              </p>
            </div>
            <div className="rounded-xl border border-white/80 bg-white/85 px-4 py-3 text-sm font-bold text-slate-600 shadow-sm">
              <p className="text-xs text-slate-500">预计完成</p>
              <p className="mt-1 text-2xl font-black text-slate-950">{workspace.unit.estimated_minutes || overview.current_unit.estimated_minutes}<span className="ml-1 text-sm text-slate-500">分钟</span></p>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <Button onClick={onStartLesson} disabled={isStartingLesson} className="min-w-36">
              {isStartingLesson ? <LoaderCircle className="size-4 animate-spin" /> : <BookOpen className="size-4" />}
              继续学习
            </Button>
            <Button variant="secondary" onClick={onViewMaterials}>
              <BookMarked className="size-4" />
              查看单元材料
            </Button>
            <Button variant="secondary" onClick={onOpenCapabilities} className="border-indigo-200 text-indigo-700 hover:bg-indigo-50">
              <Sparkles className="size-4" />
              能力加练 {capabilityCount}
            </Button>
            <Button variant="ghost" onClick={onBack}>
              返回学习中心
            </Button>
          </div>
        </div>
      </div>
    </section>
  )
}

function TodayCourseTasks({
  overview,
  vocabulary,
  isStartingLesson,
  isStartingExercise,
  isStartingDailyLesson,
  isGeneratingReadingMaterial,
  isLoadingReadingMaterials,
  readingMaterialType,
  readingMaterialLength,
  readingMaterials,
  onStartLesson,
  onStartVocabulary,
  onStartExercise,
  onStartDailyLesson,
  onGenerateReadingMaterial,
  onReadingMaterialTypeChange,
  onReadingMaterialLengthChange,
}: {
  overview: KnowledgeBaseOverview
  vocabulary: UnitVocabularySummary | null
  isStartingLesson: boolean
  isStartingExercise: boolean
  isStartingDailyLesson: boolean
  isGeneratingReadingMaterial: boolean
  isLoadingReadingMaterials: boolean
  readingMaterialType: ReadingMaterialType
  readingMaterialLength: ReadingMaterialLength
  readingMaterials: ReadingMaterialGenerationResponse['material'][]
  onStartLesson: () => void
  onStartVocabulary: (mode: VocabularyPracticeMode) => void
  onStartExercise: () => void
  onStartDailyLesson: () => void
  onGenerateReadingMaterial: () => void
  onReadingMaterialTypeChange: (value: ReadingMaterialType) => void
  onReadingMaterialLengthChange: (value: ReadingMaterialLength) => void
}) {
  const vocabularyEntry = vocabularyPracticeEntry(vocabulary)
  const canPracticeSpelling = Boolean(vocabulary && vocabulary.total > vocabulary.mastered)
  const latestReadingMaterial = readingMaterials[0]
  const tasks: CourseTaskCardProps[] = [
    {
      icon: <BookOpen className="size-5" />,
      title: '单元导学',
      description: '先过一遍本单元目标、重点和例句。',
      meta: `预计 ${overview.current_unit.estimated_minutes || 12} 分钟`,
      status: 'continue',
      actionLabel: '继续',
      isLoading: isStartingLesson,
      onAction: onStartLesson,
    },
    {
      icon: <Languages className="size-5" />,
      title: vocabularyEntry.kind === 'review' ? '词汇复习' : vocabularyEntry.kind === 'continue' ? '继续词汇' : '新词预习',
      description: vocabularyEntry.kind === 'review'
        ? '把到期词汇先拉回稳定记忆。'
        : vocabularyEntry.kind === 'new'
          ? '认识本单元的新词和核心表达。'
          : vocabularyEntry.kind === 'continue'
            ? '本单元词汇还在学习中，可以继续巩固。'
          : '本单元暂时没有可练习的词汇。',
      meta: vocabularyEntry.meta,
      status: vocabularyEntry.mode ? (vocabularyEntry.kind === 'review' || vocabularyEntry.kind === 'continue' ? 'continue' : 'not-started') : 'unavailable',
      actionLabel: vocabularyEntry.kind === 'review' ? '去复习' : vocabularyEntry.kind === 'continue' ? '继续' : vocabularyEntry.kind === 'new' ? '去预习' : '暂无可练',
      disabled: !vocabularyEntry.mode,
      onAction: () => {
        if (vocabularyEntry.mode) onStartVocabulary(vocabularyEntry.mode)
      },
    },
    {
      icon: <BookOpenCheck className="size-5" />,
      title: '阅读语感',
      description: latestReadingMaterial
        ? '按本单元知识点重新生成一篇连续输入材料；历史材料在下方阅读材料卡片查看。'
        : '融合本单元词汇、语法和主题，生成一篇连续输入材料。',
      meta: isLoadingReadingMaterials
        ? `${READING_MATERIAL_TYPE_LABELS[readingMaterialType]} · ${READING_MATERIAL_LENGTH_LABELS[readingMaterialLength]}`
        : latestReadingMaterial
          ? `已有 ${readingMaterials.length} 篇历史`
          : `${READING_MATERIAL_TYPE_LABELS[readingMaterialType]} · ${READING_MATERIAL_LENGTH_LABELS[readingMaterialLength]}`,
      status: 'not-started',
      actionLabel: '生成阅读',
      isLoading: isGeneratingReadingMaterial,
      onAction: onGenerateReadingMaterial,
    },
    {
      icon: <Dumbbell className="size-5" />,
      title: '教材练习',
      description: '用本单元知识点生成混合题，检查掌握情况。',
      meta: `预计 ${overview.daily_lesson.estimated_minutes} 分钟`,
      status: 'not-started',
      actionLabel: '开始练习',
      isLoading: isStartingExercise,
      onAction: onStartExercise,
    },
    {
      icon: <BookCheck className="size-5" />,
      title: '拼写巩固',
      description: '针对本单元单词做一次拼写检查。',
      meta: `${vocabulary?.total ?? overview.knowledge_points.filter((item) => item.type === 'vocabulary').length} 个词`,
      status: canPracticeSpelling ? 'not-started' : 'unavailable',
      actionLabel: canPracticeSpelling ? '练拼写' : '暂无可练',
      disabled: !canPracticeSpelling,
      onAction: () => {
        if (canPracticeSpelling) onStartVocabulary('spelling')
      },
    },
  ]

  return (
    <section aria-labelledby="today-course-tasks-title">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="today-course-tasks-title" className="text-xl font-black text-slate-950">今日课程任务</h2>
          <p className="mt-1 text-sm text-slate-500">主线任务只围绕当前单元推进，完成后再看能力加练。</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select
            name="reading_material_type"
            autoComplete="off"
            value={readingMaterialType}
            onChange={(event) => onReadingMaterialTypeChange(event.target.value as ReadingMaterialType)}
            wrapperClassName="w-28"
            className="h-10 py-0 text-xs font-bold text-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
          >
            {(Object.entries(READING_MATERIAL_TYPE_LABELS) as Array<[ReadingMaterialType, string]>).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </Select>
          <Select
            name="reading_material_length"
            autoComplete="off"
            value={readingMaterialLength}
            onChange={(event) => onReadingMaterialLengthChange(event.target.value as ReadingMaterialLength)}
            wrapperClassName="w-28"
            className="h-10 py-0 text-xs font-bold text-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
          >
            {(Object.entries(READING_MATERIAL_LENGTH_LABELS) as Array<[ReadingMaterialLength, string]>).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </Select>
          <Button variant="secondary" onClick={onStartDailyLesson} disabled={isStartingDailyLesson}>
            {isStartingDailyLesson ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
            AI 每日题
          </Button>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {tasks.map((task) => <CourseTaskCard key={task.title} {...task} />)}
      </div>
    </section>
  )
}

interface CourseTaskCardProps {
  icon: ReactNode
  title: string
  description: string
  meta: string
  status: 'completed' | 'continue' | 'not-started' | 'unavailable'
  actionLabel: string
  isLoading?: boolean
  disabled?: boolean
  onAction: () => void
}

function CourseTaskCard({
  icon,
  title,
  description,
  meta,
  status,
  actionLabel,
  isLoading = false,
  disabled = false,
  onAction,
}: CourseTaskCardProps) {
  const statusLabel = status === 'completed' ? '已完成' : status === 'continue' ? '继续' : status === 'unavailable' ? '暂无' : '未开始'
  const statusClassName = status === 'completed'
    ? 'bg-emerald-50 text-emerald-700'
    : status === 'continue'
      ? 'bg-indigo-50 text-indigo-700'
      : 'bg-slate-100 text-slate-600'

  return (
    <article className="group flex min-h-[210px] flex-col overflow-hidden rounded-lg border border-slate-200/90 bg-white shadow-[0_8px_24px_rgba(15,23,42,0.05)] transition-colors hover:border-indigo-200 focus-within:border-indigo-300">
      <div className="h-1 bg-gradient-to-r from-indigo-500 via-sky-400 to-emerald-400 opacity-80" />
      <div className="flex flex-1 flex-col p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex size-10 items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-slate-700 transition group-hover:border-indigo-200 group-hover:bg-indigo-50 group-hover:text-indigo-700">
          {icon}
        </div>
        <span className={`rounded-md px-2 py-1 text-[11px] font-black ${statusClassName}`}>{statusLabel}</span>
      </div>
      <h3 className="mt-4 text-base font-black text-slate-950">{title}</h3>
      <p className="mt-2 line-clamp-2 flex-1 text-sm leading-6 text-slate-600">{description}</p>
      <div className="mt-4 grid gap-3">
        <span className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500">
          <Clock3 className="size-3.5" />
          {meta}
        </span>
        <Button
          variant={status === 'continue' ? 'primary' : 'secondary'}
          onClick={onAction}
          disabled={disabled || isLoading}
          className="w-full justify-center whitespace-nowrap px-3 py-2"
        >
          {isLoading ? <LoaderCircle className="size-4 animate-spin" /> : <ArrowRight className="size-4" />}
          {isLoading ? '准备中' : actionLabel}
        </Button>
      </div>
      </div>
    </article>
  )
}

function LearningSourceTiles({
  sources,
  currentSourceId,
  onSourceChange,
  onManage,
}: {
  sources: KnowledgeBaseOverview['sources']
  currentSourceId: string
  onSourceChange: (sourceId: string) => void
  onManage: () => void
}) {
  return (
    <section className="mt-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-black text-slate-950">学习来源</h2>
          <p className="mt-1 text-sm text-slate-500">切换教材或添加资料，今日单元和练习会跟着更新。</p>
        </div>
        <Button variant="secondary" onClick={onManage}>
          <UploadCloud className="size-4" />
          添加教材
        </Button>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {sources.slice(0, 4).map((source) => {
          const isCurrent = source.id === currentSourceId
          return (
            <button
              key={source.id}
              type="button"
              onClick={() => onSourceChange(source.id)}
              className={`rounded-xl border px-4 py-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 ${
                isCurrent
                  ? 'border-indigo-400 bg-indigo-50 text-indigo-950'
                  : 'border-slate-200 bg-white text-slate-700 hover:border-indigo-200'
              }`}
            >
              <p className="truncate text-sm font-black">{source.title}</p>
              <p className="mt-1 text-xs font-semibold text-slate-500">{source.publisher || source.filename || '英语教材'}</p>
            </button>
          )
        })}
      </div>
    </section>
  )
}

function UnitMaterialsSection({
  overview,
  workspace,
  vocabulary,
  isGeneratingReadingMaterial,
  readingMaterials,
  onStartExercise,
  onStartDailyLesson,
  onStartVocabulary,
  onGenerateReadingMaterial,
  onOpenReadingMaterial,
  onStartGrammar,
}: {
  overview: KnowledgeBaseOverview
  workspace: UnitLearningWorkspace
  vocabulary: UnitVocabularySummary | null
  isGeneratingReadingMaterial: boolean
  readingMaterials: ReadingMaterialGenerationResponse['material'][]
  onStartExercise: () => void
  onStartDailyLesson: () => void
  onStartVocabulary: (mode: VocabularyPracticeMode) => void
  onGenerateReadingMaterial: () => void
  onOpenReadingMaterial: (material: ReadingMaterialGenerationResponse['material']) => void
  onStartGrammar: (topic: string) => void
}) {
  const [detail, setDetail] = useState<MaterialDetail | null>(null)
  const [isReadingHistoryOpen, setIsReadingHistoryOpen] = useState(false)
  const sectionById = new Map(workspace.sections.map((section) => [section.id, section]))
  const firstGrammarTopic = sectionById.get('grammar')?.items[0]?.title ?? overview.knowledge_points.find((item) => item.type === 'grammar')?.title ?? 'grammar'
  const expressionItems = [
    ...(sectionById.get('sentence_patterns')?.items ?? []),
    ...(sectionById.get('phrases')?.items ?? []),
  ]
  const vocabularyEntry = vocabularyPracticeEntry(vocabulary)
  const latestReadingMaterial = readingMaterials[0]
  const materialCards = [
    {
      id: 'vocabulary',
      icon: <Languages className="size-5" />,
      title: '单词表',
      description: vocabularyEntry.mode
        ? vocabularyEntry.kind === 'continue'
          ? '继续巩固本单元学习中的词汇。'
          : '进入本单元词汇预习或到期复习。'
        : '本单元暂时没有可练习的词汇。',
      meta: vocabularyEntry.meta || `${sectionById.get('vocabulary')?.count ?? 0} 个词`,
      actionLabel: vocabularyEntry.kind === 'review' ? '复习词汇' : vocabularyEntry.kind === 'continue' ? '继续词汇' : vocabularyEntry.kind === 'new' ? '打开词汇' : '暂无可练',
      actionType: (vocabularyEntry.mode === 'review' ? 'review' : 'vocabulary_new') as UnitWorkspaceActionType,
      disabled: !vocabularyEntry.mode,
      detailItems: sectionById.get('vocabulary')?.items ?? [],
      emptyDetail: '本单元暂时没有词汇条目。',
    },
    {
      id: 'grammar',
      icon: <GraduationCap className="size-5" />,
      title: '语法要点',
      description: '查看本单元语法微知识点和例句。',
      meta: `${sectionById.get('grammar')?.count ?? 0} 项`,
      actionType: 'details',
      detailItems: sectionById.get('grammar')?.items ?? [],
      emptyDetail: '本单元暂时没有语法要点。',
      itemActionLabel: '进入语法',
    },
    {
      id: 'sentence_patterns',
      icon: <FileText className="size-5" />,
      title: '句型短语',
      description: '保留教材中的重点句型、短语和表达。',
      meta: `${(sectionById.get('sentence_patterns')?.count ?? 0) + (sectionById.get('phrases')?.count ?? 0)} 项`,
      actionType: 'details',
      detailItems: expressionItems,
      emptyDetail: '本单元暂时没有句型短语。',
      itemActionLabel: '练这个表达',
    },
    {
      id: 'reading',
      icon: <BookOpenCheck className="size-5" />,
      title: '阅读材料',
      description: latestReadingMaterial
        ? latestReadingMaterial.title ?? '继续阅读本单元材料。'
        : '还没有材料时，可以生成本单元短文或对话。',
      meta: latestReadingMaterial ? `${readingMaterials.length} 篇历史` : `${sectionById.get('vocabulary')?.count ?? 0} 个词可融入`,
      actionLabel: latestReadingMaterial ? '打开最近' : isGeneratingReadingMaterial ? '生成中' : '新生成',
      actionType: 'reading' as UnitWorkspaceActionType,
      isLoading: isGeneratingReadingMaterial,
      readingItems: readingMaterials,
    },
    {
      id: 'practice',
      icon: <Dumbbell className="size-5" />,
      title: '教材题库',
      description: '用当前单元材料生成练习题。',
      meta: `${overview.knowledge_points.length} 个知识点`,
      actionLabel: '开始练习',
      actionType: 'exercise' as UnitWorkspaceActionType,
    },
  ]

  const handleAction = (type: UnitWorkspaceActionType, targetTopic?: string) => {
    if (type === 'vocabulary_new') onStartVocabulary('new')
    else if (type === 'review') onStartVocabulary('review')
    else if (type === 'vocabulary_spelling') onStartVocabulary('spelling')
    else if (type === 'daily_lesson') onStartDailyLesson()
    else if (type === 'exercise') onStartExercise()
    else if (type === 'grammar') onStartGrammar(targetTopic ?? firstGrammarTopic)
    else if (type === 'reading') {
      if (latestReadingMaterial) onOpenReadingMaterial(latestReadingMaterial)
      else onGenerateReadingMaterial()
    }
  }

  const openDetails = (card: (typeof materialCards)[number]) => {
    if (!('detailItems' in card)) return
    setDetail({
      title: card.title,
      subtitle: `${overview.current_unit.title} · ${overview.current_unit.subtitle}`,
      items: card.detailItems ?? [],
      emptyMessage: card.emptyDetail ?? '暂无详情。',
      itemActionLabel: card.itemActionLabel,
      onItemAction: card.itemActionLabel
        ? (item) => {
          setDetail(null)
          onStartGrammar(item.title)
        }
        : undefined,
    })
  }

  return (
    <section id="unit-materials" className="scroll-mt-24" aria-labelledby="unit-materials-title">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="unit-materials-title" className="text-xl font-black text-slate-950">本单元材料</h2>
          <p className="mt-1 text-sm text-slate-500">这里只保留入口，不在课程主页展开全部知识点。</p>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg bg-white px-3 py-2 text-xs font-bold text-slate-500 shadow-sm" aria-label="本单元词汇统计">
          <span className="text-slate-800">共 {vocabulary?.total ?? sectionById.get('vocabulary')?.count ?? '—'} 词</span>
          <span>新词 {vocabulary?.new ?? '—'}</span>
          <span>学习中 {vocabulary?.learning ?? '—'}</span>
          <span>待复习 {vocabulary?.due ?? '—'}</span>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {materialCards.map((card) => {
          const readingItems = 'readingItems' in card ? card.readingItems ?? [] : []
          const isReadingCardWithHistory = card.actionType === 'reading' && readingItems.length > 0
          return (
          <div
            key={card.id}
            className="relative overflow-hidden rounded-lg border border-slate-200/90 bg-white shadow-[0_8px_24px_rgba(15,23,42,0.05)] transition-colors hover:border-indigo-200 focus-within:border-indigo-300"
          >
            <div className="h-1 bg-gradient-to-r from-slate-200 via-indigo-300 to-sky-300" />
            {'detailItems' in card ? (
              <button
                type="button"
                onClick={() => openDetails(card)}
                aria-label={`查看${card.title}详情`}
                className="absolute right-3 top-4 z-10 inline-flex size-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
                title="详情"
              >
                <ListChecks className="size-4" />
              </button>
            ) : null}
            <div className="flex min-h-[190px] w-full flex-col p-4 pr-12 text-left">
              <span className="flex size-10 items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-slate-700">
                {card.icon}
              </span>
              <span className="mt-4 text-base font-black text-slate-950">{card.title}</span>
              <span className="mt-2 line-clamp-2 flex-1 text-sm leading-6 text-slate-600">{card.description}</span>
              {readingItems.length > 0 ? (
                <div className="mt-3 space-y-1.5">
                  {readingItems.slice(0, 3).map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => onOpenReadingMaterial(item)}
                      className="block w-full truncate rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-left text-xs font-bold text-slate-700 transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
                    >
                      {item.title || '未命名阅读材料'}
                    </button>
                  ))}
                  {readingItems.length > 3 ? (
                    <button
                      type="button"
                      onClick={() => setIsReadingHistoryOpen(true)}
                      className="block w-full rounded-md border border-dashed border-indigo-200 bg-indigo-50/60 px-2.5 py-1.5 text-left text-xs font-black text-indigo-700 transition hover:border-indigo-300 hover:bg-indigo-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
                    >
                      查看全部 {readingItems.length} 篇
                    </button>
                  ) : null}
                </div>
              ) : null}
              <div className="mt-4 grid gap-2 text-xs font-bold text-slate-500">
                <span>{card.meta}</span>
                {isReadingCardWithHistory ? null : card.actionType !== 'details' && card.actionType !== 'reading' ? (
                  <button
                    type="button"
                    onClick={() => handleAction(card.actionType as UnitWorkspaceActionType, 'targetTopic' in card && typeof card.targetTopic === 'string' ? card.targetTopic : undefined)}
                    disabled={card.disabled || ('isLoading' in card && card.isLoading)}
                    className="inline-flex w-full items-center justify-center gap-1 whitespace-nowrap rounded-md bg-indigo-50 px-2.5 py-1.5 text-indigo-700 transition hover:bg-indigo-600 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 active:scale-[0.98] disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
                  >
                    {'isLoading' in card && card.isLoading ? '生成中' : card.actionLabel}
                    {'isLoading' in card && card.isLoading ? <LoaderCircle className="size-3.5 animate-spin" /> : <ArrowRight className="size-3.5" />}
                  </button>
                ) : null}
              </div>
            </div>
          </div>
          )
        })}
      </div>
      <MaterialDetailDialog detail={detail} onClose={() => setDetail(null)} />
      <ReadingMaterialHistoryDialog
        items={readingMaterials}
        open={isReadingHistoryOpen}
        onClose={() => setIsReadingHistoryOpen(false)}
        onOpenMaterial={(item) => {
          setIsReadingHistoryOpen(false)
          onOpenReadingMaterial(item)
        }}
      />
    </section>
  )
}

interface MaterialDetail {
  title: string
  subtitle: string
  items: UnitWorkspaceItem[]
  emptyMessage: string
  itemActionLabel?: string
  onItemAction?: (item: UnitWorkspaceItem) => void
}

function MaterialDetailDialog({ detail, onClose }: { detail: MaterialDetail | null; onClose: () => void }) {
  const titleId = useId()
  const { containerRef, handleKeyDown } = useFocusTrap<HTMLElement>({
    isActive: Boolean(detail),
    onEscape: onClose,
  })

  if (!detail) return null

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="关闭详情"
        onClick={onClose}
        className="absolute inset-0 bg-slate-950/35 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      />
      <section
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        className="relative flex max-h-[calc(100dvh-2rem)] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white p-6 shadow-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id={titleId} className="text-xl font-extrabold text-slate-950">{detail.title}详情</h2>
            <p className="mt-1 text-sm font-semibold text-slate-500">{detail.subtitle}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            aria-label="关闭详情"
          >
            <X className="size-5" />
          </button>
        </div>

        <div className="mt-5 min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain pr-1">
          {detail.items.length ? (
            detail.items.map((item, index) => (
              <article key={item.id} className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-lg bg-white text-xs font-black text-indigo-700 shadow-sm">
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <h3 className="font-extrabold text-slate-900">{item.title}</h3>
                        {item.summary ? <p className="mt-1 text-sm leading-6 text-slate-600">{item.summary}</p> : null}
                        <p className="mt-2 text-xs font-bold text-slate-400">{item.source_page || '教材条目'}</p>
                      </div>
                      {detail.itemActionLabel && detail.onItemAction ? (
                        <button
                          type="button"
                          onClick={() => detail.onItemAction?.(item)}
                          className="inline-flex shrink-0 items-center justify-center gap-1 rounded-lg bg-indigo-50 px-3 py-2 text-xs font-extrabold text-indigo-700 transition hover:bg-indigo-600 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 active:scale-[0.98]"
                        >
                          {detail.itemActionLabel}
                          <ArrowRight className="size-3.5" />
                        </button>
                      ) : null}
                    </div>
                  </div>
                </div>
              </article>
            ))
          ) : (
            <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 p-6 text-sm font-semibold text-slate-500">
              {detail.emptyMessage}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

function ReadingMaterialHistoryDialog({
  items,
  open,
  onClose,
  onOpenMaterial,
}: {
  items: ReadingMaterialGenerationResponse['material'][]
  open: boolean
  onClose: () => void
  onOpenMaterial: (item: ReadingMaterialGenerationResponse['material']) => void
}) {
  const titleId = useId()
  const { containerRef, handleKeyDown } = useFocusTrap<HTMLElement>({
    isActive: open,
    onEscape: onClose,
  })

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="关闭阅读材料历史"
        onClick={onClose}
        className="absolute inset-0 bg-slate-950/35 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      />
      <section
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        className="relative flex max-h-[calc(100dvh-2rem)] w-full max-w-2xl flex-col overflow-hidden rounded-xl bg-white p-5 shadow-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id={titleId} className="text-xl font-extrabold text-slate-950">本单元阅读材料</h2>
            <p className="mt-1 text-sm font-semibold text-slate-500">按最近更新时间排序，点标题继续阅读。</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            aria-label="关闭阅读材料历史"
          >
            <X className="size-5" />
          </button>
        </div>

        <div className="mt-5 min-h-0 flex-1 space-y-2 overflow-y-auto overscroll-contain pr-1">
          {items.map((item, index) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onOpenMaterial(item)}
              className="grid w-full grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-3 text-left transition hover:border-indigo-200 hover:bg-indigo-50/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
            >
              <span className="flex size-8 items-center justify-center rounded-md bg-slate-100 text-xs font-black text-slate-500">
                {index + 1}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-black text-slate-900">{item.title || '未命名阅读材料'}</span>
                <span className="mt-1 block text-xs font-semibold text-slate-500">
                  {item.word_count} 词 · {READING_MATERIAL_TYPE_LABELS[item.material_type]}
                </span>
              </span>
              <ArrowRight className="size-4 text-indigo-500" />
            </button>
          ))}
        </div>
      </section>
    </div>
  )
}

function TextbookCover({ overview }: { overview: KnowledgeBaseOverview }) {
  const useCover = overview.source.grade === 'grade-7' && overview.source.volume === 'upper'
  return useCover ? (
    <img
      src="/grade7-english-upper-cover.png"
      alt={`${overview.source.title}封面`}
      width={190}
      height={240}
      className="h-48 w-full rounded-xl border border-slate-100 object-cover object-[78%_center] shadow-sm md:h-full"
    />
  ) : (
    <div className="flex h-48 w-full flex-col justify-between rounded-xl border border-indigo-100 bg-gradient-to-br from-sky-50 to-emerald-50 p-4 text-slate-800 shadow-sm md:h-full">
      <div>
        <p className="text-xs font-black uppercase text-indigo-600">English</p>
        <h3 className="mt-2 text-2xl font-black">英语</h3>
        <p className="mt-1 text-sm font-bold text-slate-500">{overview.source.title}</p>
      </div>
      <p className="text-xs font-bold text-slate-500">{overview.source.publisher || '教材来源'}</p>
    </div>
  )
}

function UnitProgressBar({ value }: { value: number }) {
  return (
    <div className="h-2 overflow-hidden rounded-full bg-slate-200">
      <div
        className="h-full rounded-full bg-indigo-600 transition-[width] duration-500"
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  )
}

function fallbackUnitWorkspace(overview: KnowledgeBaseOverview): UnitLearningWorkspace {
  const groups: Array<[UnitWorkspaceSection['id'], string, string]> = [
    ['vocabulary', '核心词汇', 'vocabulary'],
    ['sentence_patterns', '句式', 'sentence_pattern'],
    ['grammar', '语法', 'grammar'],
    ['phrases', '短语', 'phrase'],
  ]
  const sections = groups.map(([id, title, type]) => {
    const items = overview.knowledge_points.filter((item) => item.type === type)
    return {
      id,
      title,
      count: items.length,
      items,
      action: {
        type: id === 'vocabulary' ? 'vocabulary_new' : id === 'grammar' ? 'grammar' : 'daily_lesson',
        label: id === 'vocabulary' ? '认识新词' : id === 'grammar' ? '进入语法学习' : '放进今日任务',
      } as UnitWorkspaceSection['action'],
      empty: items.length === 0,
    }
  })
  const masteryValues = overview.knowledge_points.map((item) => item.mastery ?? 0)
  const average = masteryValues.length ? masteryValues.reduce((sum, value) => sum + value, 0) / masteryValues.length : 0
  return {
    unit: { ...overview.current_unit, source_id: overview.source.id, source_title: overview.source.title },
    overview: {
      title: overview.current_unit.title,
      summary: `${overview.current_unit.title} ${overview.current_unit.subtitle}`.trim(),
      objectives: [],
    },
    sections: [
      ...sections,
      { id: 'practice', title: '练习', count: overview.knowledge_points.length, items: [], action: { type: 'exercise', label: '开始教材练习' }, empty: false },
    ],
    mastery_summary: {
      average,
      mastered_count: masteryValues.filter((value) => value >= 0.8).length,
      learning_count: masteryValues.filter((value) => value > 0 && value < 0.8).length,
      new_count: masteryValues.filter((value) => value === 0).length,
      total_count: masteryValues.length,
    },
    recommended_next_action: {
      type: 'vocabulary_new',
      label: '先认识本单元新词',
      reason: overview.recommendation_reason,
    },
  }
}

function normalizePercent(value: number) {
  const normalized = value <= 1 ? value * 100 : value
  return Math.round(Math.max(0, Math.min(100, normalized)))
}

function vocabularyPracticeEntry(vocabulary: UnitVocabularySummary | null): {
  mode: Extract<VocabularyPracticeMode, 'new' | 'review'> | null
  meta: string
  kind: 'loading' | 'new' | 'continue' | 'review' | 'empty'
} {
  if (!vocabulary) return { mode: null, meta: '词汇统计加载中', kind: 'loading' }
  if (vocabulary.due > 0) return { mode: 'review', meta: `${vocabulary.due} 个待复习`, kind: 'review' }
  if (vocabulary.new > 0) return { mode: 'new', meta: `${vocabulary.new} 个新词`, kind: 'new' }
  if (vocabulary.learning > 0) return { mode: 'new', meta: `${vocabulary.learning} 个学习中`, kind: 'continue' }
  if (vocabulary.total > 0) return { mode: null, meta: `${vocabulary.total} 个词已安排`, kind: 'empty' }
  return { mode: null, meta: '暂无词表', kind: 'empty' }
}

function unitVocabularySummaryText(vocabulary: UnitVocabularySummary) {
  const parts = [`本单元 ${vocabulary.total} 个词`]
  if (vocabulary.new > 0) parts.push(`${vocabulary.new} 个新词`)
  if (vocabulary.learning > 0) parts.push(`${vocabulary.learning} 个学习中`)
  if (vocabulary.due > 0) parts.push(`${vocabulary.due} 个待复习`)
  return parts.join('，')
}

function buildCapabilityRecommendations(
  overview: KnowledgeBaseOverview,
  dailyRecommendations: CapabilityRecommendation[],
  dismissedIds: Set<string>,
) {
  const activeDailyRecommendations = dailyRecommendations
    .filter((item) => !dismissedIds.has(item.recommendation_id))
    .slice(0, 3)
  if (activeDailyRecommendations.length) return activeDailyRecommendations
  return fallbackCapabilityRecommendations(overview)
    .filter((item) => !dismissedIds.has(item.recommendation_id))
    .slice(0, 3)
}

function fallbackCapabilityRecommendations(overview: KnowledgeBaseOverview): CapabilityRecommendation[] {
  const workspace = overview.unit_workspace ?? fallbackUnitWorkspace(overview)
  const byType = (type: string) => overview.knowledge_points.filter((item) => item.type === type)
  const grammarItems = byType('grammar')
  const vocabularyItems = byType('vocabulary')
  const wordPartTarget = vocabularyItems.find((item) => isWordPartPracticeTarget(item.title))
  const vocabularyDetailTarget = vocabularyItems.find((item) => isVocabularyDetailTarget(item.title))
  const phraseItems = byType('phrase')
  const sentenceItems = byType('sentence_pattern')
  const pronunciationItems = byType('pronunciation')
  const unitTarget = `${overview.current_unit.title} ${overview.current_unit.subtitle}`.trim()
  const evidence = `${overview.current_unit.title} ${workspace.overview.title || '教材材料'}`.trim()
  const recommendations: CapabilityRecommendation[] = []

  if (grammarItems.length || workspace.sections.some((section) => section.id === 'grammar' && section.count > 0)) {
    recommendations.push(makeFallbackRecommendation({
      id: 'grammar',
      capabilityId: 'grammar-micro-knowledge',
      featureId: 'grammar-page',
      title: '语法微知识点',
      category: 'grammar',
      target: grammarItems[0]?.title ?? unitTarget,
      reason: '本单元包含可独立巩固的语法点，先做微知识点能让教材练习更稳。',
      evidence: grammarItems[0]?.source_page || evidence,
      toolTarget: 'grammar',
      priorityScore: 0.94,
    }))
  }

  if (vocabularyItems.length >= 6 && wordPartTarget) {
    recommendations.push(makeFallbackRecommendation({
      id: 'word-parts',
      capabilityId: 'word-parts',
      featureId: 'word-parts-page',
      title: '词根与词缀',
      category: 'vocabulary',
      target: wordPartTarget.title,
      reason: '本单元新词较多，拆词形和构词线索能降低记忆负担。',
      evidence: wordPartTarget.source_page || evidence,
      toolTarget: 'word-parts',
      priorityScore: 0.88,
    }))
  }

  if (vocabularyDetailTarget) {
    recommendations.push(makeFallbackRecommendation({
      id: 'vocabulary-detail',
      capabilityId: 'vocabulary-detail',
      featureId: 'vocabulary-detail-page',
      title: '词汇详解',
      category: 'vocabulary',
      target: vocabularyDetailTarget.title,
      reason: '挑一个本单元高频词做搭配、例句和近义辨析，会帮助后续阅读和写作。',
      evidence: vocabularyDetailTarget.source_page || evidence,
      toolTarget: 'vocabulary-detail',
      priorityScore: 0.82,
      action: 'vocabulary-detail',
    }))
  }

  if (sentenceItems.length || overview.knowledge_points.some((item) => item.summary.length > 80)) {
    recommendations.push(makeFallbackRecommendation({
      id: 'reading-workshop',
      capabilityId: 'reading-workshop',
      featureId: 'reading-workshop-page',
      title: '精读与泛读',
      category: 'reading',
      target: sentenceItems[0]?.title ?? unitTarget,
      reason: '本单元有句型或较长文本材料，适合做一次阅读策略加练。',
      evidence: sentenceItems[0]?.source_page || evidence,
      toolTarget: 'reading-workshop',
      priorityScore: 0.78,
    }))
  }

  if (pronunciationItems.length) {
    recommendations.push(makeFallbackRecommendation({
      id: 'pronunciation',
      capabilityId: 'pronunciation',
      featureId: 'pronunciation-page',
      title: '发音训练',
      category: 'speaking',
      target: pronunciationItems[0]?.title ?? unitTarget,
      reason: '本单元出现发音或拼读信号，适合单独做一次听辨和跟读。',
      evidence: pronunciationItems[0]?.source_page || evidence,
      toolTarget: 'pronunciation',
      priorityScore: 0.76,
    }))
  }

  if (phraseItems.length) {
    recommendations.push(makeFallbackRecommendation({
      id: 'writing-phrasebook',
      capabilityId: 'writing-phrasebook',
      featureId: 'writing-phrasebook-page',
      title: '好句收藏馆',
      category: 'writing',
      target: phraseItems[0]?.title ?? unitTarget,
      reason: '本单元有可迁移到表达中的短语和句型，适合收藏后做仿写。',
      evidence: phraseItems[0]?.source_page || evidence,
      toolTarget: 'writing-phrasebook',
      priorityScore: 0.72,
    }))
  }

  if (!recommendations.length) {
    recommendations.push(makeFallbackRecommendation({
      id: 'grammar-default',
      capabilityId: 'grammar-micro-knowledge',
      featureId: 'grammar-page',
      title: '语法微知识点',
      category: 'grammar',
      target: unitTarget,
      reason: '先用一个微知识点把本单元语言结构梳理清楚，再回到教材任务。',
      evidence,
      toolTarget: 'grammar',
      priorityScore: 0.7,
    }))
  }

  return recommendations
}

function isWordPartPracticeTarget(value: string) {
  const normalized = normalizeVocabularyTarget(value)
  if (!normalized || isLikelyBareProperNoun(normalized)) return false
  return /^[a-z][a-z'-]{2,}$/i.test(normalized)
}

function isVocabularyDetailTarget(value: string) {
  const normalized = normalizeVocabularyTarget(value)
  if (!normalized || isLikelyBareProperNoun(normalized)) return false
  return /[a-z]/i.test(normalized)
}

function normalizeVocabularyTarget(value: string) {
  return value.trim().replace(/^["'`“”‘’.,:;!?()[\]{}]+|["'`“”‘’.,:;!?()[\]{}]+$/g, '')
}

function isLikelyBareProperNoun(value: string) {
  const normalized = normalizeVocabularyTarget(value)
  if (!normalized) return false
  const tokens = normalized.split(/[\s-]+/).filter(Boolean)
  if (!tokens.length) return false
  return tokens.every((token) => /^[A-Z][a-z]+$/.test(token))
}

function makeFallbackRecommendation({
  id,
  capabilityId,
  featureId,
  title,
  category,
  target,
  reason,
  evidence,
  toolTarget,
  priorityScore,
  action = 'tool',
}: {
  id: string
  capabilityId: string
  featureId: string
  title: string
  category: string
  target: string
  reason: string
  evidence: string
  toolTarget: string
  priorityScore: number
  action?: string
}): CapabilityRecommendation {
  return {
    recommendation_id: `fallback-${id}`,
    capability_id: capabilityId,
    feature_id: featureId,
    title,
    reason,
    priority_score: priorityScore,
    category,
    action,
    tool_target: toolTarget,
    route_hint: featureId,
    input_payload: { target },
    evidence_refs: [evidence],
    source: 'fallback',
  }
}

function readRecommendationTarget(recommendation: CapabilityRecommendation) {
  const target = recommendation.input_payload?.target
  if (typeof target === 'string' && target.trim()) return target
  const promptSeed = recommendation.prompt_seed
  if (typeof promptSeed === 'string' && promptSeed.trim()) return promptSeed
  return null
}

function readRecommendationEvidence(recommendation: CapabilityRecommendation) {
  const firstEvidence = recommendation.evidence_refs?.[0]
  if (typeof firstEvidence === 'string' && firstEvidence.trim()) return firstEvidence
  if (isRecord(firstEvidence)) {
    for (const key of ['title', 'source', 'label', 'evidence']) {
      const value = firstEvidence[key]
      if (typeof value === 'string' && value.trim()) return value
    }
  }
  return recommendation.source === 'fallback' ? '当前单元材料' : `${recommendation.evidence_refs?.length ?? 0} 条学习证据`
}

function labelForCategory(category: string) {
  const labels: Record<string, string> = {
    listening: '听力',
    speaking: '口语',
    reading: '阅读',
    writing: '写作',
    vocabulary: '词汇',
    grammar: '语法',
    exam: '考试冲刺',
  }
  return labels[category] ?? category
}

function FailedSourceSummary({ source, onDelete }: { source: FailedKnowledgeSourceDetail; onDelete?: () => void }) {
  const reasons = normalizeBlockingReasons(source.blocking_reasons ?? [])

  return (
    <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-left">
      <p className="text-sm font-black text-amber-950">{source.title ?? source.filename ?? '最近上传的教材'} 暂时不能用于学习</p>
      {reasons.length ? (
        <ul className="mt-3 space-y-1 text-sm leading-6 text-amber-800">
          {reasons.map((reason) => <li key={reason}>- {reason}</li>)}
        </ul>
      ) : (
        <p className="mt-3 text-sm leading-6 text-amber-800">暂时没有足够的可用内容生成知识库。</p>
      )}
      <div className="mt-3 rounded-xl bg-white/70 px-3 py-2 text-sm leading-6 text-amber-900">
        {hasScannedPdfSignal(source)
          ? '系统会尝试本地 OCR 处理扫描版 PDF；如果仍不可用，请上传已 OCR、可复制文字的 PDF。'
          : '可以换成文字更清晰、可复制文字的 PDF 后重新上传。'}
      </div>
      {onDelete ? (
        <div className="mt-4">
          <Button variant="danger" onClick={onDelete} className="w-full">
            <Trash2 className="size-4" />
            删除这次上传
          </Button>
        </div>
      ) : null}
    </div>
  )
}

export function IngestStatusPanel({ status, compact = false }: { status: KnowledgeIngestStatus; compact?: boolean }) {
  const isFailed = status.next_action === 'upload_text_pdf' || status.quality_status === 'failed'
  const needsOcr = status.parse_quality_status === 'needs_ocr' || status.quality_summary?.needs_ocr === true
  const reasons = normalizeBlockingReasons(status.blocking_reasons ?? [])
  const progress = Math.max(0, Math.min(100, status.progress ?? 0))
  return (
    <section className={`w-full ${compact ? '' : 'max-w-lg'} rounded-2xl border ${isFailed ? 'border-red-200 bg-red-50' : 'border-indigo-200 bg-indigo-50'} p-5 text-left`}>
      <div className="flex items-start gap-3">
        {isFailed ? <AlertCircle className="mt-0.5 size-5 shrink-0 text-red-600" /> : <LoaderCircle className="mt-0.5 size-5 shrink-0 animate-spin text-indigo-600" />}
        <div className="min-w-0 flex-1">
          <p className={`font-black ${isFailed ? 'text-red-950' : 'text-indigo-950'}`}>
            {isFailed ? '教材暂时不能用于学习' : '教材正在解析'}
          </p>
          <p className={`mt-1 text-sm leading-6 ${isFailed ? 'text-red-700' : 'text-indigo-700'}`}>{status.message}</p>
          {!isFailed ? (
            <>
              <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/70">
                <div className="h-full rounded-full bg-indigo-600 transition-[width] duration-500" style={{ width: `${progress}%` }} />
              </div>
              <p className="mt-2 text-xs font-bold text-indigo-700">{stageLabel(status.stage)} · {progress}%</p>
            </>
          ) : null}
          {isFailed && reasons.length ? (
            <ul className="mt-3 space-y-1 text-sm leading-6 text-red-700">
              {reasons.map((reason) => <li key={reason}>- {reason}</li>)}
            </ul>
          ) : null}
          {(isFailed && hasScannedPdfSignal(status)) || needsOcr ? (
            <p className={`mt-3 rounded-xl bg-white/70 px-3 py-2 text-sm font-bold leading-6 ${isFailed ? 'text-red-800' : 'text-indigo-800'}`}>
              当前 PDF 文本层较弱，系统会尝试本地 OCR；如果仍不完整，请上传已 OCR 的可搜索 PDF。
            </p>
          ) : null}
        </div>
      </div>
    </section>
  )
}

function stageLabel(stage: string) {
  const labels: Record<string, string> = {
    queued: '等待开始',
    running: '正在解析',
    parsing_document: '解析文档',
    normalizing_artifact: '标准化解析结果',
    extracting_textbook_structure: '整理教材内容',
    building_chunks: '建立索引',
    quality_checking: '质量检查',
    completed: '解析完成',
    failed: '解析失败',
  }
  return labels[stage] ?? stage
}

function CapabilityBoosterDrawer({
  open,
  titleId,
  drawerRef,
  onKeyDown,
  recommendations,
  busyRecommendationId,
  onOpenRecommendation,
  onDismissRecommendation,
  onClose,
  onExploreMore,
}: {
  open: boolean
  titleId: string
  drawerRef: Ref<HTMLElement>
  onKeyDown: KeyboardEventHandler<HTMLElement>
  recommendations: CapabilityRecommendation[]
  busyRecommendationId: string | null
  onOpenRecommendation: (recommendation: CapabilityRecommendation) => void
  onDismissRecommendation: (recommendation: CapabilityRecommendation) => void
  onClose: () => void
  onExploreMore: () => void
}) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50">
      <button
        type="button"
        aria-label="关闭能力加练"
        onClick={onClose}
        className="absolute inset-0 bg-slate-950/30 transition-opacity focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
      />
      <section
        ref={drawerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        className="absolute bottom-0 left-0 right-0 flex max-h-[70dvh] flex-col overflow-hidden rounded-t-2xl bg-white shadow-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary sm:left-auto sm:top-0 sm:h-full sm:max-h-none sm:w-[min(400px,92vw)] sm:rounded-none"
      >
        <header className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div className="min-w-0">
            <p className="text-xs font-black uppercase tracking-wide text-indigo-600">Capability Booster</p>
            <h2 id={titleId} className="mt-1 text-lg font-black text-slate-950">适合本单元的能力加练</h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">根据当前单元知识点、练习结果和近期薄弱点推荐。</p>
          </div>
          <IconButton
            label="关闭能力加练"
            onClick={onClose}
            className="border-transparent text-slate-500 hover:bg-slate-100 hover:text-slate-900"
          >
            <X className="size-4" />
          </IconButton>
        </header>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain px-5 py-5">
          {recommendations.slice(0, 3).map((recommendation) => (
            <CapabilityBoosterCard
              key={recommendation.recommendation_id}
              recommendation={recommendation}
              isBusy={busyRecommendationId === recommendation.recommendation_id}
              onOpen={onOpenRecommendation}
              onDismiss={onDismissRecommendation}
            />
          ))}
        </div>

        <footer className="border-t border-slate-200 bg-white px-5 py-4">
          <Button variant="secondary" onClick={onExploreMore} className="w-full">
            <LibraryBig className="size-4" />
            查看更多能力
          </Button>
        </footer>
      </section>
    </div>
  )
}

function CapabilityBoosterCard({
  recommendation,
  isBusy,
  onOpen,
  onDismiss,
}: {
  recommendation: CapabilityRecommendation
  isBusy: boolean
  onOpen: (recommendation: CapabilityRecommendation) => void
  onDismiss: (recommendation: CapabilityRecommendation) => void
}) {
  const target = readRecommendationTarget(recommendation)
  const evidence = readRecommendationEvidence(recommendation)

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-[0_4px_14px_rgba(15,23,42,0.04)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-black uppercase tracking-wide text-indigo-600">{labelForCategory(recommendation.category)}</p>
          <h3 className="mt-1 text-base font-black text-slate-950">{recommendation.title}</h3>
        </div>
        <span className="rounded-md bg-indigo-50 px-2 py-1 text-xs font-black text-indigo-700">
          {Math.round(recommendation.priority_score * 100)}%
        </span>
      </div>
      {target ? (
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm font-bold text-slate-800">
          目标：{target}
        </p>
      ) : null}
      <p className="mt-3 text-sm leading-6 text-slate-600">{recommendation.reason}</p>
      <p className="mt-3 text-xs font-bold text-slate-500">
        证据：{evidence}
      </p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <Button onClick={() => onOpen(recommendation)} disabled={isBusy} className="px-3">
          {isBusy ? <LoaderCircle className="size-4 animate-spin" /> : <ArrowRight className="size-4" />}
          去学习
        </Button>
        <Button variant="ghost" onClick={() => onDismiss(recommendation)} disabled={isBusy} className="px-3">
          稍后
        </Button>
      </div>
    </article>
  )
}

function DailyLessonRuntimeDialog({
  lesson,
  answer,
  isSubmitting,
  dismissedRecommendationIds,
  busyRecommendationId,
  onAnswerChange,
  onSubmit,
  boosterCount,
  onOpenBoosterDrawer,
  onDismissRecommendation,
  onClose,
}: {
  lesson: DailyLessonRuntime | null
  answer: string
  isSubmitting: boolean
  dismissedRecommendationIds: Set<string>
  busyRecommendationId: string | null
  onAnswerChange: (value: string) => void
  onSubmit: (answer: string) => void
  boosterCount: number
  onOpenBoosterDrawer: () => void
  onDismissRecommendation: (recommendation: CapabilityRecommendation) => void
  onClose: () => void
}) {
  const titleId = useId()
  const [draftAnswer, setDraftAnswer] = useState(answer)
  const { containerRef, handleKeyDown } = useFocusTrap<HTMLElement>({
    isActive: Boolean(lesson),
    onEscape: onClose,
    isEscapeEnabled: !isSubmitting,
  })

  const handleDraftChange = (value: string) => {
    setDraftAnswer(value)
    onAnswerChange(value)
  }

  if (!lesson) return null
  const prompt = lesson.prompt ?? readPrompt(lesson.initial_payload) ?? '完成这道学习任务。'
  const options = readOptions(lesson.initial_payload)
  const isCompleted = lesson.status === 'completed' || Boolean(lesson.verification_status)
  const recommendations = (lesson.next_capability_recommendations ?? [])
    .filter((item) => !dismissedRecommendationIds.has(item.recommendation_id))
  const statusLabel = isCompleted ? '已完成' : '待作答'
  const canSubmit = Boolean(draftAnswer.trim()) && !isSubmitting

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-3 py-4 motion-reduce:transition-none sm:px-4 sm:py-6">
      <section
        ref={containerRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={handleKeyDown}
        className="flex h-[min(760px,calc(100dvh-2rem))] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <header className="flex items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div className="min-w-0">
            <p className="text-xs font-black uppercase tracking-wide text-indigo-600">Daily Lesson</p>
            <h2 id={titleId} className="mt-1 truncate text-lg font-black text-slate-950">
              AI 每日题 · {statusLabel}
            </h2>
          </div>
          <IconButton
            label="关闭 AI 每日题"
            onClick={onClose}
            className="border-transparent text-slate-500 hover:bg-slate-100 hover:text-slate-900"
          >
            <X className="size-4" />
          </IconButton>
        </header>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-5 py-5">
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
            <p className="whitespace-pre-wrap text-sm font-bold leading-6 text-slate-900">{prompt}</p>
          </div>

          {!isCompleted ? (
            <div className="space-y-3">
              {options.length ? (
                <div className="grid gap-2 sm:grid-cols-2" aria-label="AI 每日题选项">
                  {options.map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => handleDraftChange(option)}
                      aria-pressed={draftAnswer === option}
                      className={`rounded-xl border px-4 py-3 text-left text-sm font-bold transition-[background-color,border-color,box-shadow,transform,color] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-200 ${
                        draftAnswer === option
                          ? 'border-indigo-500 bg-indigo-50 text-indigo-700 shadow-sm'
                          : 'border-slate-200 text-slate-700 hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-sm'
                      }`}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              ) : null}
              <textarea
                name="daily_lesson_answer"
                autoComplete="off"
                aria-label="AI 每日题答案"
                value={draftAnswer}
                onChange={(event) => handleDraftChange(event.target.value)}
                className="min-h-32 w-full resize-y rounded-xl border border-slate-200 px-4 py-3 text-sm leading-6 text-slate-900 transition-colors focus-visible:border-indigo-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-100"
                placeholder="输入你的答案…"
              />
            </div>
          ) : (
            <div className="space-y-3">
              <StatusBanner tone={lesson.verification_status === 'failed' ? 'warning' : 'success'} title="今日练习已完成">
                {readLearningFeedback(lesson.feedback) ?? '已经记录本次练习，接下来可以按推荐继续巩固。'}
              </StatusBanner>
              {recommendations.length ? (
                <div className="rounded-xl border border-indigo-100 bg-indigo-50/70 p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="text-sm font-black text-indigo-950">发现 {boosterCount} 个能力加练</p>
                      <p className="mt-1 text-sm leading-6 text-indigo-800">这些入口已放到右侧抽屉，主线任务和加练分开处理。</p>
                    </div>
                    <Button onClick={onOpenBoosterDrawer}>
                      <Sparkles className="size-4" />
                      打开能力加练
                    </Button>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {recommendations.slice(0, 3).map((recommendation) => (
                      <button
                        key={recommendation.recommendation_id}
                        type="button"
                        onClick={() => onDismissRecommendation(recommendation)}
                        disabled={busyRecommendationId === recommendation.recommendation_id}
                        className="rounded-md bg-white px-2.5 py-1.5 text-xs font-bold text-indigo-700 shadow-sm transition hover:bg-indigo-100 disabled:opacity-60"
                      >
                        {recommendation.title} · 稍后
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </div>

        <footer className="flex flex-col gap-2 border-t border-slate-200 bg-white px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs font-semibold text-slate-500">
            {isCompleted ? '本次练习已写入学习记录。' : '提交后会生成反馈、掌握度和下一步推荐。'}
          </p>
          {!isCompleted ? (
            <Button onClick={() => onSubmit(draftAnswer)} disabled={!canSubmit} className="w-full sm:w-auto">
              {isSubmitting ? <LoaderCircle className="size-4 animate-spin" /> : <Send className="size-4" />}
              {isSubmitting ? '提交中…' : '提交答案'}
            </Button>
          ) : (
            <Button variant="secondary" onClick={onClose} className="w-full sm:w-auto">
              关闭
            </Button>
          )}
        </footer>
      </section>
    </div>
  )
}

function readPrompt(payload?: Record<string, unknown> | null) {
  if (!payload) return null
  const direct = payload.prompt
  if (typeof direct === 'string' && direct.trim()) return direct
  const promptPayload = payload.prompt_payload
  if (isRecord(promptPayload) && typeof promptPayload.prompt === 'string') return promptPayload.prompt
  const materials = readInputMaterials(payload)
  const first = materials[0]
  if (!first) return null
  for (const key of ['prompt', 'stem', 'content']) {
    const value = first[key]
    if (typeof value === 'string' && value.trim()) return value
  }
  return null
}

function readLearningFeedback(value: unknown) {
  if (!value) return null
  if (typeof value === 'string') return value
  if (!isRecord(value)) return null
  for (const key of ['summary', 'feedback', 'message', 'explanation']) {
    const item = value[key]
    if (typeof item === 'string' && item.trim()) return item
  }
  return null
}

function readOptions(payload?: Record<string, unknown> | null) {
  const materials = readInputMaterials(payload)
  const first = materials[0]
  const rawOptions = first?.options
  return Array.isArray(rawOptions) ? rawOptions.map(String) : []
}

function readInputMaterials(payload?: Record<string, unknown> | null): Array<Record<string, unknown>> {
  if (!payload) return []
  const direct = payload.input_materials
  if (Array.isArray(direct)) return direct.filter(isRecord)
  const promptPayload = payload.prompt_payload
  if (isRecord(promptPayload) && Array.isArray(promptPayload.input_materials)) {
    return promptPayload.input_materials.filter(isRecord)
  }
  return []
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}
