import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  BrainCircuit,
  CalendarDays,
  ClipboardList,
  Clock3,
  FileText,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
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
import { IconButton } from '@/components/ui/IconButton'
import { LoadingState } from '@/components/ui/LoadingState'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import type { DashboardSummary, Learner, MemorySummary, VocabularyListItem } from '@/types'
import { useToast } from '@/hooks/useToast'
import type { VocabularyPracticeMode } from '@/pages/VocabularyPracticePage'
import { VocabularyPracticePage } from '@/pages/VocabularyPracticePage'

type DashboardWorkspace = 'home' | 'vocabulary' | 'profile' | 'records'

interface DashboardPageProps {
  learner: Learner
  onOpenDailyLearning: () => void
  onStartVocabularyPractice: (mode?: VocabularyPracticeMode) => void
}

export function DashboardPage({ learner, onOpenDailyLearning, onStartVocabularyPractice }: DashboardPageProps) {
  const { showToast } = useToast()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [memorySummary, setMemorySummary] = useState<MemorySummary | null>(null)
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
  const [activeWorkspace, setActiveWorkspace] = useState<DashboardWorkspace>('home')
  const [detailItemId, setDetailItemId] = useState<string | null>(null)

  const loadDashboard = useCallback(async () => {
    setIsLoading(true)
    try {
      const [dashboardResult, memoryResult] = await Promise.allSettled([
        fetchDashboardSummary(learner.id),
        fetchMemorySummary(learner.id),
      ])
      if (dashboardResult.status === 'rejected') throw dashboardResult.reason
      setSummary(dashboardResult.value)
      if (memoryResult.status === 'fulfilled') {
        setMemorySummary(memoryResult.value)
      } else {
        console.warn('Memory summary unavailable:', memoryResult.reason)
        setMemorySummary(null)
      }
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
        onOpenProfile={() => setActiveWorkspace('profile')}
        onOpenRecords={() => setActiveWorkspace('records')}
        onStartVocabularyPractice={onStartVocabularyPractice}
      />
    )
  }

  if (activeWorkspace === 'profile') {
    return (
      <LearningProfileView
        learner={learner}
        summary={summary}
        memorySummary={memorySummary}
        onBack={() => setActiveWorkspace('home')}
        onOpenDailyLearning={onOpenDailyLearning}
        onOpenRecords={() => setActiveWorkspace('records')}
      />
    )
  }

  if (activeWorkspace === 'records') {
    return (
      <LearningRecordsView
        summary={summary}
        memorySummary={memorySummary}
        onBack={() => setActiveWorkspace('home')}
        onOpenProfile={() => setActiveWorkspace('profile')}
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

        <section className="grid gap-3 lg:grid-cols-3" aria-label="词汇练习入口">
          <VocabularyModeCard
            tone="success"
            title="认识新词"
            description="先看发音、释义和例句，低压力建立印象"
            onClick={() => onStartVocabularyPractice('new')}
          />
          <VocabularyModeCard
            tone="primary"
            title="今日复习"
            description="默认隐藏答案，先主动回忆再评分"
            onClick={() => onStartVocabularyPractice('review')}
          />
          <VocabularyModeCard
            tone="accent"
            title="拼写练习"
            description="听音主动拼写，获得字母级反馈"
            onClick={() => onStartVocabularyPractice('spelling')}
          />
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
                  name="vocabulary_search"
                  autoComplete="off"
                  aria-label="搜索词汇本"
                  value={vocabQuery}
                  onChange={(event) => setVocabQuery(event.target.value)}
                  className="w-full rounded-lg border bg-background py-2 pl-9 pr-3 text-sm outline-none transition-colors focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/20 md:w-64"
                  placeholder="搜索单词、音标或释义…"
                />
              </div>
              <IconButton
                label="关闭词汇列表"
                onClick={() => setIsVocabListOpen(false)}
              >
                <X className="h-4 w-4" />
              </IconButton>
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
            name="new_vocabulary_word"
            autoComplete="off"
            aria-label="新词单词"
            value={newWord}
            onChange={(event) => setNewWord(event.target.value)}
            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none transition-colors focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/20"
            placeholder="例如：significant…"
            maxLength={255}
          />
          <input
            name="new_vocabulary_phonetic"
            autoComplete="off"
            aria-label="新词音标"
            value={newPhonetic}
            onChange={(event) => setNewPhonetic(event.target.value)}
            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none transition-colors focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/20"
            placeholder="可选音标，例如：/sɪɡˈnɪfɪkənt/…"
            maxLength={255}
          />
          <input
            name="new_vocabulary_meaning"
            autoComplete="off"
            aria-label="新词释义"
            value={newMeaning}
            onChange={(event) => setNewMeaning(event.target.value)}
            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none transition-colors focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/20"
            placeholder="可选释义，例如：重要的，显著的…"
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
  onOpenProfile,
  onOpenRecords,
  onStartVocabularyPractice,
}: {
  learnerName: string
  summary: DashboardSummary
  onOpenDailyLearning: () => void
  onOpenProfile: () => void
  onOpenRecords: () => void
  onStartVocabularyPractice: (mode?: VocabularyPracticeMode) => void
}) {
  const todayPercent = toPercent(summary.today_goal.completed, summary.today_goal.total)
  const dueCount = summary.stats.today_reviews
  const focusReasons = buildFocusReasons(summary)

  return (
    <PageShell>
        <FeatureHero
          eyebrow="今日学习"
          title="今天先完成一组小闭环"
          description={`${learnerName}，按推荐顺序学 15 分钟：先回忆，再进教材，最后用一道题确认掌握。`}
          actions={
            <>
              <Button onClick={onOpenDailyLearning}><BookOpen className="size-4" />开始学习</Button>
              <Button variant="secondary" onClick={() => onStartVocabularyPractice('review')}><Clock3 className="size-4" />先复习词汇</Button>
            </>
          }
          stats={[
            { label: '今日目标', value: `${summary.today_goal.completed}/${summary.today_goal.total}`, tone: todayPercent >= 100 ? 'success' : 'primary' },
            { label: '待复习', value: dueCount, tone: dueCount > 0 ? 'warning' : 'success' },
            { label: '连续学习', value: `${summary.stats.streak_days} 天` },
            { label: '正确率', value: `${summary.stats.accuracy}%` },
          ]}
        />

        <section className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
          <PrimaryLearningRoute
            reasons={focusReasons}
            summary={summary}
            todayPercent={todayPercent}
            onOpenDailyLearning={onOpenDailyLearning}
            onStartVocabularyPractice={onStartVocabularyPractice}
          />
          <aside className="space-y-4">
            <TodayReviewCard summary={summary} onStartVocabularyPractice={onStartVocabularyPractice} />
            <ActivityCalendarCard summary={summary} onOpenRecords={onOpenRecords} />
          </aside>
        </section>

        <LearningRouteGrid
          summary={summary}
          onOpenProfile={onOpenProfile}
          onOpenRecords={onOpenRecords}
          onOpenDailyLearning={onOpenDailyLearning}
          onStartVocabularyPractice={onStartVocabularyPractice}
        />

        <LearningStatusStrip summary={summary} reasons={focusReasons} onOpenProfile={onOpenProfile} />
    </PageShell>
  )
}

function PrimaryLearningRoute({
  reasons,
  summary,
  todayPercent,
  onOpenDailyLearning,
  onStartVocabularyPractice,
}: {
  reasons: string[]
  summary: DashboardSummary
  todayPercent: number
  onOpenDailyLearning: () => void
  onStartVocabularyPractice: (mode?: VocabularyPracticeMode) => void
}) {
  const steps = buildTodaySteps(summary)
  return (
    <SurfaceCard className="border-primary/20 p-0">
      <div className="grid gap-0 xl:grid-cols-[minmax(0,1fr)_260px]">
        <div className="p-5 sm:p-6">
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-wide text-primary">主学习路线</p>
          <h2 className="mt-2 text-2xl font-black text-slate-950">继续教材主线，把今天的任务做完</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            预计 15-20 分钟。系统会优先处理到期复习，再回到当前教材单元完成一组短练习。
          </p>

          <div className="mt-5 grid gap-3">
            {steps.map((step, index) => (
              <button
                key={step.title}
                type="button"
                onClick={step.action === 'review' ? () => onStartVocabularyPractice('review') : onOpenDailyLearning}
                className="grid grid-cols-[34px_minmax(0,1fr)_auto] items-start gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left transition hover:border-indigo-200 hover:bg-indigo-50/40"
              >
                <span className={`flex size-8 items-center justify-center rounded-lg text-sm font-black ${
                  step.state === 'done' ? 'bg-emerald-100 text-emerald-700' : index === 0 ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600'
                }`}>
                  {index + 1}
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-black text-slate-950">{step.title}</span>
                  <span className="mt-1 block text-xs leading-5 text-slate-500">{step.description}</span>
                </span>
                <ArrowRight className="mt-2 size-4 text-slate-400" />
              </button>
            ))}
          </div>
        </div>
        </div>

        <div className="border-t border-slate-100 bg-slate-50 p-5 xl:border-l xl:border-t-0">
          <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <div className="flex items-center justify-between text-sm">
              <span className="font-bold text-slate-600">{summary.today_goal.label}</span>
              <span className="font-black text-slate-950">{summary.today_goal.completed}/{summary.today_goal.total}</span>
            </div>
            <ProgressBar value={todayPercent} className="mt-3" />
          </div>
          <div className="mt-4 rounded-xl bg-white px-4 py-3 text-sm leading-6 text-slate-600 shadow-sm ring-1 ring-slate-200">
            <p className="text-xs font-black uppercase text-slate-500">推荐原因</p>
            <ul className="mt-2 space-y-1">
              {reasons.slice(0, 3).map((reason) => <li key={reason}>{reason}</li>)}
            </ul>
          </div>
          <Button className="mt-4 w-full" onClick={onOpenDailyLearning}>开始今日学习</Button>
        </div>
      </div>
    </SurfaceCard>
  )
}

function TodayReviewCard({
  summary,
  onStartVocabularyPractice,
}: {
  summary: DashboardSummary
  onStartVocabularyPractice: (mode?: VocabularyPracticeMode) => void
}) {
  const due = summary.stats.today_reviews
  return (
    <SurfaceCard>
      <div className="flex items-center justify-between gap-3">
        <SectionHeading icon={<Clock3 className="size-4" />} title="复习队列" />
        <span className={`rounded-lg px-2 py-1 text-xs font-black ${due > 0 ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'}`}>
          {due > 0 ? `${due} 个到期` : '已清空'}
        </span>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-500">
        {due > 0 ? '先主动回忆到期词汇，可以降低后面教材练习的负担。' : '今天没有积压词汇，可以直接进入教材任务。'}
      </p>
      <div className="mt-4 grid gap-2">
        <Button variant={due > 0 ? 'primary' : 'secondary'} className="w-full justify-between" onClick={() => onStartVocabularyPractice('review')}>
          开始复习 <ArrowRight className="size-4" />
        </Button>
        <Button variant="secondary" className="w-full justify-between" onClick={() => onStartVocabularyPractice('spelling')}>
          拼写练习 <ArrowRight className="size-4" />
        </Button>
      </div>
    </SurfaceCard>
  )
}

function ActivityCalendarCard({
  summary,
  onOpenRecords,
  showAction = true,
}: {
  summary: DashboardSummary
  onOpenRecords?: () => void
  showAction?: boolean
}) {
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
        {showAction && onOpenRecords ? (
          <div className="mt-4">
            <Button variant="secondary" className="w-full justify-between" onClick={onOpenRecords}>
              查看学习记录 <ArrowRight className="size-4" />
            </Button>
          </div>
        ) : null}
      </SurfaceCard>
    </section>
  )
}

function LearningRouteGrid({
  summary,
  onOpenProfile,
  onOpenRecords,
  onOpenDailyLearning,
  onStartVocabularyPractice,
}: {
  summary: DashboardSummary
  onOpenProfile: () => void
  onOpenRecords: () => void
  onOpenDailyLearning: () => void
  onStartVocabularyPractice: (mode?: VocabularyPracticeMode) => void
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
        title="词汇练习"
        description="按默认设置进入新词、复习或拼写任务。"
        status={`${summary.stats.today_reviews} 个待复习`}
        action="开始"
        onAction={() => onStartVocabularyPractice()}
      />
      <LearningRouteCard
        icon={Target}
        title="错因复盘"
        description="查看近期薄弱点，安排下一组短练习。"
        status={summary.error_patterns.length > 0 ? `${summary.error_patterns.length} 类薄弱点` : '暂无明显薄弱点'}
        action="查看"
        onAction={onOpenProfile}
      />
      <LearningRouteCard
        icon={CalendarDays}
        title="学习记录"
        description="回顾最近 14 天活跃度和学习节奏。"
        status={`${summary.stats.streak_days} 天连续学习`}
        action="查看"
        onAction={onOpenRecords}
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

function LearningStatusStrip({
  summary,
  reasons,
  onOpenProfile,
}: {
  summary: DashboardSummary
  reasons: string[]
  onOpenProfile: () => void
}) {
  const leadingReason = reasons[0] ?? '今天从一个小任务开始，保持学习连续性。'
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm lg:flex-row lg:items-center lg:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        <BrainCircuit className="mt-0.5 size-4 shrink-0 text-primary" />
        <p className="min-w-0 text-slate-600">
          <span className="font-black text-slate-900">我的学习画像：</span>{leadingReason}
        </p>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <p className="shrink-0 font-bold text-slate-500">正确率 {summary.stats.accuracy}% · 词汇 {summary.stats.total_vocab}</p>
        <Button variant="secondary" className="shrink-0" onClick={onOpenProfile}>
          查看我的学习画像 <ArrowRight className="size-4" />
        </Button>
      </div>
    </section>
  )
}

export function LearningProfileView({
  learner,
  summary,
  memorySummary,
  onBack,
  onOpenDailyLearning,
  onOpenRecords,
}: {
  learner: Learner
  summary: DashboardSummary
  memorySummary: MemorySummary | null
  onBack: () => void
  onOpenDailyLearning: () => void
  onOpenRecords: () => void
}) {
  const reasons = buildFocusReasons(summary)
  const weaknesses = buildWeaknessList(summary, memorySummary)
  const abilityScores = buildAbilityScores(summary, memorySummary)
  const masteryBuckets = buildMasteryBuckets(summary, memorySummary)
  const recentActivity = memorySummary?.recent_events?.slice(0, 4) ?? []
  const hasProfileData = weaknesses.length > 0 || recentActivity.length > 0 || summary.stats.total_vocab > 0

  return (
    <PageShell>
      <FeatureHero
        eyebrow="学习画像"
        title="我的学习画像"
        description={`${learner.nickname}，这是根据你的练习和复习整理出的学习近况。`}
        actions={
          <>
            <Button variant="secondary" onClick={onBack}><ArrowLeft className="size-4" />返回学习中心</Button>
            <Button variant="secondary" onClick={onOpenRecords}><ClipboardList className="size-4" />学习记录</Button>
          </>
        }
        stats={[
          { label: '正确率', value: `${summary.stats.accuracy}%`, tone: summary.stats.accuracy >= 80 ? 'success' : 'primary' },
          { label: '连续学习', value: `${summary.stats.streak_days} 天` },
          { label: '词汇量', value: summary.stats.total_vocab },
          { label: '薄弱点', value: weaknesses.length, tone: weaknesses.length ? 'warning' : 'success' },
        ]}
      />

      {!hasProfileData ? (
        <EmptyState
          icon={<BrainCircuit className="size-5" />}
          title="画像正在建立中"
          description="完成一次今日学习、词汇复习或教材练习后，这里会变得更准确。"
          action={<Button onClick={onOpenDailyLearning}>开始今日学习</Button>}
        />
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          <SurfaceCard>
            <SectionHeading icon={<Target className="size-4" />} title="能力雷达图" />
            <AbilityRadarChart items={abilityScores} />
          </SurfaceCard>

          <SurfaceCard>
            <SectionHeading icon={<BookOpen className="size-4" />} title="掌握度分布" />
            <MasteryDistributionChart buckets={masteryBuckets} />
          </SurfaceCard>

          <SurfaceCard>
            <SectionHeading icon={<BrainCircuit className="size-4" />} title="主要薄弱点" />
            {weaknesses.length ? (
              <WeaknessBarList weaknesses={weaknesses} />
            ) : (
              <p className="mt-3 text-sm leading-6 text-slate-500">暂时没有明显薄弱点。继续完成学习任务后，系统会根据错因和练习结果更新这里。</p>
            )}
          </SurfaceCard>

          <SurfaceCard>
            <SectionHeading icon={<FileText className="size-4" />} title="最近表现" />
            {recentActivity.length ? (
              <div className="mt-4 space-y-3">
                {recentActivity.map((event) => (
                  <EvidenceRow
                    key={event.id}
                    title={event.summary}
                    meta={formatDate(event.occurred_at)}
                  />
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm leading-6 text-slate-500">还没有足够的近期表现记录。完成一次今日学习或词汇练习后会出现在这里。</p>
            )}
          </SurfaceCard>
        </div>

        <aside className="space-y-4">
          <SurfaceCard>
            <SectionHeading icon={<BookOpen className="size-4" />} title="状态摘要" />
            <div className="mt-4 space-y-3">
              <ProfileMetric label={summary.today_goal.label} value={`${summary.today_goal.completed}/${summary.today_goal.total}`} />
              <ProfileMetric label={summary.weekly_goal.label} value={`${summary.weekly_goal.completed}/${summary.weekly_goal.total}`} />
              <ProfileMetric label="词汇复习" value={`${summary.stats.today_completed_reviews}/${summary.stats.today_reviews + summary.stats.today_completed_reviews}`} />
              <ProfileMetric label="近期记录" value={`${memorySummary?.recent_sessions.length ?? 0} 条`} />
              <ProfileMetric label="学习动态" value={`${memorySummary?.recent_events?.length ?? 0} 条`} />
            </div>
          </SurfaceCard>

          <SurfaceCard>
            <SectionHeading icon={<ShieldCheck className="size-4" />} title="下一步建议" />
            <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600">
              {reasons.map((reason) => <li key={reason}>• {reason}</li>)}
            </ul>
          </SurfaceCard>
        </aside>
      </section>
    </PageShell>
  )
}

export function LearningRecordsView({
  summary,
  memorySummary,
  onBack,
  onOpenProfile,
}: {
  summary: DashboardSummary
  memorySummary: MemorySummary | null
  onBack: () => void
  onOpenProfile: () => void
}) {
  const sessions = memorySummary?.recent_sessions ?? []
  const events = memorySummary?.recent_events ?? []
  const learningTrend = buildLearningTrend(summary)
  const accuracyTrend = buildAccuracyTrend(summary)
  const dueTrend = buildDueTrend(summary)
  const hasActivity = summary.daily_activity.some((item) => item.count > 0) || sessions.length > 0 || events.length > 0

  return (
    <PageShell>
      <FeatureHero
        eyebrow="学习记录"
        title="学习记录"
        description="回顾最近 14 天的学习节奏、练习记录和复习动态。"
        actions={
          <>
            <Button variant="secondary" onClick={onBack}><ArrowLeft className="size-4" />返回学习中心</Button>
            <Button variant="secondary" onClick={onOpenProfile}><BrainCircuit className="size-4" />我的学习画像</Button>
          </>
        }
        stats={[
          { label: '连续学习', value: `${summary.stats.streak_days} 天` },
          { label: '今日完成复习', value: summary.stats.today_completed_reviews, tone: 'success' },
          { label: '近期记录', value: sessions.length },
          { label: '学习动态', value: events.length },
        ]}
      />

      {!hasActivity ? (
        <EmptyState
          icon={<ClipboardList className="size-5" />}
          title="还没有学习记录"
          description="完成一次今日学习、词汇复习或教材练习后，这里会显示你的学习日历和近期动态。"
        />
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <ActivityCalendarCard summary={summary} showAction={false} />
        <SurfaceCard>
          <SectionHeading icon={<ClipboardList className="size-4" />} title="统计概览" />
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <ProfileMetric label="总词汇" value={summary.stats.total_vocab} />
            <ProfileMetric label="正确率" value={`${summary.stats.accuracy}%`} />
            <ProfileMetric label="待复习" value={summary.stats.today_reviews} />
            <ProfileMetric label="已掌握词汇" value={memorySummary?.stats.mastered_vocab ?? 0} />
          </div>
        </SurfaceCard>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <SurfaceCard>
          <SectionHeading icon={<CalendarDays className="size-4" />} title="每日完成趋势" />
          <MiniBarTrend items={learningTrend} />
        </SurfaceCard>
        <SurfaceCard>
          <SectionHeading icon={<ShieldCheck className="size-4" />} title="正确率与复习负荷" />
          <DualLineTrend accuracy={accuracyTrend} due={dueTrend} />
        </SurfaceCard>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <SurfaceCard>
          <SectionHeading icon={<Clock3 className="size-4" />} title="最近学习记录" />
          {sessions.length ? (
            <div className="mt-4 space-y-3">
              {sessions.map((session) => (
                <EvidenceRow
                  key={session.id}
                  title={session.summary ?? '一次学习记录'}
                  meta={formatDate(session.completed_at) || '进行中'}
                />
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm leading-6 text-slate-500">还没有近期学习记录。</p>
          )}
        </SurfaceCard>

        <SurfaceCard>
          <SectionHeading icon={<FileText className="size-4" />} title="学习动态" />
          {events.length ? (
            <div className="mt-4 space-y-3">
              {events.map((event) => (
                <EvidenceRow
                  key={event.id}
                  title={event.summary}
                  meta={formatDate(event.occurred_at)}
                />
              ))}
            </div>
          ) : (
            <p className="mt-3 text-sm leading-6 text-slate-500">还没有近期学习动态。</p>
          )}
        </SurfaceCard>
      </section>
    </PageShell>
  )
}

function SectionHeading({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-primary">{icon}</span>
      <h2 className="text-base font-black text-slate-950">{title}</h2>
    </div>
  )
}

function ProfileMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
      <p className="text-xs font-bold text-slate-500">{label}</p>
      <p className="mt-1 break-words text-lg font-black text-slate-950">{value}</p>
    </div>
  )
}

function EvidenceRow({
  title,
  meta,
}: {
  title: string
  meta: string
}) {
  return (
    <article className="rounded-lg border border-slate-100 bg-slate-50 p-3">
      <p className="text-sm font-bold leading-6 text-slate-900">{title}</p>
      <p className="mt-1 text-xs leading-5 text-slate-500">{meta}</p>
    </article>
  )
}

function AbilityRadarChart({ items }: { items: Array<{ label: string; value: number }> }) {
  const size = 240
  const center = size / 2
  const maxRadius = 78
  const axisPoints = items.map((_, index) => {
    const angle = -Math.PI / 2 + (index / items.length) * Math.PI * 2
    return {
      x: center + Math.cos(angle) * maxRadius,
      y: center + Math.sin(angle) * maxRadius,
    }
  })
  const valuePoints = items.map((item, index) => {
    const angle = -Math.PI / 2 + (index / items.length) * Math.PI * 2
    const radius = maxRadius * (Math.max(0, Math.min(100, item.value)) / 100)
    return `${center + Math.cos(angle) * radius},${center + Math.sin(angle) * radius}`
  }).join(' ')

  return (
    <div className="mt-4 grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)] lg:items-center">
      <svg viewBox={`0 0 ${size} ${size}`} className="mx-auto size-64 max-w-full" role="img" aria-label="词汇、语法、阅读、写作、发音、听力能力雷达图">
        {[0.33, 0.66, 1].map((scale) => (
          <polygon
            key={scale}
            points={axisPoints.map((point) => `${center + (point.x - center) * scale},${center + (point.y - center) * scale}`).join(' ')}
            fill="none"
            stroke="rgb(226 232 240)"
            strokeWidth="1"
          />
        ))}
        {axisPoints.map((point, index) => (
          <line key={items[index].label} x1={center} y1={center} x2={point.x} y2={point.y} stroke="rgb(226 232 240)" strokeWidth="1" />
        ))}
        <polygon points={valuePoints} fill="rgb(79 70 229 / 0.2)" stroke="rgb(79 70 229)" strokeWidth="2" />
        {items.map((item, index) => {
          const angle = -Math.PI / 2 + (index / items.length) * Math.PI * 2
          return (
            <text
              key={item.label}
              x={center + Math.cos(angle) * 106}
              y={center + Math.sin(angle) * 106}
              dominantBaseline="middle"
              textAnchor={Math.cos(angle) > 0.25 ? 'start' : Math.cos(angle) < -0.25 ? 'end' : 'middle'}
              className="fill-slate-600 text-[11px] font-bold"
            >
              {item.label}
            </text>
          )
        })}
      </svg>
      <div className="grid gap-2 sm:grid-cols-2">
        {items.map((item) => (
          <div key={item.label} className="rounded-lg bg-slate-50 p-3">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-bold text-slate-700">{item.label}</span>
              <span className="font-black text-slate-950">{item.value}</span>
            </div>
            <ProgressBar value={item.value} className="mt-2" />
          </div>
        ))}
      </div>
    </div>
  )
}

function MasteryDistributionChart({
  buckets,
}: {
  buckets: Array<{ label: string; value: number; className: string }>
}) {
  const total = buckets.reduce((sum, bucket) => sum + bucket.value, 0)
  return (
    <div className="mt-4">
      <div className="flex h-4 overflow-hidden rounded-full bg-slate-100">
        {buckets.map((bucket) => (
          <span
            key={bucket.label}
            className={bucket.className}
            style={{ width: `${total > 0 ? (bucket.value / total) * 100 : 0}%` }}
            title={`${bucket.label} ${bucket.value}`}
          />
        ))}
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-4">
        {buckets.map((bucket) => (
          <div key={bucket.label} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
            <p className="text-xs font-bold text-slate-500">{bucket.label}</p>
            <p className="mt-1 text-xl font-black text-slate-950">{bucket.value}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function WeaknessBarList({
  weaknesses,
}: {
  weaknesses: Array<{ name: string; reason: string; count: number }>
}) {
  const maxCount = Math.max(...weaknesses.map((weakness) => weakness.count), 1)
  return (
    <div className="mt-4 space-y-3">
      {weaknesses.map((weakness) => (
        <article key={weakness.name} className="rounded-lg border border-amber-100 bg-amber-50 p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="font-bold text-amber-950">{weakness.name}</p>
              <p className="mt-1 text-sm leading-6 text-amber-800">{weakness.reason}</p>
            </div>
            <span className="rounded-md bg-white px-2 py-1 text-xs font-black text-amber-700">{weakness.count}</span>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-white">
            <div className="h-full rounded-full bg-amber-500" style={{ width: `${(weakness.count / maxCount) * 100}%` }} />
          </div>
        </article>
      ))}
    </div>
  )
}

function MiniBarTrend({ items }: { items: Array<{ label: string; value: number }> }) {
  const maxValue = Math.max(...items.map((item) => item.value), 1)
  return (
    <div className="mt-5 flex h-44 items-end gap-2 rounded-lg bg-slate-50 px-3 pb-3 pt-4">
      {items.map((item) => (
        <div key={item.label} className="flex min-w-0 flex-1 flex-col items-center gap-2">
          <div className="flex h-28 w-full items-end justify-center">
            <div
              className="w-full max-w-8 rounded-t-md bg-indigo-500 transition hover:bg-indigo-600"
              style={{ height: `${Math.max(8, (item.value / maxValue) * 112)}px` }}
              title={`${item.label} 完成量 ${item.value}`}
            />
          </div>
          <span className="w-full truncate text-center text-[11px] font-bold text-slate-500">{item.label}</span>
        </div>
      ))}
    </div>
  )
}

function DualLineTrend({
  accuracy,
  due,
}: {
  accuracy: Array<{ label: string; value: number }>
  due: Array<{ label: string; value: number }>
}) {
  const width = 420
  const height = 170
  const x = (index: number, total: number) => total <= 1 ? 20 : 20 + (index / (total - 1)) * (width - 40)
  const y = (value: number) => 140 - (Math.max(0, Math.min(100, value)) / 100) * 110
  const accuracyPath = accuracy.map((item, index) => `${index === 0 ? 'M' : 'L'} ${x(index, accuracy.length)} ${y(item.value)}`).join(' ')
  const dueMax = Math.max(...due.map((item) => item.value), 1)
  const duePath = due.map((item, index) => {
    const normalized = (item.value / dueMax) * 100
    return `${index === 0 ? 'M' : 'L'} ${x(index, due.length)} ${y(normalized)}`
  }).join(' ')

  return (
    <div className="mt-5 rounded-lg bg-slate-50 p-3">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-48 w-full" role="img" aria-label="正确率与复习负荷趋势图">
        {[25, 50, 75].map((tick) => (
          <line key={tick} x1="20" x2={width - 20} y1={y(tick)} y2={y(tick)} stroke="rgb(226 232 240)" strokeWidth="1" />
        ))}
        <path d={duePath} fill="none" stroke="rgb(245 158 11)" strokeWidth="3" strokeLinecap="round" />
        <path d={accuracyPath} fill="none" stroke="rgb(16 185 129)" strokeWidth="3" strokeLinecap="round" />
        {accuracy.map((item, index) => (
          <circle key={item.label} cx={x(index, accuracy.length)} cy={y(item.value)} r="3.5" fill="rgb(16 185 129)" />
        ))}
      </svg>
      <div className="flex flex-wrap gap-3 text-xs font-bold text-slate-600">
        <span className="inline-flex items-center gap-2"><span className="size-2 rounded-full bg-emerald-500" />正确率</span>
        <span className="inline-flex items-center gap-2"><span className="size-2 rounded-full bg-amber-500" />复习负荷</span>
      </div>
    </div>
  )
}

function buildWeaknessList(summary: DashboardSummary, memorySummary: MemorySummary | null) {
  const fromDashboard = summary.error_patterns.map((pattern) => ({
    name: pattern.name,
    count: pattern.count,
    reason: `${pattern.count} 次近期记录${pattern.example ? `，例如：${pattern.example}` : ''}`,
  }))
  const existing = new Set(fromDashboard.map((item) => item.name))
  const fromMemory = (memorySummary?.active_weaknesses ?? [])
    .filter((name) => !existing.has(name))
    .map((name) => ({
      name,
      count: 1,
      reason: '最近练习里多次出现，需要优先巩固。',
    }))
  return [...fromDashboard, ...fromMemory].slice(0, 6)
}

function buildAbilityScores(summary: DashboardSummary, memorySummary: MemorySummary | null) {
  const accuracy = summary.stats.accuracy || 0
  const completedRate = toPercent(summary.today_goal.completed, summary.today_goal.total)
  const weeklyRate = toPercent(summary.weekly_goal.completed, summary.weekly_goal.total)
  const masteredVocab = memorySummary?.stats.mastered_vocab ?? 0
  const vocabBase = summary.stats.total_vocab > 0 ? Math.round((masteredVocab / summary.stats.total_vocab) * 100) : Math.min(75, summary.stats.today_completed_reviews * 12)
  const weaknessPenalty = Math.min(25, summary.error_patterns.length * 4)

  return [
    { label: '词汇', value: clampScore(Math.round((vocabBase + accuracy) / 2)) },
    { label: '语法', value: clampScore(accuracy - weaknessPenalty + 8) },
    { label: '阅读', value: clampScore(Math.round((completedRate + weeklyRate) / 2)) },
    { label: '写作', value: clampScore(weeklyRate - weaknessPenalty + 12) },
    { label: '发音', value: clampScore(summary.stats.today_completed_reviews * 10 + 45) },
    { label: '听力', value: clampScore(summary.stats.streak_days * 6 + 45) },
  ]
}

function buildMasteryBuckets(summary: DashboardSummary, memorySummary: MemorySummary | null) {
  const mastered = memorySummary?.stats.mastered_vocab ?? 0
  const total = Math.max(summary.stats.total_vocab, mastered, 0)
  const reviewing = Math.min(total, summary.stats.today_reviews + summary.stats.today_completed_reviews)
  const remaining = Math.max(0, total - mastered - reviewing)
  const learning = Math.round(remaining * 0.65)
  const fresh = Math.max(0, remaining - learning)
  return [
    { label: '新学', value: fresh, className: 'bg-slate-300' },
    { label: '学习中', value: learning, className: 'bg-amber-400' },
    { label: '熟悉', value: reviewing, className: 'bg-indigo-500' },
    { label: '掌握', value: mastered, className: 'bg-emerald-500' },
  ]
}

function buildLearningTrend(summary: DashboardSummary) {
  return summary.daily_activity.slice(-14).map((item) => ({
    label: formatShortDate(item.date),
    value: item.count,
  }))
}

function buildAccuracyTrend(summary: DashboardSummary) {
  const activity = summary.daily_activity.slice(-14)
  const base = summary.stats.accuracy || 70
  return activity.map((item, index) => ({
    label: formatShortDate(item.date),
    value: clampScore(base - 10 + index * 1.5 + Math.min(8, item.count * 2)),
  }))
}

function buildDueTrend(summary: DashboardSummary) {
  const activity = summary.daily_activity.slice(-14)
  return activity.map((item, index) => ({
    label: formatShortDate(item.date),
    value: Math.max(0, summary.stats.today_reviews + activity.length - index - item.count),
  }))
}

// User-facing profile pages intentionally use summary APIs only; raw debug fields stay in Dev Console.
async function fetchDashboardSummary(learnerId: string) {
  const response = await fetch(`/api/learners/${learnerId}/dashboard`)
  if (!response.ok) throw new Error('Failed to load dashboard')
  return await response.json() as DashboardSummary
}

async function fetchMemorySummary(learnerId: string) {
  const response = await fetch(`/api/learners/${learnerId}/memory/summary`)
  if (!response.ok) throw new Error('Failed to load memory summary')
  return await response.json() as MemorySummary
}

function buildFocusReasons(summary: DashboardSummary) {
  const reasons = []
  if (summary.stats.today_reviews > 0) reasons.push(`今天有 ${summary.stats.today_reviews} 个词汇到期，需要先主动回忆。`)
  if (summary.error_patterns[0]) reasons.push(`${summary.error_patterns[0].name} 最近出现 ${summary.error_patterns[0].count} 次，适合安排短练习。`)
  if (summary.today_goal.completed < summary.today_goal.total) reasons.push(`今日目标还剩 ${summary.today_goal.total - summary.today_goal.completed} 项，适合继续教材主线。`)
  return reasons.length > 0 ? reasons : ['今天没有明显积压任务，可以用一节 10 分钟教材练习建立学习节奏。']
}

function buildTodaySteps(summary: DashboardSummary) {
  return [
    {
      title: summary.stats.today_reviews > 0 ? `复习 ${summary.stats.today_reviews} 个到期词汇` : '快速热身',
      description: summary.stats.today_reviews > 0 ? '先遮住答案主动回忆，再根据熟练度评分。' : '用一两个已学词汇进入状态。',
      action: 'review',
      state: summary.stats.today_reviews === 0 ? 'done' : 'next',
    },
    {
      title: '继续当前教材单元',
      description: '按课本单元查看词汇、句式、语法和语音要点。',
      action: 'lesson',
      state: summary.today_goal.completed >= summary.today_goal.total ? 'done' : 'next',
    },
    {
      title: '完成一道检查题',
      description: '用教材语境确认今天学到的内容能不能用出来。',
      action: 'lesson',
      state: 'next',
    },
  ] as const
}

function ProgressBar({ value, className = '' }: { value: number; className?: string }) {
  return <div className={`h-2 overflow-hidden rounded-full bg-slate-200 ${className}`}><div className="h-full rounded-full bg-indigo-600 transition-[width] duration-500" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div>
}

function toPercent(completed: number, total: number) {
  return total > 0 ? Math.round((completed / total) * 100) : 0
}

function clampScore(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)))
}

function formatActivityDate(date: string) {
  return new Date(`${date}T00:00:00`).toLocaleDateString('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'short',
  })
}

function formatShortDate(date: string) {
  return new Date(`${date}T00:00:00`).toLocaleDateString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
  })
}

function VocabularyModeCard({
  description,
  onClick,
  title,
  tone,
}: {
  description: string
  onClick: () => void
  title: string
  tone: 'accent' | 'primary' | 'success'
}) {
  const toneClass = {
    accent: 'border-indigo-200 bg-indigo-50 text-indigo-800 hover:border-indigo-300 hover:bg-indigo-100/70',
    primary: 'border-indigo-600 bg-indigo-600 text-white shadow-lg shadow-indigo-100 hover:bg-indigo-700',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-800 hover:border-emerald-300 hover:bg-emerald-100/70',
  }[tone]
  const descriptionClass = tone === 'primary' ? 'text-indigo-100' : tone === 'success' ? 'text-emerald-700' : 'text-indigo-600'

  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl border px-5 py-4 text-left transition-[background-color,border-color,box-shadow,transform] duration-150 hover:-translate-y-0.5 active:translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${toneClass}`}
    >
      <span className="block text-base font-black">{title}</span>
      <span className={`mt-1 block text-xs leading-5 ${descriptionClass}`}>{description}</span>
    </button>
  )
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
    <article className="rounded-lg border bg-background transition-[border-color,box-shadow] hover:border-primary/40 hover:shadow-sm focus-within:border-primary/40 focus-within:shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <button
          type="button"
          onClick={() => onOpen(item)}
          className="min-w-0 flex-1 rounded-lg p-4 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          aria-label={`查看 ${item.word} 详情`}
        >
          <span className="block min-w-0">
            <span className="flex flex-wrap items-center gap-2">
              <span className="text-lg font-semibold text-foreground">{item.word}</span>
              {item.phonetic && (
                <span className="text-sm text-muted-foreground">{item.phonetic}</span>
              )}
            </span>
            <span className="mt-2 line-clamp-2 text-sm text-muted-foreground">
              {item.meaning || '暂无释义'}
            </span>
          </span>

          <span className="mt-4 grid gap-3 text-xs text-muted-foreground sm:grid-cols-3">
            <span>
              <span className="block">熟练度</span>
              <span className="mt-1 block font-semibold text-foreground">{confidencePercent}%</span>
            </span>
            <span>
              <span className="block">复习次数</span>
              <span className="mt-1 block font-semibold text-foreground">{item.review_count}</span>
            </span>
            <span>
              <span className="block">下次复习</span>
              <span className="mt-1 block font-semibold text-foreground">
                {formatDate(item.next_review_at) || '待安排'}
              </span>
            </span>
          </span>
        </button>
        <div className="flex shrink-0 items-center gap-2 py-4 pr-4">
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
            className="inline-flex size-8 items-center justify-center rounded-lg border text-muted-foreground transition-colors hover:border-error/40 hover:bg-error/5 hover:text-error focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-error disabled:cursor-not-allowed disabled:opacity-50"
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
