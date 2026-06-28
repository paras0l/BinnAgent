import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CalendarDays,
  Clock3,
  Plus,
  RefreshCw,
  Search,
  Target,
  Trash2,
  X,
} from 'lucide-react'
import { VocabReviewCard } from '@/components/dashboard/VocabReviewCard'
import { ErrorPatternList } from '@/components/dashboard/ErrorPatternList'
import { LearningGoalProgress } from '@/components/dashboard/LearningGoalProgress'
import { FeatureHero } from '@/components/layout/FeatureHero'
import { PageShell } from '@/components/layout/PageShell'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import { ReasonCard } from '@/components/learning/ReasonCard'
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
  const [wordPendingDelete, setWordPendingDelete] = useState<VocabularyListItem | null>(null)
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
      setWordPendingDelete(null)
    }
  }

  if (isLoading && !summary) {
    return <LoadingState title="正在加载学习中心" description="正在读取今日目标、复习队列和最近记忆..." />
  }

  if (!summary) {
    return (
      <ErrorState
        title="学习中心暂时无法加载"
        description="可以重新加载学习中心，或先进入 AI 对话继续学习。"
        action={<Button onClick={() => void loadDashboard()}><RefreshCw className="size-4" />重新加载</Button>}
      />
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
    <PageShell>
      <FeatureHero
        eyebrow="Vocabulary Workspace"
        title="背单词"
        description="先处理到期复习，再补充新词；每次评分都会更新下一次复习时间。"
        actions={
          <>
            <Button variant="secondary" onClick={() => setActiveWorkspace('home')}><ArrowLeft className="size-4" />返回学习中心</Button>
            <Button variant="secondary" onClick={handleOpenVocabularyList}><BookOpen className="size-4" />管理词汇本</Button>
          </>
        }
        stats={[
          { label: '今日待复习', value: summary.stats.today_reviews, tone: 'primary' },
          { label: '今日已复习', value: summary.stats.today_completed_reviews, tone: 'success' },
          { label: '词汇总量', value: summary.stats.total_vocab },
          { label: '正确率', value: `${summary.stats.accuracy}%` },
        ]}
      />

        <section className="grid gap-3 lg:grid-cols-3">
          <button type="button" onClick={() => onStartVocabularyPractice('new')} className="rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-left text-emerald-800 transition hover:border-emerald-300"><span className="block text-base font-black">认识新词</span><span className="mt-1 block text-xs text-emerald-700">先看发音、释义和例句，低压力建立印象</span></button>
          <button type="button" onClick={() => onStartVocabularyPractice('review')} className="rounded-xl bg-indigo-600 px-5 py-4 text-left text-white shadow-lg shadow-indigo-100 transition hover:bg-indigo-700"><span className="block text-base font-black">今日复习</span><span className="mt-1 block text-xs text-indigo-100">默认隐藏答案，先主动回忆再评分</span></button>
          <button type="button" onClick={() => onStartVocabularyPractice('spelling')} className="rounded-xl border border-indigo-200 bg-indigo-50 px-5 py-4 text-left text-indigo-800 transition hover:border-indigo-300"><span className="block text-base font-black">拼写练习</span><span className="mt-1 block text-xs text-indigo-600">听音主动拼写，获得字母级反馈</span></button>
        </section>

      {isVocabListOpen && (
        <SurfaceCard>
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
                    onDelete={setWordPendingDelete}
                  />
                ))}
              </div>
            )}
          </div>
        </SurfaceCard>
      )}

      <SurfaceCard>
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
          <Button
            onClick={() => void handleAddWord()}
            disabled={isAddingWord}
          >
            <Plus className="h-4 w-4" />
            加入
          </Button>
        </div>
      </SurfaceCard>

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
        <EmptyState
          icon={<BookOpen className="h-5 w-5" />}
          title="暂无待复习词卡"
          description="当你在对话或课程里沉淀新词后，系统会按复习计划把词卡放到这里。"
          action={<Button variant="secondary" onClick={() => onStartVocabularyPractice('new')}>认识新词</Button>}
        />
      )}

      <ErrorPatternList patterns={summary.error_patterns} />

      <LearningGoalProgress
        dailyGoal={summary.today_goal}
        weeklyGoal={summary.weekly_goal}
      />
      <ConfirmDialog
        open={Boolean(wordPendingDelete)}
        title="删除这个词？"
        description={`删除后「${wordPendingDelete?.word ?? ''}」不会再出现在复习计划里，但历史练习记录仍会保留。`}
        confirmLabel="删除"
        danger
        isBusy={Boolean(wordPendingDelete && deletingWordId === wordPendingDelete.id)}
        onCancel={() => setWordPendingDelete(null)}
        onConfirm={() => {
          if (wordPendingDelete) void handleDeleteWord(wordPendingDelete)
        }}
      />
    </PageShell>
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
  const dueCount = summary.stats.today_reviews
  const completedReviews = summary.stats.today_completed_reviews
  const focusReasons = buildFocusReasons(summary)

  return (
    <PageShell>
        <FeatureHero
          eyebrow="Learning Center"
          title="学习中心"
          description={`${learnerName}，今天从一个明确任务开始，把知识真正学会。`}
          actions={
            <>
              <Button onClick={onOpenDailyLearning}>查看今日任务 <ArrowRight className="size-4" /></Button>
              <Button variant="secondary" onClick={() => onStartVocabularyPractice('review')}>词汇复习</Button>
            </>
          }
        />

        <section className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="grid gap-5">
            <TodayFocusCard
              reasons={focusReasons}
              onOpenDailyLearning={onOpenDailyLearning}
              onStartVocabularyReview={() => onStartVocabularyPractice('review')}
            />
            <ReviewQueueCard
              dueCount={dueCount}
              completedReviews={completedReviews}
              firstReviewWord={summary.review_items[0]?.word}
              onOpenVocabulary={onOpenVocabulary}
              onReview={() => onStartVocabularyPractice('review')}
              onSpelling={() => onStartVocabularyPractice('spelling')}
            />
          </div>

          <aside className="grid gap-4">
            <LearningProgressPanel
              summary={summary}
              todayPercent={todayPercent}
              onOpenDailyLearning={onOpenDailyLearning}
            />
            <LearningCalendarPanel summary={summary} />
            <QuickStartPanel
              onOpenDailyLearning={onOpenDailyLearning}
              onOpenVocabulary={onOpenVocabulary}
              onStartVocabularyPractice={onStartVocabularyPractice}
            />
          </aside>
        </section>

        <MemoryReasonSection summary={summary} reasons={focusReasons} />
    </PageShell>
  )
}

