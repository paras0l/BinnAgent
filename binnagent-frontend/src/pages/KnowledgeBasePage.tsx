import { AlertCircle, BookCheck, BookOpen, ChevronLeft, Dumbbell, GraduationCap, Languages, LoaderCircle, PanelLeftOpen, PanelRightOpen, Send, Sparkles, Target, Trash2, UploadCloud, X } from 'lucide-react'
import { useCallback, useEffect, useId, useMemo, useState, type ReactNode } from 'react'
import {
  CapabilityRecommendationCard,
  type CapabilityRecommendation,
} from '@/components/learning/CapabilityRecommendationCard'
import { ReasonCard } from '@/components/learning/ReasonCard'
import { PageShell } from '@/components/layout/PageShell'
import { CurriculumRail } from '@/components/knowledge/CurriculumRail'
import { ExerciseSessionDialog } from '@/components/knowledge/ExerciseSessionDialog'
import { KnowledgeContextPanel } from '@/components/knowledge/KnowledgeContextPanel'
import { LessonSessionDialog } from '@/components/knowledge/LessonSessionDialog'
import { UploadTextbookDialog } from '@/components/knowledge/UploadTextbookDialog'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { IconButton } from '@/components/ui/IconButton'
import { StatusBanner } from '@/components/ui/StatusBanner'
import { useFocusTrap } from '@/hooks/useFocusTrap'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { useToast } from '@/hooks/useToast'
import { GrammarPage } from '@/pages/GrammarPage'
import { deleteKnowledgeSource } from '@/api/knowledge'
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

type KnowledgeWorkspace = 'today' | 'unit' | 'exercises'

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

