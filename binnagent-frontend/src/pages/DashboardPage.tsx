import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Target,
  Trash2,
  X,
} from 'lucide-react'
import { VocabReviewCard } from '@/components/dashboard/VocabReviewCard'
import { ErrorPatternList } from '@/components/dashboard/ErrorPatternList'
import { LearningGoalProgress } from '@/components/dashboard/LearningGoalProgress'
import type { DashboardSummary, Learner, VocabularyListItem } from '@/types'
import { useToast } from '@/hooks/useToast'
import type { VocabularyPracticeMode } from '@/pages/VocabularyPracticePage'

interface DashboardPageProps {
  learner: Learner
  onOpenDailyLearning: () => void
  onStartVocabularyPractice: (mode: VocabularyPracticeMode) => void
}

export function DashboardPage({ learner, onOpenDailyLearning, onStartVocabularyPractice }: DashboardPageProps) {
  const { showToast } = useToast()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [currentVocabIndex, setCurrentVocabIndex] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [isReviewing, setIsReviewing] = useState(false)
  const [isAddingWord, setIsAddingWord] = useState(false)
  const [isVocabListOpen, setIsVocabListOpen] = useState(false)
  const [isLoadingVocabulary, setIsLoadingVocabulary] = useState(false)
  const [deletingWordId, setDeletingWordId] = useState<string | null>(null)
  const [vocabularyItems, setVocabularyItems] = useState<VocabularyListItem[]>([])
  const [vocabQuery, setVocabQuery] = useState('')
  const [newWord, setNewWord] = useState('')
  const [newPhonetic, setNewPhonetic] = useState('')
  const [newMeaning, setNewMeaning] = useState('')
  const [activeWorkspace, setActiveWorkspace] = useState<'home' | 'vocabulary'>('home')

  const loadDashboard = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`/api/learners/${learner.id}/dashboard`)
      if (!response.ok) throw new Error('Failed to load dashboard')
      const data: DashboardSummary = await response.json()
      setSummary(data)
      setCurrentVocabIndex(0)
    } catch (err) {
      console.error('Dashboard error:', err)
      showToast('学习中心暂时无法加载，请稍后重试。', { variant: 'error' })
    } finally {
      setIsLoading(false)
    }
  }, [learner.id, showToast])

  const loadVocabularyList = useCallback(async () => {
    setIsLoadingVocabulary(true)
    try {
      const response = await fetch(`/api/learners/${learner.id}/vocabulary`)
      if (!response.ok) throw new Error('Failed to load vocabulary')
      const data: VocabularyListItem[] = await response.json()
      setVocabularyItems(data)
    } catch (err) {
      console.error('Vocabulary list error:', err)
      showToast('词汇列表暂时无法加载，请稍后重试。', { variant: 'error' })
    } finally {
      setIsLoadingVocabulary(false)
    }
  }, [learner.id, showToast])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadDashboard(), 0)
    return () => window.clearTimeout(timer)
  }, [loadDashboard])

  const reviewItems = summary?.review_items ?? []
  const currentVocab = reviewItems[currentVocabIndex]
  const filteredVocabulary = useMemo(() => {
    const query = vocabQuery.trim().toLowerCase()
    if (!query) return vocabularyItems
    return vocabularyItems.filter((item) => {
      return (
        item.word.toLowerCase().includes(query) ||
        item.meaning?.toLowerCase().includes(query) ||
        item.phonetic?.toLowerCase().includes(query)
      )
    })
  }, [vocabQuery, vocabularyItems])

  const handleOpenVocabularyList = () => {
    setIsVocabListOpen(true)
    void loadVocabularyList()
  }

  const handleRate = async (rating: 1 | 2 | 3 | 4) => {
    if (!currentVocab) return
    setIsReviewing(true)
    try {
      const response = await fetch(`/api/learners/${learner.id}/vocabulary/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          word_id: currentVocab.id,
          correct: rating >= 3,
        }),
      })
      if (!response.ok) throw new Error('Review failed')
      await loadDashboard()
      if (isVocabListOpen) await loadVocabularyList()
    } catch (err) {
      console.error('Vocabulary review error:', err)
      showToast('词卡评分失败，请稍后重试。', { variant: 'error' })
    } finally {
      setIsReviewing(false)
    }
  }

  const handleAddWord = async () => {
    const word = newWord.trim()
    const meaning = newMeaning.trim()
    if (!word) {
      showToast('请输入要加入词汇本的单词。', { variant: 'warning' })
      return
    }

    setIsAddingWord(true)
    try {
      const response = await fetch(`/api/learners/${learner.id}/vocabulary/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          word,
          phonetic: newPhonetic.trim() || null,
          meanings: meaning ? [meaning] : null,
        }),
      })
      if (!response.ok) throw new Error('Add word failed')
      setNewWord('')
      setNewPhonetic('')
      setNewMeaning('')
      await loadDashboard()
      if (isVocabListOpen) await loadVocabularyList()
      showToast(`已将「${word}」加入词汇本。`, { variant: 'success' })
    } catch (err) {
      console.error('Add vocabulary error:', err)
      showToast('加入词汇本失败，请稍后重试。', { variant: 'error' })
    } finally {
      setIsAddingWord(false)
    }
  }

  const handleDeleteWord = async (item: VocabularyListItem) => {
    const shouldDelete = window.confirm(`确定从词汇本删除 "${item.word}" 吗？`)
    if (!shouldDelete) return

    setDeletingWordId(item.id)
    try {
      const response = await fetch(`/api/learners/${learner.id}/vocabulary/${item.id}`, {
        method: 'DELETE',
      })
      if (!response.ok) throw new Error('Delete word failed')
      setVocabularyItems((items) => items.filter((existing) => existing.id !== item.id))
      await loadDashboard()
      if (isVocabListOpen) await loadVocabularyList()
      showToast(`已从词汇本删除「${item.word}」。`, { variant: 'success' })
    } catch (err) {
      console.error('Delete vocabulary error:', err)
      showToast('删除词汇失败，请稍后重试。', { variant: 'error' })
    } finally {
      setDeletingWordId(null)
    }
  }

  if (isLoading && !summary) {
    return (
      <div className="container mx-auto flex min-h-[calc(100vh-4rem)] items-center justify-center p-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <RefreshCw className="h-4 w-4 animate-spin" />
          正在加载学习记录...
        </div>
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="container mx-auto p-6">
        <div className="rounded-xl border bg-card p-8 text-center">
          <p className="text-sm text-muted-foreground">学习中心暂时不可用。</p>
          <button
            onClick={() => void loadDashboard()}
            className="mt-4 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            重新加载
          </button>
        </div>
      </div>
    )
  }

  if (activeWorkspace === 'home') {
    return (
      <LearningCenterHome
        learnerName={learner.nickname}
        summary={summary}
        onOpenDailyLearning={onOpenDailyLearning}
        onOpenVocabulary={() => setActiveWorkspace('vocabulary')}
        onStartVocabularyPractice={onStartVocabularyPractice}
      />
    )
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#f6f7f9] px-4 py-7 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1100px] space-y-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <button
              type="button"
              onClick={() => setActiveWorkspace('home')}
              className="mb-4 inline-flex items-center gap-1.5 text-sm font-bold text-slate-500 transition-colors hover:text-indigo-600"
            >
              <ArrowLeft className="size-4" />
              返回学习中心
            </button>
            <h1 className="text-3xl font-black tracking-tight text-slate-950">背单词</h1>
            <p className="mt-2 text-sm text-slate-500">按记忆曲线安排新词与复习，把难词逐个攻下来。</p>
          </div>
          <button
            type="button"
            onClick={handleOpenVocabularyList}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 shadow-sm transition hover:border-indigo-200 hover:text-indigo-600"
          >
            <BookOpen className="size-4" />
            管理词汇本
          </button>
        </div>

        <section className="grid gap-3 sm:grid-cols-2">
          <button type="button" onClick={() => onStartVocabularyPractice('review')} className="rounded-xl bg-indigo-600 px-5 py-4 text-left text-white shadow-lg shadow-indigo-100 transition hover:bg-indigo-700"><span className="block text-base font-black">开始沉浸式复习</span><span className="mt-1 block text-xs text-indigo-100">听发音、回忆词义，按掌握程度安排复习</span></button>
          <button type="button" onClick={() => onStartVocabularyPractice('spelling')} className="rounded-xl border border-indigo-200 bg-indigo-50 px-5 py-4 text-left text-indigo-800 transition hover:border-indigo-300"><span className="block text-base font-black">拼写练习</span><span className="mt-1 block text-xs text-indigo-600">听音主动拼写，获得字母级反馈</span></button>
        </section>

      {isVocabListOpen && (
        <section className="rounded-[13px] border border-slate-200 bg-white p-5 shadow-[0_4px_14px_rgba(15,23,42,0.05)]">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-base font-semibold text-foreground">我的词汇本</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                共 {vocabularyItems.length} 个词，按最近复习或更新时间排序
              </p>
            </div>
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  value={vocabQuery}
                  onChange={(event) => setVocabQuery(event.target.value)}
                  className="w-full rounded-lg border bg-background py-2 pl-9 pr-3 text-sm outline-none transition-colors focus:border-primary md:w-64"
                  placeholder="搜索单词、音标或释义"
                />
              </div>
              <button
                type="button"
                onClick={() => setIsVocabListOpen(false)}
                className="inline-flex size-9 items-center justify-center rounded-lg border text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                aria-label="关闭词汇列表"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="mt-4">
            {isLoadingVocabulary ? (
              <div className="flex items-center justify-center rounded-lg border border-dashed p-8 text-sm text-muted-foreground">
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                正在加载词汇...
              </div>
            ) : vocabularyItems.length === 0 ? (
              <div className="rounded-lg border border-dashed p-8 text-center">
                <BookOpen className="mx-auto h-6 w-6 text-muted-foreground" />
                <p className="mt-3 text-sm font-medium text-foreground">还没有词汇</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  可以去探索页使用 AI 词汇讲解，或在学习中心手动添加。
                </p>
              </div>
            ) : filteredVocabulary.length === 0 ? (
              <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                没有匹配的词汇。
              </div>
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                {filteredVocabulary.map((item) => (
                  <VocabularyListRow
                    key={item.id}
                    item={item}
                    isDeleting={deletingWordId === item.id}
                    onDelete={handleDeleteWord}
                  />
                ))}
              </div>
            )}
          </div>
        </section>
      )}

      <section className="rounded-[13px] border border-slate-200 bg-white p-5 shadow-[0_4px_14px_rgba(15,23,42,0.05)]">
        <div className="mb-3 flex items-center gap-2">
          <Plus className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-semibold text-foreground">加入词汇本</h2>
        </div>
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,2fr)_auto]">
          <input
            value={newWord}
            onChange={(event) => setNewWord(event.target.value)}
            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
            placeholder="significant"
            maxLength={255}
          />
          <input
            value={newPhonetic}
            onChange={(event) => setNewPhonetic(event.target.value)}
            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
            placeholder="可选音标，例如：/sɪɡˈnɪfɪkənt/"
            maxLength={255}
          />
          <input
            value={newMeaning}
            onChange={(event) => setNewMeaning(event.target.value)}
            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
            placeholder="可选释义，例如：重要的，显著的"
            maxLength={255}
          />
          <button
            onClick={() => void handleAddWord()}
            disabled={isAddingWord}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Plus className="h-4 w-4" />
            加入
          </button>
        </div>
      </section>

      {currentVocab ? (
        <div className={isReviewing ? 'pointer-events-none opacity-70' : ''}>
          <VocabReviewCard
            key={currentVocab.id}
            word={currentVocab.word}
            phonetic={currentVocab.phonetic}
            definition={currentVocab.definition}
            example={currentVocab.example}
            currentIndex={currentVocabIndex}
            totalCount={reviewItems.length}
            onRate={handleRate}
          />
        </div>
      ) : (
        <div className="flex flex-col items-center rounded-xl border bg-card p-8 text-center">
          <div className="mb-3 flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <BookOpen className="h-5 w-5" />
          </div>
          <h2 className="text-lg font-semibold text-foreground">暂无待复习词卡</h2>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">
            当你在对话或课程里沉淀新词后，系统会按复习计划把词卡放到这里。
          </p>
        </div>
      )}

      <ErrorPatternList patterns={summary.error_patterns} />

      <LearningGoalProgress
        dailyGoal={summary.today_goal}
        weeklyGoal={summary.weekly_goal}
      />
      </div>
    </div>
  )
}