function LearningProgressPanel({
  summary,
  todayPercent,
  onOpenDailyLearning,
}: {
  summary: DashboardSummary
  todayPercent: number
  onOpenDailyLearning: () => void
}) {
  return (
    <SurfaceCard>
      <div className="flex items-center gap-2">
        <Target className="size-4 text-primary" />
        <h2 className="text-base font-black text-slate-950">今日进度</h2>
      </div>
      <button
        type="button"
        onClick={onOpenDailyLearning}
        className="mt-4 w-full rounded-xl border border-indigo-100 bg-indigo-50 px-4 py-4 text-left transition hover:border-indigo-300 hover:bg-indigo-100/70"
      >
        <div className="flex items-end justify-between gap-3">
          <span className="text-sm font-bold text-indigo-700">{summary.today_goal.label}</span>
          <strong className="text-3xl font-black leading-none text-indigo-900">
            {summary.today_goal.completed}/{summary.today_goal.total}
          </strong>
        </div>
        <ProgressBar value={todayPercent} className="mt-4 bg-indigo-100" />
        <p className="mt-3 text-xs font-semibold text-indigo-700">
          {todayPercent >= 100 ? '今日任务已完成，点击查看记录。' : '点击查看今天具体要完成的教材任务。'}
        </p>
      </button>
      <div className="mt-3 rounded-xl border border-slate-200 px-4 py-3">
        <div className="flex items-center justify-between text-sm">
          <span className="font-bold text-slate-600">{summary.weekly_goal.label}</span>
          <span className="font-black text-slate-950">{summary.weekly_goal.completed}/{summary.weekly_goal.total}</span>
        </div>
        <ProgressBar value={toPercent(summary.weekly_goal.completed, summary.weekly_goal.total)} className="mt-3" />
      </div>
    </SurfaceCard>
  )
}