const WORKSPACES: Array<{ id: KnowledgeWorkspace; label: string }> = [
  { id: 'today', label: '今日任务' },
  { id: 'unit', label: '单元内容' },
  { id: 'exercises', label: '练习任务' },
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

export function KnowledgeBasePage({ learner, onBack, onStartVocabularyPractice }: KnowledgeBasePageProps) {
  const { showToast } = useToast()
  const [overview, setOverview] = useState<KnowledgeBaseOverview | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [failedSource, setFailedSource] = useState<FailedKnowledgeSourceDetail | null>(null)
  const [ingestStatus, setIngestStatus] = useState<KnowledgeIngestStatus | null>(null)
  const [workspace, setWorkspace] = useState<KnowledgeWorkspace>('today')
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null)
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [deleteSourceTarget, setDeleteSourceTarget] = useState<DeleteSourceTarget | null>(null)
  const [isDeletingSource, setIsDeletingSource] = useState(false)
  const [lessonSession, setLessonSession] = useState<KnowledgeLessonSession | null>(null)
  const [isStartingLesson, setIsStartingLesson] = useState(false)
  const [unitVocabulary, setUnitVocabulary] = useState<UnitVocabularySummary | null>(null)
  const [grammarTopic, setGrammarTopic] = useState<string | null>(null)
  const [exerciseSession, setExerciseSession] = useState<ExerciseSession | null>(null)
  const [isStartingExercise, setIsStartingExercise] = useState(false)
  const [dailyLesson, setDailyLesson] = useState<DailyLessonRuntime | null>(null)
  const [dailyAnswer, setDailyAnswer] = useState('')
  const [isStartingDailyLesson, setIsStartingDailyLesson] = useState(false)
  const [isCurriculumRailOpen, setIsCurriculumRailOpen] = useState(false)
  const [isContextPanelOpen, setIsContextPanelOpen] = useState(false)
  const [isSubmittingDailyAnswer, setIsSubmittingDailyAnswer] = useState(false)
  const [dismissedDailyRecommendationIds, setDismissedDailyRecommendationIds] = useState<Set<string>>(() => new Set())
  const [busyDailyRecommendationId, setBusyDailyRecommendationId] = useState<string | null>(null)
  const isKnowledgePanelDrawer = useMediaQuery('(max-width: 767px)')
  const curriculumPanelId = useId()
  const curriculumTitleId = useId()
  const contextPanelId = useId()
  const contextTitleId = useId()
  const { containerRef: curriculumPanelRef, handleKeyDown: handleCurriculumPanelKeyDown } = useFocusTrap<HTMLElement>({
    isActive: isKnowledgePanelDrawer && isCurriculumRailOpen,
    onEscape: () => setIsCurriculumRailOpen(false),
  })
  const { containerRef: contextPanelRef, handleKeyDown: handleContextPanelKeyDown } = useFocusTrap<HTMLElement>({
    isActive: isKnowledgePanelDrawer && isContextPanelOpen,
    onEscape: () => setIsContextPanelOpen(false),
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
    setIsStartingLesson(true)
    try {
      const response = await fetch(
        `/api/learners/${learner.id}/knowledge-base/lessons/${overview?.current_unit.id}/start`,
        { method: 'POST' }
      )
      if (!response.ok) throw new Error('今日课程暂时无法开始。')
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
    void loadOverview(selectedSourceId ?? overview?.source.id, nodeId)
  }

  const handleSelectSource = (sourceId: string) => {
    if (sourceId === selectedSourceId) return
    setSelectedSourceId(sourceId)
    setSelectedNodeId(null)
    setUnitVocabulary(null)
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
    const result = await response.json() as KnowledgeLessonCompleteResult
    setLessonSession(null)
    if (result.next_node_id) {
      showToast(`本单元已完成，接下来学习「${result.next_unit_title}」。`, { variant: 'success', duration: 6000 })
      await loadOverview(selectedSourceId ?? overview?.source.id, result.next_node_id)
    } else {
      showToast('恭喜，你已经完成本册全部课程！', { variant: 'success', duration: 6000 })
      await loadOverview(selectedSourceId ?? overview?.source.id)
    }
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

  const handleSubmitDailyAnswer = async () => {
    if (!dailyLesson || !dailyAnswer.trim()) {
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
          body: JSON.stringify({ answer: dailyAnswer.trim(), metadata: {} }),
        },
      )
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

  const handleOpenDailyCapabilityRecommendation = async (recommendation: CapabilityRecommendation) => {
    setBusyDailyRecommendationId(recommendation.recommendation_id)
    try {
      await recordDailyCapabilityEvent(recommendation, 'clicked')
      setDailyLesson(null)
      if (recommendation.tool_target === 'grammar') {
        setGrammarTopic(null)
        setGrammarTopic('grammar')
      } else if (recommendation.tool_target === 'reading-workshop') {
        showToast('请在探索页打开精读与泛读入口。', { variant: 'info' })
      } else if (recommendation.tool_target === 'writing-phrasebook') {
        showToast('请在探索页打开好句收藏馆入口。', { variant: 'info' })
      } else if (recommendation.tool_target === 'word-parts') {
        showToast('请在探索页打开词根与词缀入口。', { variant: 'info' })
      } else if (recommendation.action === 'vocabulary-detail') {
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
      await recordDailyCapabilityEvent(recommendation, 'dismissed')
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
  const sourceProgressPercent = normalizePercent(overview.source.progress)
  const knowledgeShellStyle = {
    gridTemplateColumns: isCurriculumRailOpen
      ? '280px minmax(0, 1fr)'
      : isContextPanelOpen
        ? 'minmax(0, 1fr) 310px'
        : 'minmax(0, 1fr)',
  }
  const curriculumRailClassName = isCurriculumRailOpen
    ? 'max-md:fixed max-md:bottom-0 max-md:left-0 max-md:top-16 max-md:z-40 max-md:w-[min(86vw,22rem)] max-md:min-h-0 max-md:overflow-y-auto max-md:shadow-2xl max-md:transition-[transform,opacity] max-md:duration-200 max-md:motion-reduce:transition-none'
    : 'hidden'
  const contextPanelClassName = isContextPanelOpen
    ? 'max-md:fixed max-md:bottom-0 max-md:right-0 max-md:top-16 max-md:z-40 max-md:w-[min(88vw,23rem)] max-md:overflow-y-auto max-md:shadow-2xl max-md:transition-[transform,opacity] max-md:duration-200 max-md:motion-reduce:transition-none'
    : 'hidden'

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
          <span>今日学习</span>
          <span className="mx-2 text-slate-300">/</span>
          <span className="hidden sm:inline">{overview.current_unit.title} · {overview.current_unit.subtitle}</span>
        </div>
        <div className="knowledge-shell grid min-h-[calc(100vh-7rem)] bg-white" style={knowledgeShellStyle}>
      {isKnowledgePanelDrawer && isCurriculumRailOpen ? (
        <button
          type="button"
          aria-label="收起教材目录"
          onClick={() => setIsCurriculumRailOpen(false)}
          className="fixed inset-x-0 bottom-0 top-16 z-30 bg-slate-950/30 transition-opacity duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 motion-reduce:transition-none md:hidden"
        />
      ) : null}
      <CurriculumRail
        panelId={curriculumPanelId}
        titleId={curriculumTitleId}
        panelRef={isKnowledgePanelDrawer ? curriculumPanelRef : undefined}
        role={isKnowledgePanelDrawer ? 'dialog' : undefined}
        ariaModal={isKnowledgePanelDrawer ? true : undefined}
        ariaLabelledby={isKnowledgePanelDrawer ? curriculumTitleId : undefined}
        tabIndex={isKnowledgePanelDrawer ? -1 : undefined}
        onKeyDown={isKnowledgePanelDrawer ? handleCurriculumPanelKeyDown : undefined}
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

      <main className="min-w-0 px-6 py-8 xl:px-8">
        <div className="mx-auto max-w-4xl">
          <div className="mb-5 grid gap-2 sm:grid-cols-2">
            <button
              type="button"
              onClick={() => {
                setIsCurriculumRailOpen((current) => {
                  const next = !current
                  if (next) setIsContextPanelOpen(false)
                  return next
                })
              }}
              aria-expanded={isCurriculumRailOpen}
              aria-controls={curriculumPanelId}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 transition-colors hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
            >
              <PanelLeftOpen className="size-4" />
              {isCurriculumRailOpen ? '收起教材目录' : '展开教材目录'}
            </button>
            <button
              type="button"
              onClick={() => {
                setIsContextPanelOpen((current) => {
                  const next = !current
                  if (next) setIsCurriculumRailOpen(false)
                  return next
                })
              }}
              aria-expanded={isContextPanelOpen}
              aria-controls={contextPanelId}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 transition-colors hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
            >
              <PanelRightOpen className="size-4" />
              {isContextPanelOpen ? '收起学习概览' : '展开学习概览'}
            </button>
          </div>

          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-black tracking-tight text-slate-950">今日学习</h1>
              <p className="mt-2 text-sm text-slate-500">围绕当前单元完成一组清晰任务：先学、再练、最后复习。</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-right shadow-sm">
              <p className="text-xs font-bold text-slate-500">当前进度</p>
              <p className="mt-1 text-2xl font-black text-indigo-600">{sourceProgressPercent}%</p>
            </div>
          </div>

          <div className="mt-6 flex gap-2 overflow-x-auto border-b border-slate-200" role="tablist" aria-label="教材工作区">
            {WORKSPACES.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={workspace === item.id}
                onClick={() => setWorkspace(item.id)}
                className={`relative shrink-0 px-1 pb-3 text-sm font-bold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 ${
                  workspace === item.id ? 'text-indigo-600' : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                {item.label}
                {workspace === item.id ? <span className="absolute inset-x-0 bottom-0 h-0.5 rounded-full bg-indigo-600" /> : null}
              </button>
            ))}
          </div>

          <div className="mt-5">
            {ingestStatus ? (
              <div className="mb-4">
                <IngestStatusPanel status={ingestStatus} compact />
              </div>
            ) : null}
          </div>

          {workspace === 'today' ? (
            <TodayLearningPlan
              overview={overview}
              vocabulary={activeUnitVocabulary}
              isStartingExercise={isStartingExercise}
              isStartingDailyLesson={isStartingDailyLesson}
              onStartVocabulary={(mode) => onStartVocabularyPractice(mode, overview.current_unit.id, currentSourceLabel)}
              onStartExercise={() => void handleStartExercise()}
              onStartDailyLesson={() => void handleStartDailyLesson()}
            />
          ) : null}

          {workspace === 'unit' ? (
            <div className="mt-6">
              <UnitLearningWorkspaceView
                workspace={overview.unit_workspace}
                overview={overview}
                vocabulary={activeUnitVocabulary}
                sourceLabel={currentSourceLabel}
                isStartingLesson={isStartingLesson}
                isStartingDailyLesson={isStartingDailyLesson}
                isStartingExercise={isStartingExercise}
                onStartLesson={() => void handleStartLesson()}
                onStartDailyLesson={() => void handleStartDailyLesson()}
                onStartExercise={() => void handleStartExercise()}
                onStartVocabulary={(mode) => onStartVocabularyPractice(mode, overview.current_unit.id, currentSourceLabel)}
                onStartGrammar={setGrammarTopic}
              />
            </div>
          ) : null}

          {workspace === 'exercises' ? (
            <ExerciseWorkspace
              overview={overview}
              isStartingExercise={isStartingExercise}
              onStartExercise={() => void handleStartExercise()}
              onStartSpelling={() => onStartVocabularyPractice('spelling', overview.current_unit.id, currentSourceLabel)}
            />
          ) : null}

          <details className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_4px_14px_rgba(15,23,42,0.05)]">
            <summary className="cursor-pointer text-sm font-black text-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500">
              切换教材或添加资料
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

      {isKnowledgePanelDrawer && isContextPanelOpen ? (
        <button
          type="button"
          aria-label="收起学习概览"
          onClick={() => setIsContextPanelOpen(false)}
          className="fixed inset-x-0 bottom-0 top-16 z-30 bg-slate-950/30 transition-opacity duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500 motion-reduce:transition-none md:hidden"
        />
      ) : null}
      <KnowledgeContextPanel
        overview={overview}
        panelId={contextPanelId}
        titleId={contextTitleId}
        panelRef={isKnowledgePanelDrawer ? contextPanelRef : undefined}
        role={isKnowledgePanelDrawer ? 'dialog' : undefined}
        ariaModal={isKnowledgePanelDrawer ? true : undefined}
        ariaLabelledby={isKnowledgePanelDrawer ? contextTitleId : undefined}
        tabIndex={isKnowledgePanelDrawer ? -1 : undefined}
        onKeyDown={isKnowledgePanelDrawer ? handleContextPanelKeyDown : undefined}
        className={contextPanelClassName}
        onUpload={() => {
          setIsContextPanelOpen(false)
          setIsUploadOpen(true)
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
          setLessonSession(null)
          void loadOverview(selectedSourceId ?? overview.source.id)
        }}
        onAttempt={handleAttempt}
        onComplete={handleCompleteLesson}
      />
      <DailyLessonRuntimeDialog
        lesson={dailyLesson}
        answer={dailyAnswer}
        isSubmitting={isSubmittingDailyAnswer}
        dismissedRecommendationIds={dismissedDailyRecommendationIds}
        busyRecommendationId={busyDailyRecommendationId}
        onAnswerChange={setDailyAnswer}
        onSubmit={() => void handleSubmitDailyAnswer()}
        onOpenRecommendation={(item) => void handleOpenDailyCapabilityRecommendation(item)}
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

function TodayLearningPlan({
  overview,
  vocabulary,
  isStartingExercise,
  isStartingDailyLesson,
  onStartVocabulary,
  onStartExercise,
  onStartDailyLesson,
}: {
  overview: KnowledgeBaseOverview
  vocabulary: UnitVocabularySummary | null
  isStartingExercise: boolean
  isStartingDailyLesson: boolean
  onStartVocabulary: (mode: VocabularyPracticeMode) => void
  onStartExercise: () => void
  onStartDailyLesson: () => void
}) {
  const due = vocabulary?.due ?? 0
  const steps = [
    {
      title: due > 0 ? '复习到期词汇' : '预习本单元词汇',
      meta: due > 0 ? `${due} 个待复习` : `${vocabulary?.new ?? 0} 个新词`,
      icon: <BookOpen className="size-5" />,
      active: due > 0,
      action: () => onStartVocabulary(due > 0 ? 'review' : 'new'),
      busy: false,
    },
    {
      title: '练一道教材题',
      meta: `预计 ${overview.daily_lesson.estimated_minutes} 分钟`,
      icon: <Target className="size-5" />,
      active: due === 0,
      action: onStartExercise,
      busy: isStartingExercise,
    },
    {
      title: 'AI 每日题',
      meta: '完成后给出下一步',
      icon: <Sparkles className="size-5" />,
      active: false,
      action: onStartDailyLesson,
      busy: isStartingDailyLesson,
    },
  ]

  return (
    <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_4px_14px_rgba(15,23,42,0.05)]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex size-9 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700">
              <Sparkles className="size-5" />
            </span>
            <h2 className="text-xl font-black text-slate-950">今天先做什么</h2>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            根据当前单元和复习计划，今天只保留三步：词汇、教材题、AI 每日题。
          </p>
        </div>
        <div className="rounded-lg bg-emerald-50 px-3 py-2 text-sm font-black text-emerald-700">
          今日 3 步
        </div>
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-3">
        {steps.map((step, index) => (
          <button
            key={step.title}
            type="button"
            onClick={step.action}
            disabled={step.busy}
            className={`group grid grid-cols-[32px_minmax(0,1fr)] gap-3 rounded-xl border px-4 py-4 text-left transition disabled:cursor-not-allowed disabled:opacity-70 ${
              step.active
                ? 'border-emerald-300 bg-emerald-50 text-emerald-950 shadow-sm'
                : 'border-slate-200 bg-white text-slate-800 hover:border-indigo-200 hover:bg-indigo-50/40'
            } focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500`}
          >
            <span className={`flex size-8 items-center justify-center rounded-full text-sm font-black ${
              step.active ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-500 group-hover:bg-indigo-100 group-hover:text-indigo-700'
            }`}>
              {step.busy ? <LoaderCircle className="size-4 animate-spin" /> : index + 1}
            </span>
            <span className="min-w-0">
              <span className="flex items-center gap-2">
                <span className={step.active ? 'text-emerald-700' : 'text-indigo-600'}>{step.icon}</span>
                <span className="truncate text-sm font-black">{step.title}</span>
              </span>
              <span className="mt-1 block text-xs font-semibold text-slate-500">{step.meta}</span>
            </span>
          </button>
        ))}
      </div>
    </section>
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
          <p className="mt-1 text-sm text-slate-500">切换教材后，今日单元和练习会跟着更新。</p>
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

function UnitLearningWorkspaceView({
  workspace,
  overview,
  vocabulary,
  sourceLabel,
  isStartingLesson,
  isStartingDailyLesson,
  isStartingExercise,
  onStartLesson,
  onStartDailyLesson,
  onStartExercise,
  onStartVocabulary,
  onStartGrammar,
}: {
  workspace?: UnitLearningWorkspace
  overview: KnowledgeBaseOverview
  vocabulary: UnitVocabularySummary | null
  sourceLabel: string
  isStartingLesson: boolean
  isStartingDailyLesson: boolean
  isStartingExercise: boolean
  onStartLesson: () => void
  onStartDailyLesson: () => void
  onStartExercise: () => void
  onStartVocabulary: (mode: VocabularyPracticeMode) => void
  onStartGrammar: (topic: string) => void
}) {
  const unitWorkspace = workspace ?? fallbackUnitWorkspace(overview)
  const recommended = unitWorkspace.recommended_next_action
  const recommendedType = recommended.type === 'pronunciation' ? 'exercise' : recommended.type
  const recommendedLabel = recommended.type === 'pronunciation' ? '练一道教材题' : recommended.label
  const recommendedReason = recommended.type === 'pronunciation'
    ? '先用教材题检查本单元掌握情况。'
    : recommended.reason
  const visibleSections = unitWorkspace.sections.filter((section) => section.id !== 'pronunciation')
  const handleAction = (type: UnitWorkspaceActionType, section?: UnitWorkspaceSection) => {
    if (type === 'vocabulary_new') onStartVocabulary('new')
    else if (type === 'vocabulary_spelling') onStartVocabulary('spelling')
    else if (type === 'daily_lesson') onStartDailyLesson()
    else if (type === 'exercise') onStartExercise()
    else if (type === 'grammar') {
      const topic = recommended.target ?? section?.items[0]?.title
      if (topic) onStartGrammar(topic)
    }
  }

  return (
    <section className="space-y-5">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="rounded-2xl border border-indigo-200 bg-white p-5 shadow-[0_4px_14px_rgba(15,23,42,0.05)]">
          <div className="grid gap-5 md:grid-cols-[190px_minmax(0,1fr)]">
            <TextbookCover overview={overview} />
            <div className="min-w-0">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-xs font-black uppercase tracking-wide text-indigo-600">{sourceLabel}</p>
                    <span className="rounded-md bg-indigo-50 px-2 py-1 text-xs font-black text-indigo-700">当前学习</span>
                  </div>
                  <h2 className="mt-3 text-2xl font-black tracking-tight text-slate-950">
                    {unitWorkspace.unit.title} · {unitWorkspace.unit.subtitle}
                  </h2>
                  <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">{unitWorkspace.overview.summary}</p>
                </div>
                <Button onClick={onStartLesson} disabled={isStartingLesson}>
                  {isStartingLesson ? <LoaderCircle className="size-4 animate-spin" /> : <BookOpen className="size-4" />}
                  继续学习
                </Button>
              </div>

              {unitWorkspace.overview.objectives.length ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  {unitWorkspace.overview.objectives.slice(0, 3).map((objective) => (
                    <span key={objective} className="rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-bold leading-5 text-slate-700">
                      {objective}
                    </span>
                  ))}
                </div>
              ) : null}

              <div className="mt-5 grid gap-3 sm:grid-cols-[90px_minmax(0,1fr)_56px] sm:items-center">
                <p className="text-sm font-black text-slate-700">学习进度</p>
                <UnitProgressBar value={Math.round(unitWorkspace.mastery_summary.average * 100)} />
                <p className="text-sm font-black text-slate-500">{Math.round(unitWorkspace.mastery_summary.average * 100)}%</p>
              </div>

              <div className="mt-5 grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-4">
                <UnitShortcut icon={<BookOpen className="size-4" />} label="单元导学" onClick={onStartLesson} />
                <UnitShortcut icon={<Languages className="size-4" />} label={`单词表 ${vocabulary?.total ?? '—'}`} onClick={() => onStartVocabulary('new')} />
                <UnitShortcut icon={<GraduationCap className="size-4" />} label="语法要点" onClick={() => handleAction('grammar')} />
                <UnitShortcut icon={<Dumbbell className="size-4" />} label="教材题库" onClick={onStartExercise} />
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-5">
          <div className="flex items-start gap-3">
            <Sparkles className="mt-0.5 size-5 shrink-0 text-indigo-600" />
            <div>
              <p className="text-sm font-black text-indigo-950">推荐下一步</p>
              <h3 className="mt-1 text-lg font-black text-slate-950">{recommendedLabel}</h3>
              <p className="mt-2 text-sm leading-6 text-indigo-800">{recommendedReason}</p>
              <Button className="mt-4 w-full" onClick={() => handleAction(recommendedType)}>
                {recommendedLabel}
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl bg-slate-50 px-4 py-3 text-xs font-bold text-slate-500" aria-label="本单元词汇统计">
        <span className="text-slate-800">本单元共 {vocabulary?.total ?? '—'} 词</span>
        <span>新词 {vocabulary?.new ?? '—'}</span>
        <span>待复习 {vocabulary?.due ?? '—'}</span>
        <span>已掌握 {vocabulary?.mastered ?? '—'}</span>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {visibleSections.map((section) => (
          <WorkspaceSectionCard
            key={section.id}
            section={section}
            isBusy={
              (section.action.type === 'exercise' && isStartingExercise)
              || (section.action.type === 'daily_lesson' && isStartingDailyLesson)
            }
            onAction={(type) => handleAction(type, section)}
          />
        ))}
      </div>
    </section>
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

function UnitShortcut({ icon, label, onClick }: { icon: ReactNode; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-bold text-slate-700 transition-colors hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-500"
    >
      {icon}
      {label}
    </button>
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

function WorkspaceSectionCard({
  section,
  isBusy,
  onAction,
}: {
  section: UnitWorkspaceSection
  isBusy: boolean
  onAction: (type: UnitWorkspaceActionType) => void
}) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-700">
            {sectionIcon(section.id)}
          </div>
          <div className="min-w-0">
            <h3 className="font-black text-slate-950">{section.title}</h3>
            <p className="mt-1 text-xs font-bold text-slate-500">{section.count} 项</p>
          </div>
        </div>
        <Button variant="secondary" onClick={() => onAction(section.action.type)} disabled={isBusy || section.empty}>
          {isBusy ? <LoaderCircle className="size-4 animate-spin" /> : null}
          {section.action.label}
        </Button>
      </div>
      {section.items.length ? (
        <div className="mt-4 grid gap-2">
          {section.items.map((item) => (
            <div key={item.id} className="rounded-lg bg-slate-50 px-3 py-2">
              <div className="flex items-center justify-between gap-3">
                <p className="min-w-0 truncate text-sm font-black text-slate-900">{item.title}</p>
                <span className="shrink-0 text-xs font-bold text-slate-500">{Math.round(item.mastery * 100)}%</span>
              </div>
              <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-600">{item.summary}</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-lg bg-slate-50 px-3 py-6 text-center text-sm font-semibold text-slate-500">
          {section.id === 'practice' ? '使用本单元结构化知识生成检查题。' : '本单元暂无这一类条目。'}
        </div>
      )}
    </article>
  )
}

function sectionIcon(sectionId: string) {
  if (sectionId === 'vocabulary') return <Languages className="size-5" />
  if (sectionId === 'sentence_patterns') return <BookCheck className="size-5" />
  if (sectionId === 'grammar') return <GraduationCap className="size-5" />
  if (sectionId === 'phrases') return <BookOpen className="size-5" />
  if (sectionId === 'practice') return <Dumbbell className="size-5" />
  return <BookOpen className="size-5" />
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

function DailyLessonRuntimeDialog({
  lesson,
  answer,
  isSubmitting,
  dismissedRecommendationIds,
  busyRecommendationId,
  onAnswerChange,
  onSubmit,
  onOpenRecommendation,
  onDismissRecommendation,
  onClose,
}: {
  lesson: DailyLessonRuntime | null
  answer: string
  isSubmitting: boolean
  dismissedRecommendationIds: Set<string>
  busyRecommendationId: string | null
  onAnswerChange: (value: string) => void
  onSubmit: () => void
  onOpenRecommendation: (recommendation: CapabilityRecommendation) => void
  onDismissRecommendation: (recommendation: CapabilityRecommendation) => void
  onClose: () => void
}) {
  const titleId = useId()
  const { containerRef, handleKeyDown } = useFocusTrap<HTMLElement>({
    isActive: Boolean(lesson),
    onEscape: onClose,
    isEscapeEnabled: !isSubmitting,
  })

  if (!lesson) return null
  const prompt = lesson.prompt ?? readPrompt(lesson.initial_payload) ?? '完成这道学习任务。'
  const options = readOptions(lesson.initial_payload)
  const isCompleted = lesson.status === 'completed' || Boolean(lesson.verification_status)
  const recommendations = (lesson.next_capability_recommendations ?? [])
    .filter((item) => !dismissedRecommendationIds.has(item.recommendation_id))
  const statusLabel = isCompleted ? '已完成' : '待作答'
  const canSubmit = Boolean(answer.trim()) && !isSubmitting

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
                      onClick={() => onAnswerChange(option)}
                      aria-pressed={answer === option}
                      className={`rounded-xl border px-4 py-3 text-left text-sm font-bold transition-[background-color,border-color,box-shadow,transform,color] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-200 ${
                        answer === option
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
                value={answer}
                onChange={(event) => onAnswerChange(event.target.value)}
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
                <div className="space-y-3">
                  <p className="text-sm font-black text-slate-950">接下来适合你的学习入口</p>
                  {recommendations.map((recommendation) => (
                    <CapabilityRecommendationCard
                      key={recommendation.recommendation_id}
                      recommendation={recommendation}
                      isBusy={busyRecommendationId === recommendation.recommendation_id}
                      onOpen={onOpenRecommendation}
                      onDismiss={onDismissRecommendation}
                    />
                  ))}
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
            <Button onClick={onSubmit} disabled={!canSubmit} className="w-full sm:w-auto">
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

function ExerciseWorkspace({
  overview,
  isStartingExercise,
  onStartExercise,
  onStartSpelling,
}: {
  overview: KnowledgeBaseOverview
  isStartingExercise: boolean
  onStartExercise: () => void
  onStartSpelling: () => void
}) {
  return (
    <section className="mt-6 space-y-5">
      <ReasonCard
        title={`${overview.current_unit.title} 练习任务`}
        reason="练习会使用本单元知识点生成混合题型，答题结果会写入教材掌握度、错因和下次复习信号。"
        evidence={[
          `当前单元：${overview.current_unit.title} ${overview.current_unit.subtitle}`,
          `知识点数量：${overview.knowledge_points.length}`,
          `推荐依据：${overview.recommendation_reason}`,
        ]}
        outcome="完成后更新知识点状态、词汇复习计划和学习记录。"
        action={(
          <div className="flex flex-wrap gap-2">
            <Button onClick={onStartExercise} disabled={isStartingExercise}>
              {isStartingExercise ? '正在准备…' : '开始教材练习'}
            </Button>
            <Button variant="secondary" onClick={onStartSpelling}>练习本单元拼写</Button>
          </div>
        )}
      />
      <div className="grid gap-3 sm:grid-cols-2">
        {overview.daily_lesson.parts.map((part) => (
          <article key={part.id} className="rounded-2xl border border-slate-200 bg-white p-5">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                <BookCheck className="size-5" />
              </div>
              <div>
                <h3 className="font-black text-slate-950">{part.title}</h3>
                <p className="mt-1 text-xs font-semibold text-slate-500">预计 {part.estimated_minutes} 分钟</p>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