function LearningCenterHome({
  learnerName,
  summary,
  onOpenDailyLearning,
  onOpenVocabulary,
  onStartVocabularyPractice,
}: {
  learnerName: string
  summary: DashboardSummary
  onOpenDailyLearning: () => void
  onOpenVocabulary: () => void
  onStartVocabularyPractice: (mode: VocabularyPracticeMode) => void
}) {
  const todayPercent = toPercent(summary.today_goal.completed, summary.today_goal.total)
  const weeklyPercent = toPercent(summary.weekly_goal.completed, summary.weekly_goal.total)
  const dueCount = summary.stats.today_reviews
  const completedReviews = summary.stats.today_completed_reviews
  const heatmapValues = summary.daily_activity.length === 14
    ? summary.daily_activity.map((item) => item.count)
    : Array.from({ length: 14 }, () => 0)
  const maxLearningAmount = Math.max(...heatmapValues, 1)

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#f6f7f9] px-4 py-7 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1100px]">
        <header>
          <h1 className="text-3xl font-black tracking-tight text-slate-950 sm:text-[34px]">学习中心</h1>
          <p className="mt-2 text-sm text-slate-500">
            {learnerName}，今天也从一小步开始，把知识真正学会。
          </p>
        </header>

        <section className="mt-5 grid gap-4 md:grid-cols-[repeat(3,minmax(0,314px))] md:justify-between" aria-label="学习数据">
          <DataPanel title="今日进度" icon={CheckCircle2}>
            <div className="mt-7 flex items-end gap-2">
              <strong className="text-4xl font-black leading-none text-slate-950">
                {summary.today_goal.completed}
              </strong>
              <span className="pb-0.5 text-xl font-bold text-slate-400">/ {summary.today_goal.total} 项</span>
            </div>
            <p className="mt-3 text-sm text-slate-500">{summary.today_goal.label}</p>
            <ProgressBar value={todayPercent} className="mt-4" />
            <p className="mt-3 text-xs font-semibold text-slate-500">
              {todayPercent >= 100 ? '今日目标已完成' : `还差 ${Math.max(summary.today_goal.total - summary.today_goal.completed, 0)} 项完成今日目标`}
            </p>
          </DataPanel>

          <DataPanel title="学习日历" icon={CalendarDays}>
            <div className="mt-4 flex items-baseline gap-2 text-slate-600">
              <span className="text-sm">连续</span>
              <strong className="text-3xl font-black text-slate-950">{summary.stats.streak_days}</strong>
              <span className="text-sm">天</span>
            </div>
            <div className="mt-5 grid grid-cols-7 gap-2" aria-label="最近两周每日学习量">
              {heatmapValues.map((amount, index) => {
                const intensity = amount === 0 ? 0 : 0.14 + (amount / maxLearningAmount) * 0.86
                return (
                  <div
                    key={`${index}-${amount}`}
                    className="aspect-square rounded-[4px] bg-slate-100"
                    style={amount === 0 ? undefined : { backgroundColor: `rgb(99 102 241 / ${intensity.toFixed(2)})` }}
                    title={`学习量 ${amount}`}
                    aria-label={`第 ${index + 1} 天，学习量 ${amount}`}
                  />
                )
              })}
            </div>
            <div className="mt-3 flex items-center justify-between text-[11px] font-semibold text-slate-400">
              <span>两周前</span>
              <span>颜色越深，学习量越大</span>
              <span>今天</span>
            </div>
          </DataPanel>

          <DataPanel title="复习概览" icon={Clock3}>
            <div className="mt-10 grid grid-cols-3 divide-x divide-slate-200 text-center">
              <Metric label="待复习" value={dueCount} />
              <Metric label="正确率" value={`${summary.stats.accuracy}%`} />
              <Metric label="词汇" value={summary.stats.total_vocab} />
            </div>
          </DataPanel>
        </section>

        <section className="mt-6">
          <h2 className="text-xl font-black text-slate-950">开始学习</h2>
          <div className="mt-3 grid gap-4 lg:grid-cols-[1.08fr_0.92fr]">
            <article className="rounded-[13px] border border-slate-200 bg-white p-5 shadow-[0_4px_14px_rgba(15,23,42,0.05)] sm:p-6">
              <div className="flex items-start gap-4">
                <div className="flex size-12 shrink-0 items-center justify-center rounded-xl border border-indigo-200 bg-indigo-50 text-indigo-600">
                  <BookOpen className="size-6" strokeWidth={1.8} />
                </div>
                <div>
                  <h3 className="text-xl font-black text-slate-950">每日学习</h3>
                  <p className="mt-1 text-sm leading-6 text-slate-500">跟着教材顺序学习语法、词汇、词组和固定句式</p>
                </div>
              </div>
              <p className="mt-5 text-xs font-bold text-slate-500">教材课程 / 初中 / 七年级英语 / 上册</p>
              <button
                type="button"
                onClick={onOpenDailyLearning}
                className="mt-3 w-full rounded-xl bg-slate-50 p-4 text-left transition hover:bg-indigo-50 focus-visible:outline-2 focus-visible:outline-indigo-500"
              >
                <span className="flex items-center justify-between gap-3">
                  <span className="min-w-0 truncate text-sm font-black text-slate-900">Starter Unit 1 · Good morning!</span>
                  <ArrowRight className="size-4 shrink-0 text-slate-400" />
                </span>
                <ProgressBar value={todayPercent} className="mt-4" />
                <span className="mt-2 flex justify-between text-xs font-semibold text-slate-500">
                  <span>学习进度 {todayPercent}%</span>
                  <span>{summary.today_goal.completed} / {summary.today_goal.total} 节已完成</span>
                </span>
              </button>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                <button type="button" onClick={onOpenDailyLearning} className="flex-1 rounded-lg bg-indigo-600 px-4 py-3 text-sm font-bold text-white transition hover:bg-indigo-700">继续今日课程</button>
                <button type="button" onClick={onOpenDailyLearning} className="inline-flex items-center justify-center gap-1 px-4 py-3 text-sm font-bold text-indigo-600 transition hover:text-indigo-700">选择教材 <ArrowRight className="size-4" /></button>
              </div>
            </article>

            <article className="rounded-[13px] border border-slate-200 bg-white p-5 shadow-[0_4px_14px_rgba(15,23,42,0.05)] sm:p-6">
              <div className="flex items-start gap-4">
                <div className="flex size-12 shrink-0 items-center justify-center rounded-xl border border-indigo-200 bg-indigo-50 text-xl font-black text-indigo-600">Aa</div>
                <div>
                  <h3 className="text-xl font-black text-slate-950">背单词</h3>
                  <p className="mt-1 text-sm leading-6 text-slate-500">按记忆曲线安排新词与复习</p>
                </div>
              </div>
              <div className="mt-5 flex items-center gap-3 rounded-xl border border-indigo-100 bg-indigo-50/60 p-4 text-slate-900">
                <Clock3 className="size-5 text-indigo-600" />
                <span className="text-sm font-black">今日 {dueCount} 个待复习</span>
              </div>
              <ProgressBar value={dueCount + completedReviews > 0 ? (completedReviews / (dueCount + completedReviews)) * 100 : 0} className="mt-5" />
              <div className="mt-2 flex justify-between text-xs font-semibold text-slate-500">
                <span>今日已复习</span>
                <span>{completedReviews} 个</span>
              </div>
              <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                <button type="button" onClick={() => onStartVocabularyPractice('review')} className="flex-1 rounded-lg bg-indigo-600 px-4 py-3 text-sm font-bold text-white transition hover:bg-indigo-700">开始复习</button>
                <button type="button" onClick={() => onStartVocabularyPractice('spelling')} className="flex-1 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm font-bold text-indigo-700 transition hover:border-indigo-300">拼写练习</button>
                <button type="button" onClick={onOpenVocabulary} className="inline-flex items-center justify-center gap-1 px-4 py-3 text-sm font-bold text-indigo-600 transition hover:text-indigo-700">管理词汇本 <ArrowRight className="size-4" /></button>
              </div>
            </article>
          </div>
        </section>

        <section className="mt-4 grid gap-4 pb-8 lg:grid-cols-2">
          <article className="rounded-[13px] border border-slate-200 bg-white p-5 shadow-[0_4px_14px_rgba(15,23,42,0.04)]">
            <div className="flex items-center gap-2">
              <Target className="size-4 text-indigo-600" />
              <h3 className="font-black text-slate-900">薄弱知识</h3>
            </div>
            {summary.error_patterns.length > 0 ? (
              <div className="mt-4 space-y-3">
                {summary.error_patterns.slice(0, 3).map((pattern) => (
                  <div key={pattern.id} className="flex items-center justify-between gap-4 text-sm">
                    <span className="truncate text-slate-600">{pattern.name}</span>
                    <span className="shrink-0 font-bold text-slate-900">{pattern.count} 次</span>
                  </div>
                ))}
              </div>
            ) : <p className="mt-4 text-sm text-slate-500">完成练习后，这里会沉淀需要加强的知识点。</p>}
          </article>
          <article className="rounded-[13px] border border-slate-200 bg-white p-5 shadow-[0_4px_14px_rgba(15,23,42,0.04)]">
            <div className="flex items-center gap-2">
              <Sparkles className="size-4 text-indigo-600" />
              <h3 className="font-black text-slate-900">本周目标</h3>
            </div>
            <div className="mt-4 flex items-center justify-between text-sm">
              <span className="text-slate-600">{summary.weekly_goal.label}</span>
              <strong className="text-slate-900">{summary.weekly_goal.completed} / {summary.weekly_goal.total}</strong>
            </div>
            <ProgressBar value={weeklyPercent} className="mt-3" />
          </article>
        </section>
      </div>
    </div>
  )
}