function LearningCalendarPanel({ summary }: { summary: DashboardSummary }) {
  const activity = summary.daily_activity.length > 0 ? summary.daily_activity : []
  const maxLearningAmount = Math.max(...activity.map((item) => item.count), 1)

  return (
    <SurfaceCard>
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <CalendarDays className="size-4 text-primary" />
          <h2 className="text-base font-black text-slate-950">学习日历</h2>
        </div>
        <div className="text-right">
          <p className="text-xs font-semibold text-slate-500">连续学习</p>
          <p className="text-lg font-black text-slate-950">{summary.stats.streak_days} 天</p>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-7 gap-2" aria-label="最近两周每日学习量">
        {activity.map((item) => {
          const intensity = item.count === 0 ? 0 : 0.14 + (item.count / maxLearningAmount) * 0.86
          const label = `${formatActivityDate(item.date)}，学习量 ${item.count}`
          return (
            <div
              key={item.date}
              className="aspect-square rounded-[4px] bg-slate-100 ring-1 ring-inset ring-slate-200/70 transition hover:scale-110 hover:ring-indigo-300"
              style={item.count === 0 ? undefined : { backgroundColor: `rgb(99 102 241 / ${intensity.toFixed(2)})` }}
              title={label}
              aria-label={label}
            />
          )
        })}
      </div>
      <div className="mt-3 flex items-center justify-between text-[11px] font-semibold text-slate-400">
        <span>{activity[0] ? formatMonthDay(activity[0].date) : '两周前'}</span>
        <span>颜色越深，学习越多</span>
        <span>{activity.at(-1) ? formatMonthDay(activity.at(-1)!.date) : '今天'}</span>
      </div>
    </SurfaceCard>
  )
}

function QuickStartPanel({
  onOpenDailyLearning,
  onOpenVocabulary,
  onStartVocabularyPractice,
}: {
  onOpenDailyLearning: () => void
  onOpenVocabulary: () => void
  onStartVocabularyPractice: (mode: VocabularyPracticeMode) => void
}) {
  return (
    <SurfaceCard>
      <h2 className="text-base font-black text-slate-950">快速开始</h2>
      <div className="mt-4 grid gap-2">
        <Button className="w-full justify-between" onClick={onOpenDailyLearning}>继续教材 <ArrowRight className="size-4" /></Button>
        <Button variant="secondary" className="w-full justify-between" onClick={() => onStartVocabularyPractice('review')}>今日复习 <ArrowRight className="size-4" /></Button>
        <Button variant="ghost" className="w-full justify-between" onClick={onOpenVocabulary}>词汇本 <ArrowRight className="size-4" /></Button>
      </div>
    </SurfaceCard>
  )
}

function TodayFocusCard({
  reasons,
  onOpenDailyLearning,
  onStartVocabularyReview,
}: {
  reasons: string[]
  onOpenDailyLearning: () => void
  onStartVocabularyReview: () => void
}) {
  return (
    <SurfaceCard className="border-primary/20">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-wide text-primary">今日建议</p>
          <h2 className="mt-2 text-2xl font-black text-slate-950">Unit 1 词汇复习 + 对话补全练习</h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            预计 15-20 分钟。先处理到期词汇，再回到教材语境完成一组短练习。
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg bg-slate-50 p-3">
              <p className="text-xs font-bold text-slate-500">为什么推荐</p>
              <ul className="mt-2 space-y-1 text-sm leading-6 text-slate-700">
                {reasons.map((reason) => <li key={reason}>{reason}</li>)}
              </ul>
            </div>
            <div className="rounded-lg bg-emerald-50 p-3 text-emerald-800">
              <p className="text-xs font-bold">完成后会沉淀</p>
              <p className="mt-2 text-sm leading-6">更新词汇掌握度、错因记忆、教材进度和下次复习时间。</p>
            </div>
          </div>
        </div>
        <div className="w-full shrink-0 rounded-lg border border-slate-200 bg-white p-4 lg:w-56">
          <p className="text-sm font-bold leading-6 text-slate-600">先进入今日任务查看具体练习，再按需要单独处理词汇复习。</p>
          <Button className="mt-4 w-full" onClick={onOpenDailyLearning}>开始今日学习</Button>
          <Button variant="secondary" className="mt-2 w-full" onClick={onStartVocabularyReview}>只做词汇复习</Button>
        </div>
      </div>
    </SurfaceCard>
  )
}

