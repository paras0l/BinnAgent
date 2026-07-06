import { AlertCircle, BookCheck, ChevronLeft, FileWarning, LoaderCircle, Search, Send, ShieldCheck, Trash2, UploadCloud, Wrench, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { EvidencePanel } from '@/components/learning/EvidencePanel'
import {
  CapabilityRecommendationCard,
  type CapabilityRecommendation,
} from '@/components/learning/CapabilityRecommendationCard'
import { ReasonCard } from '@/components/learning/ReasonCard'
import { PageShell } from '@/components/layout/PageShell'
import { CurriculumRail } from '@/components/knowledge/CurriculumRail'
import { DailyLessonCard } from '@/components/knowledge/DailyLessonCard'
import { ExerciseSessionDialog } from '@/components/knowledge/ExerciseSessionDialog'
import { KnowledgeContextPanel } from '@/components/knowledge/KnowledgeContextPanel'
import { KnowledgeList, type KnowledgeFilter } from '@/components/knowledge/KnowledgeList'
import { LessonSessionDialog } from '@/components/knowledge/LessonSessionDialog'
import { UploadTextbookDialog } from '@/components/knowledge/UploadTextbookDialog'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { StatusBanner } from '@/components/ui/StatusBanner'
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
  KnowledgeReviewItem,
  KnowledgeUploadResult,
  Learner,
  UnitVocabularySummary,
} from '@/types'
import type { VocabularyPracticeMode } from '@/pages/VocabularyPracticePage'

interface KnowledgeBasePageProps {
  learner: Learner
  onBack: () => void
  onStartVocabularyPractice: (mode: VocabularyPracticeMode, nodeId: string, sourceLabel: string) => void
}