function DataPanel({ title, icon: Icon, children }: { title: string; icon: typeof CalendarDays; children: ReactNode }) {
  return (
    <article className="min-h-[228px] w-full rounded-[13px] border border-slate-200 bg-white px-4 pb-2 pt-4 shadow-[0_4px_14px_rgba(15,23,42,0.06)]">
      <div className="flex items-center gap-2">
        <Icon className="size-[18px] text-indigo-600" strokeWidth={1.9} />
        <h2 className="font-black text-slate-900">{title}</h2>
      </div>
      {children}
    </article>
  )
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <div className="px-2"><p className="text-xs font-semibold text-slate-500">{label}</p><p className="mt-4 text-2xl font-black text-slate-950">{value}</p></div>
}

function ProgressBar({ value, className = '' }: { value: number; className?: string }) {
  return <div className={`h-2 overflow-hidden rounded-full bg-slate-200 ${className}`}><div className="h-full rounded-full bg-indigo-600 transition-[width] duration-500" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div>
}

function toPercent(completed: number, total: number) {
  return total > 0 ? Math.round((completed / total) * 100) : 0
}


function VocabularyListRow({
  item,
  isDeleting,
  onDelete,
}: {
  item: VocabularyListItem
  isDeleting: boolean
  onDelete: (item: VocabularyListItem) => void
}) {
  const statusText = getVocabularyStatusText(item.status)
  const confidencePercent = Math.round(item.confidence * 100)

  return (
    <article className="rounded-lg border bg-background p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold text-foreground">{item.word}</h3>
            {item.phonetic && (
              <span className="text-sm text-muted-foreground">{item.phonetic}</span>
            )}
          </div>
          <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
            {item.meaning || '暂无释义'}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-medium ${getVocabularyStatusClass(
              item.status,
            )}`}
          >
            {statusText}
          </span>
          <button
            type="button"
            onClick={() => onDelete(item)}
            disabled={isDeleting}
            className="inline-flex size-8 items-center justify-center rounded-lg border text-muted-foreground transition-colors hover:border-error/40 hover:bg-error/5 hover:text-error disabled:cursor-not-allowed disabled:opacity-50"
            aria-label={`删除 ${item.word}`}
            title="删除单词"
          >
            {isDeleting ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 text-xs text-muted-foreground sm:grid-cols-3">
        <div>
          <p>熟练度</p>
          <p className="mt-1 font-semibold text-foreground">{confidencePercent}%</p>
        </div>
        <div>
          <p>复习次数</p>
          <p className="mt-1 font-semibold text-foreground">{item.review_count}</p>
        </div>
        <div>
          <p>下次复习</p>
          <p className="mt-1 font-semibold text-foreground">
            {formatDate(item.next_review_at) || '待安排'}
          </p>
        </div>
      </div>
    </article>
  )
}

function getVocabularyStatusText(status: string) {
  const statusMap: Record<string, string> = {
    new: '新词',
    learning: '学习中',
    reviewing: '复习中',
    mastered: '已掌握',
  }
  return statusMap[status] ?? status
}

function getVocabularyStatusClass(status: string) {
  if (status === 'mastered') return 'bg-success/15 text-success'
  if (status === 'reviewing') return 'bg-primary/10 text-primary'
  if (status === 'learning') return 'bg-warning/15 text-warning'
  return 'bg-muted text-muted-foreground'
}

function formatDate(value?: string | null) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
  })
}