function ReviewQueueCard({ dueCount, completedReviews, firstReviewWord, onOpenVocabulary, onReview, onSpelling }: { dueCount: number; completedReviews: number; firstReviewWord?: string; onOpenVocabulary: () => void; onReview: () => void; onSpelling: () => void }) {
  const total = dueCount + completedReviews
  return (
    <SurfaceCard>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-xl font-black text-slate-950">复习队列</h3>
          <p className="mt-1 text-sm leading-6 text-slate-500">把到期内容先处理掉，系统会重新安排间隔。</p>
        </div>
        <Clock3 className="size-5 text-primary" />
      </div>
      <div className="mt-5 grid grid-cols-3 divide-x divide-slate-200 text-center">
        <Metric label="待复习" value={dueCount} />
        <Metric label="已完成" value={completedReviews} />
        <Metric label="下一张" value={firstReviewWord ?? '暂无'} />
      </div>
      <ProgressBar value={total > 0 ? (completedReviews / total) * 100 : 0} className="mt-5" />
      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <Button variant="secondary" onClick={onReview}>开始复习</Button>
        <Button variant="secondary" onClick={onSpelling}>拼写练习</Button>
        <Button variant="ghost" onClick={onOpenVocabulary}>词汇本</Button>
      </div>
    </SurfaceCard>
  )
}

function MemoryReasonSection({ summary, reasons }: { summary: DashboardSummary; reasons: string[] }) {
  return (
    <section>
      <div className="mb-3 flex items-center gap-2">
        <Target className="size-4 text-primary" />
        <h2 className="text-base font-black text-slate-950">为什么这样推荐</h2>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        {summary.error_patterns.length > 0 ? summary.error_patterns.slice(0, 3).map((pattern) => (
          <ReasonCard
            key={pattern.id}
            title={pattern.name}
            reason={`系统近期记录到这个薄弱点出现 ${pattern.count} 次，因此今天优先安排相关复习和短练习。`}
            evidence={[`错因记录：${pattern.count} 次`, ...reasons.slice(0, 1)]}
            outcome="练完后会更新错因记忆和后续推荐权重。"
          />
        )) : (
          <ReasonCard
            title="先建立学习基线"
            reason="当前薄弱点还不够明确，建议先完成一节教材任务和一组词汇复习。"
            evidence={reasons}
            outcome="系统会根据练习结果沉淀下一次推荐依据。"
          />
        )}
      </div>
    </section>
  )
}

function buildFocusReasons(summary: DashboardSummary) {
  const reasons = []
  if (summary.stats.today_reviews > 0) reasons.push(`今天有 ${summary.stats.today_reviews} 个词汇到期，需要先主动回忆。`)
  if (summary.error_patterns[0]) reasons.push(`${summary.error_patterns[0].name} 最近出现 ${summary.error_patterns[0].count} 次，适合安排短练习。`)
  if (summary.today_goal.completed < summary.today_goal.total) reasons.push(`今日目标还剩 ${summary.today_goal.total - summary.today_goal.completed} 项，适合继续教材主线。`)
  return reasons.length > 0 ? reasons : ['今天没有明显积压任务，可以用一节 10 分钟教材练习建立学习节奏。']
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

function formatActivityDate(date: string) {
  return new Date(`${date}T00:00:00`).toLocaleDateString('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'short',
  })
}

function formatMonthDay(date: string) {
  return new Date(`${date}T00:00:00`).toLocaleDateString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
  })
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