type KnowledgeWorkspace = 'structure' | 'unit' | 'exercises' | 'review'

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
  { id: 'structure', label: '教材结构' },
  { id: 'unit', label: '单元学习' },
  { id: 'exercises', label: '练习任务' },
  { id: 'review', label: '解析校对' },
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
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<KnowledgeFilter>('all')
  const [workspace, setWorkspace] = useState<KnowledgeWorkspace>('unit')
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null)
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null)
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [deleteSourceTarget, setDeleteSourceTarget] = useState<DeleteSourceTarget | null>(null)
  const [isDeletingSource, setIsDeletingSource] = useState(false)
  const [confirmReviewItem, setConfirmReviewItem] = useState<KnowledgeReviewItem | null>(null)
  const [isReviewSaving, setIsReviewSaving] = useState(false)
  const [lessonSession, setLessonSession] = useState<KnowledgeLessonSession | null>(null)
  const [isStartingLesson, setIsStartingLesson] = useState(false)
  const [unitVocabulary, setUnitVocabulary] = useState<UnitVocabularySummary | null>(null)
  const [grammarTopic, setGrammarTopic] = useState<string | null>(null)
  const [exerciseSession, setExerciseSession] = useState<ExerciseSession | null>(null)
  const [isStartingExercise, setIsStartingExercise] = useState(false)
  const [dailyLesson, setDailyLesson] = useState<DailyLessonRuntime | null>(null)
  const [dailyAnswer, setDailyAnswer] = useState('')
  const [isStartingDailyLesson, setIsStartingDailyLesson] = useState(false)
  const [isSubmittingDailyAnswer, setIsSubmittingDailyAnswer] = useState(false)
  const [dismissedDailyRecommendationIds, setDismissedDailyRecommendationIds] = useState<Set<string>>(() => new Set())
  const [busyDailyRecommendationId, setBusyDailyRecommendationId] = useState<string | null>(null)

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

  const visibleKnowledge = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase()
    return (overview?.knowledge_points ?? []).filter((item) => {
      if (filter !== 'all' && item.type !== filter) return false
      if (!normalizedQuery) return true
      return `${item.title} ${item.summary}`.toLocaleLowerCase().includes(normalizedQuery)
    })
  }, [filter, overview?.knowledge_points, query])

  const selectedReviewItem = useMemo(() => {
    const items = overview?.review.items ?? []
    return items.find((item) => item.id === selectedReviewId) ?? items[0] ?? null
  }, [overview?.review.items, selectedReviewId])
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
    setSelectedReviewId(null)
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
        setSelectedReviewId(null)
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

  const handleReviewAction = async (
    item: KnowledgeReviewItem,
    action: 'confirm' | 'update' | 'ignore',
    patch?: { title?: string; summary?: string; source_page?: string; note?: string },
  ) => {
    setIsReviewSaving(true)
    try {
      const response = await fetch(`/api/learners/${learner.id}/knowledge-base/review-items/${item.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, ...patch }),
      })
      if (!response.ok) throw new Error('校对结果保存失败，请重试。')
      showToast(action === 'ignore' ? '已忽略该解析项。' : '已确认解析项并进入教材知识库。', { variant: 'success' })
      setConfirmReviewItem(null)
      await loadOverview(selectedSourceId ?? overview?.source.id, selectedNodeId)
    } catch (reviewError) {
      showToast(reviewError instanceof Error ? reviewError.message : '校对结果保存失败，请重试。', { variant: 'error' })
    } finally {
      setIsReviewSaving(false)
    }
  }

  if (isLoading && !overview) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-white text-sm text-slate-500">
        <LoaderCircle className="mr-2 size-4 animate-spin text-indigo-600" />
        正在打开每日学习...
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
            <button
              type="button"
              onClick={() => setIsUploadOpen(true)}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-indigo-700"
            >
              <UploadCloud className="size-4" />
              上传教材
            </button>
            <button
              type="button"
              onClick={() => void loadOverview(selectedSourceId)}
              className="rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-700 transition hover:bg-slate-50"
            >
              重新加载
            </button>
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
          <button type="button" onClick={onBack} className="inline-flex items-center gap-1 font-semibold transition-colors hover:text-indigo-600">
            <ChevronLeft className="size-4" />
            学习中心
          </button>
          <span className="mx-2 text-slate-300">/</span>
          <span>教材知识库</span>
          <span className="mx-2 text-slate-300">/</span>
          <span className="hidden sm:inline">{overview.current_unit.title} · {overview.current_unit.subtitle}</span>
        </div>
        <div className="knowledge-shell grid min-h-[calc(100vh-7rem)] bg-white">
      <CurriculumRail
        nodes={overview.curriculum}
        currentNodeId={selectedNodeId ?? overview.current_node_id}
        sourceTitle={overview.source.title}
        sources={overview.sources}
        currentSourceId={overview.source.id}
        progress={overview.source.progress}
        canDelete={overview.source.can_delete}
        onSourceChange={handleSelectSource}
        onSelect={handleSelectNode}
        onManage={() => setIsUploadOpen(true)}
        onDelete={handleRequestDeleteCurrentSource}
      />

      <main className="min-w-0 px-6 py-8 xl:px-8">
        <div className="mx-auto max-w-4xl">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-black tracking-tight text-slate-950">英语教材工作台</h1>
              <p className="mt-2 text-sm text-slate-500">教材结构、单元学习、练习任务和解析校对在这里形成闭环。</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-right shadow-sm">
              <p className="text-xs font-bold text-slate-500">待校对</p>
              <p className={`mt-1 text-2xl font-black ${overview.review.pending_count > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>{overview.review.pending_count}</p>
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
                className={`relative shrink-0 px-1 pb-3 text-sm font-bold transition-colors ${
                  workspace === item.id ? 'text-indigo-600' : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                {item.label}
                {item.id === 'review' && overview.review.pending_count > 0 ? (
                  <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">{overview.review.pending_count}</span>
                ) : null}
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
            {overview.review.requires_review ? (
              <StatusBanner title="教材已可学习，部分条目待校对" tone="warning">
                已确认的单元、词汇和知识点可以先学；还有 {overview.review.low_confidence_count} 个低置信词条、{overview.review.warning_count} 个解析提示等待校对，确认后会继续加入练习材料。
              </StatusBanner>
            ) : (
              <StatusBanner title="今日教材学习" tone="info">
                先完成当前单元的小目标；练习结果会用于安排后续复习。
              </StatusBanner>
            )}
          </div>

          {workspace !== 'review' ? (
            <label className="mt-6 flex h-12 items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 shadow-[0_1px_2px_rgba(15,23,42,0.02)] focus-within:border-indigo-400 focus-within:ring-2 focus-within:ring-indigo-100">
              <Search className="size-5 shrink-0 text-slate-400" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="min-w-0 flex-1 bg-transparent text-sm text-slate-800 outline-none placeholder:text-slate-400"
                placeholder="搜索知识点（词汇 / 语法 / 词组 / 句式 / 课文）"
                aria-label="搜索知识点"
              />
              <kbd className="hidden text-xs font-semibold text-slate-400 sm:inline">⌘ K</kbd>
            </label>
          ) : null}

          {workspace === 'structure' ? (
            <StructureWorkspace overview={overview} onSelect={handleSelectNode} />
          ) : null}

          {workspace === 'unit' ? (
            <div className="mt-6">
              <DailyLessonCard
                unit={overview.current_unit}
                lesson={overview.daily_lesson}
                onContinue={() => void handleStartLesson()}
              />
              {isStartingLesson ? <p className="mt-2 flex items-center justify-end gap-2 text-xs font-semibold text-slate-500"><LoaderCircle className="size-3.5 animate-spin" />正在准备课程...</p> : null}
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl bg-slate-50 px-4 py-3 text-xs font-bold text-slate-500" aria-label="本单元词汇统计">
                <span className="text-slate-800">本单元共 {activeUnitVocabulary?.total ?? '—'} 词</span>
                <span>新词 {activeUnitVocabulary?.new ?? '—'}</span>
                <span>待复习 {activeUnitVocabulary?.due ?? '—'}</span>
                <span>已掌握 {activeUnitVocabulary?.mastered ?? '—'}</span>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-4">
                <button type="button" onClick={() => onStartVocabularyPractice('new', overview.current_unit.id, currentSourceLabel)} className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-black text-emerald-700 transition hover:border-emerald-300">认识本单元新词</button>
                <button type="button" onClick={() => onStartVocabularyPractice('spelling', overview.current_unit.id, currentSourceLabel)} className="rounded-xl bg-indigo-600 px-4 py-3 text-sm font-black text-white transition hover:bg-indigo-700">练习本单元拼写</button>
                <button type="button" disabled={isStartingDailyLesson} onClick={() => void handleStartDailyLesson()} className="inline-flex items-center justify-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm font-black text-indigo-700 transition hover:border-indigo-300 disabled:opacity-60">
                  {isStartingDailyLesson ? <LoaderCircle className="size-4 animate-spin" /> : null}
                  AI 每日题
                </button>
                <button type="button" disabled={isStartingExercise} onClick={() => void handleStartExercise()} className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-black text-white transition hover:bg-emerald-700 disabled:opacity-60">
                  {isStartingExercise ? <LoaderCircle className="size-4 animate-spin" /> : null}
                  教材练习题
                </button>
              </div>
              <KnowledgeList
                items={visibleKnowledge}
                filter={filter}
                onFilterChange={setFilter}
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

          {workspace === 'review' ? (
            <ReviewWorkspace
              key={selectedReviewItem?.id ?? 'empty-review'}
              items={overview.review.items}
              selectedItem={selectedReviewItem}
              onSelect={(item) => setSelectedReviewId(item.id)}
              onConfirm={(item) => setConfirmReviewItem(item)}
              onUpdate={(item, patch) => void handleReviewAction(item, 'update', patch)}
              onIgnore={(item) => void handleReviewAction(item, 'ignore')}
              isSaving={isReviewSaving}
            />
          ) : null}
        </div>
      </main>

      <KnowledgeContextPanel overview={overview} selectedReviewItem={selectedReviewItem} onUpload={() => setIsUploadOpen(true)} />
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
      <ConfirmDialog
        open={Boolean(confirmReviewItem)}
        title="确认这个解析词条？"
        description={confirmReviewItem ? `确认后「${confirmReviewItem.title}」会从低置信队列进入正式教材知识库，并可用于单元学习、练习和词汇沉淀。` : ''}
        confirmLabel="确认并发布"
        isBusy={isReviewSaving}
        onCancel={() => setConfirmReviewItem(null)}
        onConfirm={() => {
          if (confirmReviewItem) void handleReviewAction(confirmReviewItem, 'confirm')
        }}
      >
        {confirmReviewItem ? <EvidencePanel items={confirmReviewItem.evidence} /> : null}
      </ConfirmDialog>
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

function FailedSourceSummary({ source, onDelete }: { source: FailedKnowledgeSourceDetail; onDelete?: () => void }) {
  const reasons = normalizeBlockingReasons(source.blocking_reasons ?? [])
  const summary = source.parser_report_summary ?? {}
  const metrics = [
    typeof summary.page_count === 'number' ? `页数 ${summary.page_count}` : null,
    typeof summary.text_char_count === 'number' ? `可读取文字 ${summary.text_char_count} 字` : null,
    typeof summary.unit_count === 'number' ? `单元 ${summary.unit_count}` : null,
    typeof summary.rag_chunk_count === 'number' ? `素材片段 ${summary.rag_chunk_count}` : null,
  ].filter(Boolean)

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
      {metrics.length ? <p className="mt-3 text-xs font-bold text-amber-700">{metrics.join(' · ')}</p> : null}
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
  const warnings = status.warnings ?? []
  const quality = status.quality_summary ?? status.parser_report_summary ?? {}
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
                <div className="h-full rounded-full bg-indigo-600 transition-all" style={{ width: `${progress}%` }} />
              </div>
              <p className="mt-2 text-xs font-bold text-indigo-700">{stageLabel(status.stage)} · {progress}%</p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs font-bold text-indigo-800">
                {status.selected_engine ? <span className="rounded-full bg-white/70 px-2 py-1">engine {status.selected_engine}</span> : null}
                {status.attempted_engines?.length ? <span className="rounded-full bg-white/70 px-2 py-1">attempted {status.attempted_engines.join(', ')}</span> : null}
                {status.fallback_used ? <span className="rounded-full bg-white/70 px-2 py-1">fallback used</span> : null}
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-indigo-800 sm:grid-cols-4">
                {typeof quality.text_char_count === 'number' ? <MetricChip label="文字" value={`${quality.text_char_count}`} /> : null}
                {typeof quality.text_coverage_score === 'number' ? <MetricChip label="覆盖" value={`${Math.round(quality.text_coverage_score * 100)}%`} /> : null}
                {typeof quality.empty_page_ratio === 'number' ? <MetricChip label="空页" value={`${Math.round(quality.empty_page_ratio * 100)}%`} /> : null}
                {typeof quality.block_count === 'number' ? <MetricChip label="块" value={`${quality.block_count}`} /> : null}
              </div>
            </>
          ) : null}
          {isFailed && reasons.length ? (
            <ul className="mt-3 space-y-1 text-sm leading-6 text-red-700">
              {reasons.map((reason) => <li key={reason}>- {reason}</li>)}
            </ul>
          ) : null}
          {warnings.length ? (
            <ul className={`mt-3 space-y-1 text-sm leading-6 ${isFailed ? 'text-red-700' : 'text-indigo-700'}`}>
              {warnings.map((warning) => <li key={warning}>- {warning}</li>)}
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

function MetricChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="rounded-lg bg-white/70 px-2 py-1">
      {label} {value}
    </span>
  )
}

function stageLabel(stage: string) {
  const labels: Record<string, string> = {
    queued: '等待开始',
    running: '正在解析',
    parsing_document: '解析文档',
    normalizing_artifact: '标准化解析结果',
    extracting_textbook_structure: '提取教材结构',
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
  if (!lesson) return null
  const prompt = lesson.prompt ?? readPrompt(lesson.initial_payload) ?? '完成这道学习任务。'
  const options = readOptions(lesson.initial_payload)
  const isCompleted = lesson.status === 'completed' || Boolean(lesson.verification_status)
  const recommendations = (lesson.next_capability_recommendations ?? [])
    .filter((item) => !dismissedRecommendationIds.has(item.recommendation_id))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4 py-6">
      <section className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded-2xl bg-white shadow-2xl">
        <header className="flex items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div>
            <p className="text-xs font-black uppercase tracking-wide text-indigo-600">Daily Lesson</p>
            <h2 className="mt-1 text-lg font-black text-slate-950">{lesson.status}</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex size-9 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
            aria-label="关闭 AI 每日题"
          >
            <X className="size-4" />
          </button>
        </header>

        <div className="space-y-4 px-5 py-5">
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
            <p className="whitespace-pre-wrap text-sm font-bold leading-6 text-slate-900">{prompt}</p>
            {lesson.checkpoint_id ? (
              <p className="mt-2 break-all font-mono text-xs text-slate-500">
                checkpoint {lesson.checkpoint_status ?? 'waiting_user'} · {lesson.checkpoint_id}
              </p>
            ) : null}
          </div>

          {!isCompleted ? (
            <div className="space-y-3">
              {options.length ? (
                <div className="grid gap-2 sm:grid-cols-2">
                  {options.map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => onAnswerChange(option)}
                      className={`rounded-xl border px-4 py-3 text-left text-sm font-bold transition ${
                        answer === option
                          ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                          : 'border-slate-200 text-slate-700 hover:border-indigo-200'
                      }`}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              ) : null}
              <textarea
                value={answer}
                onChange={(event) => onAnswerChange(event.target.value)}
                className="min-h-32 w-full resize-y rounded-xl border border-slate-200 px-4 py-3 text-sm leading-6 text-slate-900 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
                placeholder="输入你的答案"
              />
              <Button onClick={onSubmit} disabled={isSubmitting} className="w-full">
                {isSubmitting ? <LoaderCircle className="size-4 animate-spin" /> : <Send className="size-4" />}
                提交答案
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              <StatusBanner tone={lesson.verification_status === 'passed' ? 'success' : 'info'} title="AI 每日题结果">
                Verification: {lesson.verification_status ?? 'completed'}
              </StatusBanner>
              <RuntimeJson title="feedback" value={lesson.feedback} />
              <RuntimeJson title="grading_result" value={lesson.grading_result} />
              <RuntimeJson title="mastery_update" value={lesson.mastery_update} />
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
      </section>
    </div>
  )
}

function RuntimeJson({ title, value }: { title: string; value: unknown }) {
  if (value === undefined || value === null) return null
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <p className="text-xs font-black uppercase text-slate-500">{title}</p>
      <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap break-words text-xs leading-5 text-slate-700">
        {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
      </pre>
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

function StructureWorkspace({ overview, onSelect }: { overview: KnowledgeBaseOverview; onSelect: (nodeId: string) => void }) {
  return (
    <section className="mt-6 space-y-5">
      <div className="grid gap-3 sm:grid-cols-4">
        <MetricCard label="单元" value={overview.source.unit_count} />
        <MetricCard label="知识点" value={overview.source.knowledge_count} />
        <MetricCard label="素材片段" value={overview.parser_evidence.rag_chunk_count} />
        <MetricCard label="待校对" value={overview.review.pending_count} tone={overview.review.pending_count > 0 ? 'warning' : 'success'} />
      </div>
      <ReasonCard
        title="教材结构如何进入学习闭环"
        reason="单元目录决定今日学习顺序；知识点和词汇会进入课程、练习、复习和记忆事件。解析校对完成后，低置信词条才会参与正式学习。"
        evidence={[
          `教材状态：${overview.source.status}`,
          `教材规则：${overview.parser_evidence.parser_profile ?? '未记录'}`,
          `教材版本：${overview.parser_evidence.book_manifest_id ?? '未记录'}`,
        ]}
      />
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="grid grid-cols-[70px_minmax(0,1fr)_110px_110px] border-b border-slate-200 bg-slate-50 px-4 py-3 text-xs font-bold text-slate-500">
          <span>序号</span>
          <span>单元</span>
          <span>预计时间</span>
          <span>状态</span>
        </div>
        {overview.curriculum.map((node) => (
          <button
            key={node.id}
            type="button"
            onClick={() => onSelect(node.id)}
            className="grid w-full grid-cols-[70px_minmax(0,1fr)_110px_110px] items-center border-b border-slate-100 px-4 py-3 text-left text-sm transition hover:bg-slate-50 last:border-b-0"
          >
            <span className="font-bold text-slate-400">{node.ordinal}</span>
            <span className="min-w-0">
              <span className="block truncate font-extrabold text-slate-900">{node.title}</span>
              <span className="block truncate text-xs text-slate-500">{node.subtitle}</span>
            </span>
            <span className="text-slate-600">{node.estimated_minutes ?? 20} 分钟</span>
            <span className="font-bold text-indigo-600">{node.status === 'completed' ? '已完成' : node.status === 'in_progress' ? '当前' : '可学习'}</span>
          </button>
        ))}
      </div>
    </section>
  )
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
              {isStartingExercise ? '正在准备...' : '开始教材练习'}
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

function ReviewWorkspace({
  items,
  selectedItem,
  onSelect,
  onConfirm,
  onUpdate,
  onIgnore,
  isSaving,
}: {
  items: KnowledgeReviewItem[]
  selectedItem: KnowledgeReviewItem | null
  onSelect: (item: KnowledgeReviewItem) => void
  onConfirm: (item: KnowledgeReviewItem) => void
  onUpdate: (item: KnowledgeReviewItem, patch: { title: string; summary: string; source_page: string; note: string }) => void
  onIgnore: (item: KnowledgeReviewItem) => void
  isSaving: boolean
}) {
  const [draft, setDraft] = useState(() => (
    selectedItem
      ? {
      title: selectedItem.title,
      summary: selectedItem.summary,
      source_page: selectedItem.source_page,
      note: '',
        }
      : { title: '', summary: '', source_page: '', note: '' }
  ))

  if (items.length === 0) {
    return (
      <section className="mt-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-8 text-center">
        <ShieldCheck className="mx-auto size-10 text-emerald-600" />
        <h2 className="mt-3 text-xl font-black text-slate-950">解析校对已完成</h2>
        <p className="mt-2 text-sm text-slate-600">当前单元没有低置信词条或 parser warning 队列。</p>
      </section>
    )
  }

  return (
    <section className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(320px,0.75fr)]">
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="text-lg font-black text-slate-950">低置信词条队列</h2>
          <p className="mt-1 text-sm text-slate-500">逐条查看原文、提示、页码和来源信息，再决定确认、修改或忽略。</p>
        </div>
        <div className="divide-y divide-slate-100">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelect(item)}
              className={`grid w-full grid-cols-[minmax(0,1fr)_90px] gap-3 px-5 py-4 text-left transition ${
                selectedItem?.id === item.id ? 'bg-indigo-50' : 'hover:bg-slate-50'
              }`}
            >
              <span className="min-w-0">
                <span className="flex items-center gap-2">
                  <span className="truncate font-black text-slate-900">{item.title}</span>
                  {item.warnings.length > 0 ? <FileWarning className="size-4 shrink-0 text-amber-600" /> : null}
                </span>
                <span className="mt-1 block truncate text-xs text-slate-500">{item.raw_line ?? item.summary}</span>
              </span>
              <span className={`text-right text-sm font-black ${(item.confidence ?? 1) < 0.75 ? 'text-amber-600' : 'text-slate-500'}`}>
                {item.confidence == null ? '—' : `${Math.round(item.confidence * 100)}%`}
              </span>
            </button>
          ))}
        </div>
      </div>

      {selectedItem ? (
        <article className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-black text-slate-950">校对工作区</h2>
              <p className="mt-1 text-sm text-slate-500">确认前可修改标题、说明和来源页码。</p>
            </div>
            <Wrench className="size-5 text-indigo-600" />
          </div>

          <div className="mt-5 space-y-4">
            <label className="block">
              <span className="text-xs font-bold text-slate-500">词条</span>
              <input value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-900 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100" />
            </label>
            <label className="block">
              <span className="text-xs font-bold text-slate-500">说明</span>
              <textarea value={draft.summary} onChange={(event) => setDraft({ ...draft, summary: event.target.value })} rows={4} className="mt-1 w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm leading-6 text-slate-800 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100" />
            </label>
            <label className="block">
              <span className="text-xs font-bold text-slate-500">来源页码</span>
              <input value={draft.source_page} onChange={(event) => setDraft({ ...draft, source_page: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100" />
            </label>
            <label className="block">
              <span className="text-xs font-bold text-slate-500">校对备注</span>
              <input value={draft.note} onChange={(event) => setDraft({ ...draft, note: event.target.value })} placeholder="例如：按词表页码修正" className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100" />
            </label>
          </div>

          <div className="mt-5 space-y-3">
            <EvidencePanel title="原始证据" items={selectedItem.evidence} />
            <EvidencePanel title="解析提示" items={selectedItem.warnings} emptyText="无提示" />
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <Button onClick={() => onConfirm(selectedItem)} disabled={isSaving}>确认原词条</Button>
            <Button variant="secondary" onClick={() => onUpdate(selectedItem, draft)} disabled={isSaving}>保存修改并发布</Button>
            <Button variant="danger" onClick={() => onIgnore(selectedItem)} disabled={isSaving}>忽略</Button>
          </div>
        </article>
      ) : null}
    </section>
  )
}

function MetricCard({ label, value, tone = 'default' }: { label: string; value: number | string; tone?: 'default' | 'warning' | 'success' }) {
  const toneClass = tone === 'warning' ? 'text-amber-600' : tone === 'success' ? 'text-emerald-600' : 'text-slate-950'
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5">
      <p className="text-xs font-bold text-slate-500">{label}</p>
      <p className={`mt-2 text-2xl font-black ${toneClass}`}>{value}</p>
    </article>
  )
}
