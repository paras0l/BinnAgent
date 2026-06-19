import { AlertCircle, ChevronLeft, LoaderCircle, Search } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { CurriculumRail } from '@/components/knowledge/CurriculumRail'
import { DailyLessonCard } from '@/components/knowledge/DailyLessonCard'
import { KnowledgeContextPanel } from '@/components/knowledge/KnowledgeContextPanel'
import { KnowledgeList, type KnowledgeFilter } from '@/components/knowledge/KnowledgeList'
import { LessonSessionDialog } from '@/components/knowledge/LessonSessionDialog'
import { UploadTextbookDialog } from '@/components/knowledge/UploadTextbookDialog'
import { useToast } from '@/hooks/useToast'
import { GrammarPage } from '@/pages/GrammarPage'
import type {
  KnowledgeAttemptResult,
  KnowledgeBaseOverview,
  KnowledgeLessonCompleteResult,
  KnowledgeLessonSession,
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

export function KnowledgeBasePage({ learner, onBack, onStartVocabularyPractice }: KnowledgeBasePageProps) {
  const { showToast } = useToast()
  const [overview, setOverview] = useState<KnowledgeBaseOverview | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<KnowledgeFilter>('all')
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [lessonSession, setLessonSession] = useState<KnowledgeLessonSession | null>(null)
  const [isStartingLesson, setIsStartingLesson] = useState(false)
  const [unitVocabulary, setUnitVocabulary] = useState<UnitVocabularySummary | null>(null)
  const [grammarTopic, setGrammarTopic] = useState<string | null>(null)

  const loadOverview = useCallback(async (nodeId?: string | null) => {
    setIsLoading(true)
    setError(null)
    try {
      const query = nodeId ? `?node_id=${encodeURIComponent(nodeId)}` : ''
      const response = await fetch(`/api/learners/${learner.id}/knowledge-base${query}`)
      if (!response.ok) throw new Error('知识库暂时无法加载。')
      const data = await response.json() as KnowledgeBaseOverview
      setOverview(data)
      setSelectedNodeId(data.current_node_id)
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
    await loadOverview()
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
    void loadOverview(nodeId)
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
      await loadOverview(result.next_node_id)
    } else {
      showToast('恭喜，你已经完成本册全部课程！', { variant: 'success', duration: 6000 })
      await loadOverview()
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
          <button type="button" onClick={() => void loadOverview()} className="mt-5 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-bold text-white">重新加载</button>
        </div>
      </div>
    )
  }

  const activeUnitVocabulary = unitVocabulary?.unit_id === overview.current_unit.id ? unitVocabulary : null

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
    <div className="min-h-[calc(100vh-4rem)] bg-white">
      <div className="flex h-12 items-center border-b border-slate-200 px-4 text-sm text-slate-500 sm:px-6">
        <button type="button" onClick={onBack} className="inline-flex items-center gap-1 font-semibold transition-colors hover:text-indigo-600">
          <ChevronLeft className="size-4" />
          学习中心
        </button>
        <span className="mx-2 text-slate-300">/</span>
        <span>每日学习</span>
        <span className="mx-2 text-slate-300">/</span>
        <span className="hidden sm:inline">教材课程 / 初中 / 七年级英语</span>
      </div>
      <div className="knowledge-shell grid min-h-[calc(100vh-7rem)] bg-white">
      <CurriculumRail
        nodes={overview.curriculum}
        currentNodeId={selectedNodeId ?? overview.current_node_id}
        progress={overview.source.progress}
        onSelect={handleSelectNode}
        onManage={() => setIsUploadOpen(true)}
      />

      <main className="min-w-0 px-6 py-8 xl:px-8">
        <div className="mx-auto max-w-4xl">
          <h1 className="text-3xl font-black tracking-tight text-slate-950">七年级英语 · 每日学习</h1>
          <p className="mt-2 text-sm text-slate-500">沿着课本顺序学习，也可以从知识点自由探索。</p>

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
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <button type="button" onClick={() => onStartVocabularyPractice('review', overview.current_unit.id, `七上 · ${overview.current_unit.title}`)} className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm font-black text-indigo-700 transition hover:border-indigo-300">学习本单元词汇</button>
              <button type="button" onClick={() => onStartVocabularyPractice('spelling', overview.current_unit.id, `七上 · ${overview.current_unit.title}`)} className="rounded-xl bg-indigo-600 px-4 py-3 text-sm font-black text-white transition hover:bg-indigo-700">练习本单元拼写</button>
            </div>
          </div>

          <KnowledgeList
            items={visibleKnowledge}
            filter={filter}
            onFilterChange={setFilter}
            onStartGrammar={setGrammarTopic}
          />
        </div>
      </main>

      <KnowledgeContextPanel overview={overview} onUpload={() => setIsUploadOpen(true)} />
      <UploadTextbookDialog open={isUploadOpen} onClose={() => setIsUploadOpen(false)} onUpload={handleUpload} />
      <LessonSessionDialog
        key={lessonSession?.session_id ?? 'closed-lesson'}
        session={lessonSession}
        onClose={() => {
          setLessonSession(null)
          void loadOverview()
        }}
        onAttempt={handleAttempt}
        onComplete={handleCompleteLesson}
      />
      </div>
    </div>
  )
}
