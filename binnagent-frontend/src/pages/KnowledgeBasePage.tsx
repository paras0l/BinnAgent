import { AlertCircle, BookCheck, ChevronLeft, FileWarning, LoaderCircle, Search, ShieldCheck, Wrench } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { EvidencePanel } from '@/components/learning/EvidencePanel'
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
import type {
  ExerciseAnswerResult,
  ExerciseSession,
  KnowledgeAttemptResult,
  KnowledgeBaseOverview,
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

const WORKSPACES: Array<{ id: KnowledgeWorkspace; label: string }> = [
  { id: 'structure', label: '教材结构' },
  { id: 'unit', label: '单元学习' },
  { id: 'exercises', label: '练习任务' },
  { id: 'review', label: '解析校对' },
]

export function KnowledgeBasePage({ learner, onBack, onStartVocabularyPractice }: KnowledgeBasePageProps) {
  const { showToast } = useToast()
  const [overview, setOverview] = useState<KnowledgeBaseOverview | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<KnowledgeFilter>('all')
  const [workspace, setWorkspace] = useState<KnowledgeWorkspace>('unit')
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null)
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null)
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [confirmReviewItem, setConfirmReviewItem] = useState<KnowledgeReviewItem | null>(null)
  const [isReviewSaving, setIsReviewSaving] = useState(false)
  const [lessonSession, setLessonSession] = useState<KnowledgeLessonSession | null>(null)
  const [isStartingLesson, setIsStartingLesson] = useState(false)
  const [unitVocabulary, setUnitVocabulary] = useState<UnitVocabularySummary | null>(null)
  const [grammarTopic, setGrammarTopic] = useState<string | null>(null)
  const [exerciseSession, setExerciseSession] = useState<ExerciseSession | null>(null)
  const [isStartingExercise, setIsStartingExercise] = useState(false)

  const loadOverview = useCallback(async (sourceId?: string | null, nodeId?: string | null) => {
    setIsLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (sourceId) params.set('source_id', sourceId)
      if (nodeId) params.set('node_id', nodeId)
      const query = params.toString() ? `?${params.toString()}` : ''
      const response = await fetch(`/api/learners/${learner.id}/knowledge-base${query}`)
      if (!response.ok) throw new Error('知识库暂时无法加载。')
      const data = await response.json() as KnowledgeBaseOverview
      setOverview(data)
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
    const ingestResult = await ingestResponse.json() as { message: string }
    showToast(ingestResult.message, { variant: 'success', duration: 6000 })
    setSelectedSourceId(result.source_id)
    await loadOverview(result.source_id)
  }

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

  const handleExerciseAnswer = async (questionId: string, answer: string, meta?: { hintUsed?: number; attemptIndex?: number }) => {
    const response = await fetch(
      `/api/learners/${learner.id}/knowledge-base/exercises/${questionId}/attempts`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          answer,
          hint_used: meta?.hintUsed ?? 0,
          attempt_index: meta?.attemptIndex ?? 0,
        }),
      },
    )
    if (!response.ok) throw new Error('答案提交失败，请重试。')
    return await response.json() as ExerciseAnswerResult
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

  if (!overview || error) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-white p-6">
        <div className="max-w-md text-center">
          <AlertCircle className="mx-auto size-8 text-amber-500" />
          <h1 className="mt-4 text-xl font-extrabold text-slate-950">知识库暂时不可用</h1>
          <p className="mt-2 text-sm text-slate-500">{error}</p>
          <button type="button" onClick={() => void loadOverview(selectedSourceId)} className="mt-5 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-bold text-white">重新加载</button>
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
        onSourceChange={handleSelectSource}
        onSelect={handleSelectNode}
        onManage={() => setIsUploadOpen(true)}
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
            {overview.review.requires_review ? (
              <StatusBanner title="教材解析需要人工校对" tone="warning">
                {overview.review.low_confidence_count} 个低置信词条、{overview.review.warning_count} 个 warning 正在等待确认，确认后才会进入正式教材学习材料。
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
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <button type="button" onClick={() => onStartVocabularyPractice('new', overview.current_unit.id, currentSourceLabel)} className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-black text-emerald-700 transition hover:border-emerald-300">认识本单元新词</button>
                <button type="button" onClick={() => onStartVocabularyPractice('spelling', overview.current_unit.id, currentSourceLabel)} className="rounded-xl bg-indigo-600 px-4 py-3 text-sm font-black text-white transition hover:bg-indigo-700">练习本单元拼写</button>
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
      <ExerciseSessionDialog
        key={exerciseSession?.curriculum_node_id ?? 'closed-exercise'}
        session={exerciseSession}
        onClose={() => setExerciseSession(null)}
        onSubmit={handleExerciseAnswer}
      />
        </div>
      </div>
    </PageShell>
  )
}

function StructureWorkspace({ overview, onSelect }: { overview: KnowledgeBaseOverview; onSelect: (nodeId: string) => void }) {
  return (
    <section className="mt-6 space-y-5">
      <div className="grid gap-3 sm:grid-cols-4">
        <MetricCard label="单元" value={overview.source.unit_count} />
        <MetricCard label="知识点" value={overview.source.knowledge_count} />
        <MetricCard label="RAG chunks" value={overview.parser_evidence.rag_chunk_count} />
        <MetricCard label="待校对" value={overview.review.pending_count} tone={overview.review.pending_count > 0 ? 'warning' : 'success'} />
      </div>
      <ReasonCard
        title="教材结构如何进入学习闭环"
        reason="单元目录决定今日学习顺序；知识点和词汇会进入课程、练习、复习和记忆事件。解析校对完成后，低置信词条才会参与正式学习。"
        evidence={[
          `教材状态：${overview.source.status}`,
          `Parser profile：${overview.parser_evidence.parser_profile ?? '未记录'}`,
          `Manifest：${overview.parser_evidence.book_manifest_id ?? '未记录'}`,
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
        outcome="完成后更新知识点状态、词汇复习计划和 Memory 事件。"
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
          <p className="mt-1 text-sm text-slate-500">逐条查看 raw line、warnings、页码和 parser evidence，再决定确认、修改或忽略。</p>
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
            <EvidencePanel title="Warnings" items={selectedItem.warnings} emptyText="无 warning" />
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
