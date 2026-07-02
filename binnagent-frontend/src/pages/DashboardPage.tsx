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
import type { DashboardSummary, Learner, VocabularyListItem } from '@/types'
import { useToast } from '@/hooks/useToast'
import type { VocabularyPracticeMode } from '@/pages/VocabularyPracticePage'
import { VocabularyPracticePage } from '@/pages/VocabularyPracticePage'

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
  const [detailItemId, setDetailItemId] = useState<string | null>(null)

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

  if (detailItemId) {
    return (
      <VocabularyPracticePage
        learner={learner}
        initialMode="new"
        readonlyItemId={detailItemId}
        readonlyBackLabel="返回词汇本"
        sourceLabel="我的词汇本"
        onExit={() => setDetailItemId(null)}
      />
    )
  }

  if (isLoading && !summary) {
    return <LoadingState title="正在加载学习中心" description="正在读取今日目标、复习队列和最近学习记录..." />
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
                    onOpen={(selected) => setDetailItemId(selected.id)}
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
  const focusReasons = buildFocusReasons(summary)

  return (
    <PageShell>
        <FeatureHero
          eyebrow="Learning Center"
          title="学习中心"
          description={`${learnerName}，今天从一个明确任务开始，把知识真正学会。`}
          stats={[
            { label: '今日目标', value: `${summary.today_goal.completed}/${summary.today_goal.total}`, tone: todayPercent >= 100 ? 'success' : 'primary' },
            { label: '待复习', value: dueCount, tone: dueCount > 0 ? 'warning' : 'success' },
            { label: '连续学习', value: `${summary.stats.streak_days} 天` },
          ]}
        />

        <section className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
          <PrimaryLearningRoute
            reasons={focusReasons}
            summary={summary}
            todayPercent={todayPercent}
            onOpenDailyLearning={onOpenDailyLearning}
          />
          <ActivityCalendarCard summary={summary} />
        </section>

        <LearningRouteGrid
          summary={summary}
          onOpenActivity={() => document.getElementById('learning-activity')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
          onOpenDailyLearning={onOpenDailyLearning}
          onOpenVocabulary={onOpenVocabulary}
          onStartVocabularyPractice={onStartVocabularyPractice}
        />

        <LearningStatusStrip summary={summary} reasons={focusReasons} />
    </PageShell>
  )
}

function PrimaryLearningRoute({
  reasons,
  summary,
  todayPercent,
  onOpenDailyLearning,
}: {
  reasons: string[]
  summary: DashboardSummary
  todayPercent: number
  onOpenDailyLearning: () => void
}) {
  return (
    <SurfaceCard className="border-primary/20">
      <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-wide text-primary">主学习路线</p>
          <h2 className="mt-2 text-2xl font-black text-slate-950">Unit 1 词汇复习 + 对话补全练习</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            预计 15-20 分钟。先处理到期词汇，再回到教材语境完成一组短练习。
          </p>
          <div className="mt-5 max-w-xl rounded-xl bg-slate-50 p-4">
            <p className="text-xs font-bold text-slate-500">今天优先做这个</p>
            <ul className="mt-2 space-y-1 text-sm leading-6 text-slate-700">
              {reasons.slice(0, 2).map((reason) => <li key={reason}>{reason}</li>)}
            </ul>
          </div>
        </div>

        <div className="w-full shrink-0 sm:w-56">
          <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
            <div className="flex items-center justify-between text-sm">
              <span className="font-bold text-slate-600">{summary.today_goal.label}</span>
              <span className="font-black text-slate-950">{summary.today_goal.completed}/{summary.today_goal.total}</span>
            </div>
            <ProgressBar value={todayPercent} className="mt-3" />
          </div>
          <Button className="mt-4 w-full" onClick={onOpenDailyLearning}>开始今日学习</Button>
        </div>
      </div>
    </SurfaceCard>
  )
}

function ActivityCalendarCard({ summary }: { summary: DashboardSummary }) {
  const activity = summary.daily_activity.length > 0 ? summary.daily_activity : []
  const maxLearningAmount = Math.max(...activity.map((item) => item.count), 1)

  return (
    <section id="learning-activity">
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

        <div className="mt-5 grid grid-cols-7 gap-2" aria-label="最近 14 天活跃度">
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
        <div className="mt-4">
          <Button variant="secondary" className="w-full justify-between" onClick={() => document.getElementById('learning-activity')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>
            查看学习记录 <ArrowRight className="size-4" />
          </Button>
        </div>
      </SurfaceCard>
    </section>
  )
}

function LearningRouteGrid({
  summary,
  onOpenActivity,
  onOpenDailyLearning,
  onOpenVocabulary,
  onStartVocabularyPractice,
}: {
  summary: DashboardSummary
  onOpenActivity: () => void
  onOpenDailyLearning: () => void
  onOpenVocabulary: () => void
  onStartVocabularyPractice: (mode: VocabularyPracticeMode) => void
}) {
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <LearningRouteCard
        icon={BookOpen}
        title="教材学习"
        description="沿着当前单元完成今日课程。"
        status={`${summary.today_goal.completed}/${summary.today_goal.total} 项`}
        action="继续"
        onAction={onOpenDailyLearning}
      />
      <LearningRouteCard
        icon={Clock3}
        title="词汇复习"
        description="处理到期单词，更新下次复习时间。"
        status={`${summary.stats.today_reviews} 个待复习`}
        action="复习"
        onAction={() => onStartVocabularyPractice('review')}
      />
      <LearningRouteCard
        icon={Target}
        title="错因复盘"
        description="查看近期薄弱点，安排下一组短练习。"
        status={summary.error_patterns.length > 0 ? `${summary.error_patterns.length} 类薄弱点` : '暂无明显薄弱点'}
        action="查看"
        onAction={onOpenVocabulary}
      />
      <LearningRouteCard
        icon={CalendarDays}
        title="学习记录"
        description="回顾最近 14 天活跃度和学习节奏。"
        status={`${summary.stats.streak_days} 天连续学习`}
        action="查看"
        onAction={onOpenActivity}
      />
    </section>
  )
}

function LearningRouteCard({
  action,
  description,
  icon: Icon,
  onAction,
  status,
  title,
}: {
  action: string
  description: string
  icon: typeof BookOpen
  onAction: () => void
  status: string
  title: string
}) {
  return (
    <SurfaceCard className="flex min-h-[220px] flex-col">
      <div className="flex size-11 items-center justify-center rounded-xl border border-indigo-200 bg-indigo-50 text-indigo-600">
        <Icon className="size-5" />
      </div>
      <h3 className="mt-4 text-lg font-black text-slate-950">{title}</h3>
      <p className="mt-2 min-h-12 text-sm leading-6 text-slate-500">{description}</p>
      <p className="mt-3 text-sm font-black text-primary">{status}</p>
      <div className="mt-auto pt-4">
        <Button variant="secondary" className="w-full justify-between" onClick={onAction}>{action}<ArrowRight className="size-4" /></Button>
      </div>
    </SurfaceCard>
  )
}

function LearningStatusStrip({ summary, reasons }: { summary: DashboardSummary; reasons: string[] }) {
  const leadingReason = reasons[0] ?? '今天从一个小任务开始，保持学习连续性。'
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        <Target className="mt-0.5 size-4 shrink-0 text-primary" />
        <p className="min-w-0 text-slate-600">
          <span className="font-black text-slate-900">学习状态：</span>{leadingReason}
        </p>
      </div>
      <p className="shrink-0 font-bold text-slate-500">正确率 {summary.stats.accuracy}% · 词汇 {summary.stats.total_vocab}</p>
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

function VocabularyListRow({
  item,
  isDeleting,
  onDelete,
  onOpen,
}: {
  item: VocabularyListItem
  isDeleting: boolean
  onDelete: (item: VocabularyListItem) => void
  onOpen: (item: VocabularyListItem) => void
}) {
  const statusText = getVocabularyStatusText(item.status)
  const confidencePercent = Math.round(item.confidence * 100)

  return (
    <article
      role="button"
      tabIndex={0}
      onClick={() => onOpen(item)}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onOpen(item)
        }
      }}
      className="cursor-pointer rounded-lg border bg-background p-4 text-left transition hover:border-primary/40 hover:shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
      aria-label={`查看 ${item.word} 详情`}
    >
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
            onClick={(event) => {
              event.stopPropagation()
              onDelete(item)
            }}
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
