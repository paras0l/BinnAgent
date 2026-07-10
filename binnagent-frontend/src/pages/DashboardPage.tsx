import { lazy, Suspense, useCallback, useEffect, useId, useMemo, useState, type ReactNode } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  BrainCircuit,
  CalendarDays,
  ClipboardList,
  Clock3,
  FileText,
  FlaskConical,
  HelpCircle,
  MessageCircle,
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
import { Select } from '@/components/ui/Select'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import type { DashboardSummary, Learner, LearnerProfile, MemorySummary, VocabularyListItem } from '@/types'
import { useToast } from '@/hooks/useToast'
import { useFocusTrap } from '@/hooks/useFocusTrap'
import type { VocabularyPracticeMode } from '@/pages/VocabularyPracticePage'
import type { ExpressionLabSourceSeed } from '@/pages/ExpressionLabPage'
import {
  listGroupLearningSignals,
  listGroupLearningSources,
  type GroupLearningSource,
} from '@/services/groupLearningApi'
import {
  CURRENT_LEVEL_OPTIONS,
  LEARNING_GOAL_OPTIONS,
  LEVEL_STANDARD_NOTES,
  currentLevelLabel,
  learningGoalLabel,
} from '@/utils/learnerProfile'
import { buildTodaySteps } from '@/utils/dashboardLearningFlow'

const VOCABULARY_PAGE_SIZE = 12

const GroupLearningSignalsPage = lazy(() =>
  import('@/pages/GroupLearningSignalsPage').then((module) => ({ default: module.GroupLearningSignalsPage }))
)

const VocabularyPracticePage = lazy(() =>
  import('@/pages/VocabularyPracticePage').then((module) => ({ default: module.VocabularyPracticePage }))
)

type GroupLearningCardState = 'not_configured' | 'paused' | 'unbound' | 'pending_sync' | 'active'

interface GroupLearningCardSummary {
  state: GroupLearningCardState
  sourceCount: number
  participantCount: number
  pendingCount: number
  latestSyncLabel: string
}

const EMPTY_GROUP_LEARNING_SUMMARY: GroupLearningCardSummary = {
  state: 'not_configured',
  sourceCount: 0,
  participantCount: 0,
  pendingCount: 0,
  latestSyncLabel: '尚未同步',
}

export type DashboardWorkspace = 'home' | 'vocabulary' | 'profile' | 'records' | 'group-signals'

interface DashboardPageProps {
  learner: Learner
  learnerProfile?: LearnerProfile | null
  initialWorkspace?: DashboardWorkspace
  initialVocabularyListOpen?: boolean
  onOpenAiConversation: () => void
  onOpenDailyLearning: () => void
  onOpenGroupLearningSettings: () => void
  onOpenExpressionLab: (options: { sourceSignal?: ExpressionLabSourceSeed }) => void
  onProfileUpdate?: (patch: Partial<LearnerProfile>) => void
  onStartVocabularyPractice: (mode?: VocabularyPracticeMode) => void
}

export function DashboardPage({
  learner,
  learnerProfile,
  initialVocabularyListOpen = false,
  initialWorkspace = 'home',
  onOpenAiConversation,
  onOpenDailyLearning,
  onOpenGroupLearningSettings,
  onOpenExpressionLab,
  onProfileUpdate,
  onStartVocabularyPractice,
}: DashboardPageProps) {
  const { showToast } = useToast()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [memorySummary, setMemorySummary] = useState<MemorySummary | null>(null)
  const [groupLearningSummary, setGroupLearningSummary] = useState<GroupLearningCardSummary>(EMPTY_GROUP_LEARNING_SUMMARY)
  const [currentVocabIndex, setCurrentVocabIndex] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [isReviewing, setIsReviewing] = useState(false)
  const [isAddingWord, setIsAddingWord] = useState(false)
  const [isVocabListOpen, setIsVocabListOpen] = useState(initialVocabularyListOpen)
  const [isLoadingVocabulary, setIsLoadingVocabulary] = useState(false)
  const [deletingWordId, setDeletingWordId] = useState<string | null>(null)
  const [wordPendingDelete, setWordPendingDelete] = useState<VocabularyListItem | null>(null)
  const [vocabularyItems, setVocabularyItems] = useState<VocabularyListItem[]>([])
  const [vocabPage, setVocabPage] = useState(1)
  const [vocabQuery, setVocabQuery] = useState('')
  const [newWord, setNewWord] = useState('')
  const [newPhonetic, setNewPhonetic] = useState('')
  const [newMeaning, setNewMeaning] = useState('')
  const [activeWorkspace, setActiveWorkspace] = useState<DashboardWorkspace>(initialWorkspace)
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
      fetchGroupLearningCardSummary(learner.id)
        .then(setGroupLearningSummary)
        .catch((error: unknown) => {
          console.warn('Group learning summary unavailable:', error)
          setGroupLearningSummary(EMPTY_GROUP_LEARNING_SUMMARY)
        })
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
  const vocabularyTotalPages = Math.max(1, Math.ceil(filteredVocabulary.length / VOCABULARY_PAGE_SIZE))
  const safeVocabularyPage = Math.min(vocabPage, vocabularyTotalPages)
  const pagedVocabulary = useMemo(() => {
    const start = (safeVocabularyPage - 1) * VOCABULARY_PAGE_SIZE
    return filteredVocabulary.slice(start, start + VOCABULARY_PAGE_SIZE)
  }, [filteredVocabulary, safeVocabularyPage])

  const handleOpenVocabularyList = () => {
    setIsVocabListOpen(true)
    setVocabPage(1)
    void loadVocabularyList()
  }

  const handleOpenVocabularyManager = () => {
    setActiveWorkspace('vocabulary')
    handleOpenVocabularyList()
  }

  const handleOpenVocabularyTraining = () => {
    setIsVocabListOpen(false)
    setActiveWorkspace('vocabulary')
  }

  useEffect(() => {
    if (initialWorkspace === 'vocabulary' && initialVocabularyListOpen) {
      const timer = window.setTimeout(() => void loadVocabularyList(), 0)
      return () => window.clearTimeout(timer)
    }
  }, [initialVocabularyListOpen, initialWorkspace, loadVocabularyList])

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
      <Suspense fallback={<LoadingState title="正在打开词卡" description="正在加载单词详情..." />}>
        <VocabularyPracticePage
          learner={learner}
          initialMode="new"
          readonlyItemId={detailItemId}
          readonlyBackLabel="返回词汇本"
          sourceLabel="我的词汇本"
          onExit={() => setDetailItemId(null)}
        />
      </Suspense>
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
        onOpenAiConversation={onOpenAiConversation}
        onOpenDailyLearning={onOpenDailyLearning}
        onOpenVocabularyManager={handleOpenVocabularyManager}
        onOpenVocabularyTraining={handleOpenVocabularyTraining}
        onOpenProfile={() => setActiveWorkspace('profile')}
        onOpenRecords={() => setActiveWorkspace('records')}
        onOpenGroupSignals={() => setActiveWorkspace('group-signals')}
        onOpenExpressionLab={() => onOpenExpressionLab({})}
        onStartVocabularyPractice={onStartVocabularyPractice}
        groupLearningSummary={groupLearningSummary}
      />
    )
  }

  if (activeWorkspace === 'profile') {
    return (
      <LearningProfileView
        learner={learner}
        learnerProfile={learnerProfile}
        summary={summary}
        memorySummary={memorySummary}
        onBack={() => setActiveWorkspace('home')}
        onOpenDailyLearning={onOpenDailyLearning}
        onOpenRecords={() => setActiveWorkspace('records')}
        onProfileUpdate={onProfileUpdate}
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

  if (activeWorkspace === 'group-signals') {
    return (
      <Suspense fallback={<LoadingState title="正在打开群聊学习线索" description="正在加载候选表达和复习线索..." />}>
        <GroupLearningSignalsPage
          learner={learner}
          onBack={() => setActiveWorkspace('home')}
          onOpenSettings={onOpenGroupLearningSettings}
          onOpenExpressionLab={onOpenExpressionLab}
        />
      </Suspense>
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
                  onChange={(event) => {
                    setVocabQuery(event.target.value)
                    setVocabPage(1)
                  }}
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
              <div className="space-y-3">
                <div className="max-h-[min(64vh,760px)] overflow-y-auto rounded-xl border border-slate-100 bg-slate-50/60 p-2">
                  <div className="grid gap-3 md:grid-cols-2">
                    {pagedVocabulary.map((item) => (
                      <VocabularyListRow
                        key={item.id}
                        item={item}
                        isDeleting={deletingWordId === item.id}
                        onDelete={setWordPendingDelete}
                        onOpen={(selected) => setDetailItemId(selected.id)}
                      />
                    ))}
                  </div>
                </div>
                <VocabularyListPagination
                  currentPage={safeVocabularyPage}
                  pageSize={VOCABULARY_PAGE_SIZE}
                  totalItems={filteredVocabulary.length}
                  totalPages={vocabularyTotalPages}
                  onPageChange={setVocabPage}
                />
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
  groupLearningSummary,
  onOpenAiConversation,
  onOpenDailyLearning,
  onOpenVocabularyManager,
  onOpenVocabularyTraining,
  onOpenProfile,
  onOpenRecords,
  onOpenGroupSignals,
  onOpenExpressionLab,
  onStartVocabularyPractice,
}: {
  learnerName: string
  summary: DashboardSummary
  groupLearningSummary: GroupLearningCardSummary
  onOpenAiConversation: () => void
  onOpenDailyLearning: () => void
  onOpenVocabularyManager: () => void
  onOpenVocabularyTraining: () => void
  onOpenProfile: () => void
  onOpenRecords: () => void
  onOpenGroupSignals: () => void
  onOpenExpressionLab: () => void
  onStartVocabularyPractice: (mode?: VocabularyPracticeMode) => void
}) {
  const todayPercent = toPercent(summary.today_goal.completed, summary.today_goal.total)
  const dueCount = summary.stats.today_reviews
  const focusReasons = buildFocusReasons(summary)
  const nextActionLabel = dueCount > 0 ? `先复习 ${dueCount} 个词` : '开始今日学习'
  const routeStatus = todayPercent >= 100 ? '今日任务已收口' : dueCount > 0 ? '先清复习，再进教材' : '可以直接进入教材'

  return (
    <PageShell>
      <section className="relative overflow-hidden rounded-[1.75rem] border border-slate-200 bg-[linear-gradient(135deg,#ffffff_0%,#f8fafc_54%,#eef2ff_100%)] px-5 py-6 shadow-[0_18px_48px_rgba(15,23,42,0.08)] ring-1 ring-white/80 sm:px-7 lg:px-8">
        <div className="absolute inset-x-0 top-0 h-1 bg-[linear-gradient(90deg,#6366f1,#22d3ee,#22c55e)]" />
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-stretch">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-full border border-indigo-100 bg-white/80 px-3 py-1 text-xs font-black text-primary shadow-sm">
                <span className="size-1.5 rounded-full bg-primary" />
                学习中心
              </span>
              <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-black text-white shadow-sm">{routeStatus}</span>
            </div>
            <h1 className="mt-4 text-3xl font-black leading-tight tracking-tight text-slate-950 sm:text-4xl">
              {learnerName}，今天从这里开始
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-500">
              先完成当前最该做的一步，再继续教材。系统会按复习、学习、检查题、AI 对话的顺序带你往前走。
            </p>
          </div>
          <div className="rounded-2xl border border-white/80 bg-white/85 p-4 shadow-[0_10px_30px_rgba(15,23,42,0.08)] backdrop-blur">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs font-black uppercase text-slate-500">今日进度</p>
                <p className="mt-1 text-2xl font-black text-slate-950">{todayPercent}%</p>
              </div>
              <span className="rounded-xl bg-indigo-50 px-3 py-2 text-xs font-black text-indigo-700">{summary.today_goal.completed}/{summary.today_goal.total}</span>
            </div>
            <ProgressBar value={todayPercent} className="mt-4 bg-slate-100" />
            <div className="mt-4 grid gap-2">
              <Button className="justify-between shadow-[0_10px_24px_rgba(99,102,241,0.22)]" onClick={dueCount > 0 ? () => onStartVocabularyPractice('review') : onOpenDailyLearning}>
                {nextActionLabel}<ArrowRight className="size-4" />
              </Button>
              {dueCount > 0 ? (
                <Button variant="secondary" className="justify-between" onClick={onOpenDailyLearning}>
                  进入教材学习<ArrowRight className="size-4" />
                </Button>
              ) : null}
            </div>
          </div>
        </div>

        <div className="mt-6 grid gap-3 border-t border-slate-100 pt-5 sm:grid-cols-3">
          <LearningPulseItem label={summary.today_goal.label} value={`${summary.today_goal.completed}/${summary.today_goal.total}`} detail={`${todayPercent}%`} tone={todayPercent >= 100 ? 'success' : 'primary'} />
          <LearningPulseItem label="待复习" value={dueCount} detail={dueCount > 0 ? '建议先清' : '无积压'} tone={dueCount > 0 ? 'warning' : 'success'} />
          <LearningPulseItem label="连续学习" value={`${summary.stats.streak_days} 天`} detail={`${summary.weekly_goal.completed}/${summary.weekly_goal.total} 本周`} tone="neutral" />
        </div>
      </section>

      <section className="grid items-stretch gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <TodayLearningFlow
          reasons={focusReasons}
          summary={summary}
          onOpenAiConversation={onOpenAiConversation}
          onOpenDailyLearning={onOpenDailyLearning}
          onStartVocabularyPractice={onStartVocabularyPractice}
        />
        <LearningSideRail
          summary={summary}
          groupLearningSummary={groupLearningSummary}
          onOpenGroupSignals={onOpenGroupSignals}
          onOpenExpressionLab={onOpenExpressionLab}
          onOpenVocabularyManager={onOpenVocabularyManager}
          onOpenVocabularyTraining={onOpenVocabularyTraining}
          onOpenProfile={onOpenProfile}
          onOpenRecords={onOpenRecords}
        />
      </section>
    </PageShell>
  )
}

function TodayLearningFlow({
  reasons,
  summary,
  onOpenAiConversation,
  onOpenDailyLearning,
  onStartVocabularyPractice,
}: {
  reasons: string[]
  summary: DashboardSummary
  onOpenAiConversation: () => void
  onOpenDailyLearning: () => void
  onStartVocabularyPractice: (mode?: VocabularyPracticeMode) => void
}) {
  const steps = buildTodaySteps(summary)
  return (
    <section className="h-full rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-[0_12px_34px_rgba(15,23,42,0.06)] sm:p-6">
      <div>
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-black uppercase text-primary">
            <Clock3 className="size-3.5" />
            今日学习流
          </p>
          <h2 className="mt-2 text-2xl font-black text-slate-950">按顺序完成，不用挑入口</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            建议 20-25 分钟。按复习、教材、检查题、AI 对话推进，今天只完成一组清晰任务。
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-3">
        {steps.map((step, index) => (
          <button
            key={step.title}
            type="button"
            onClick={
              step.action === 'review'
                ? () => onStartVocabularyPractice('review')
                : step.action === 'chat'
                  ? onOpenAiConversation
                  : onOpenDailyLearning
            }
            className={`group grid grid-cols-[42px_minmax(0,1fr)_auto] items-center gap-3 rounded-2xl border px-4 py-3.5 text-left transition hover:-translate-y-0.5 hover:shadow-[0_12px_30px_rgba(15,23,42,0.08)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
              step.state === 'done'
                ? 'border-emerald-100 bg-emerald-50/50'
                : index === 0
                  ? 'border-indigo-200 bg-[linear-gradient(135deg,#ffffff,#eef2ff)]'
                  : 'border-slate-200 bg-white hover:border-primary/30'
            }`}
          >
            <span className={`flex size-10 items-center justify-center rounded-xl text-sm font-black shadow-sm ${
              step.state === 'done' ? 'bg-emerald-100 text-emerald-700' : index === 0 ? 'bg-primary text-primary-foreground' : 'bg-slate-100 text-slate-600'
            }`}>
              {step.state === 'done' ? '✓' : index + 1}
            </span>
            <span className="min-w-0">
              <span className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-black text-slate-950">{step.title}</span>
                {step.badge ? <span className="rounded-full bg-white px-2.5 py-0.5 text-[11px] font-black text-slate-500 shadow-sm ring-1 ring-slate-200">{step.badge}</span> : null}
              </span>
              <span className="mt-1 block text-xs leading-5 text-slate-500">{step.description}</span>
            </span>
            <ArrowRight className="size-4 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-primary" />
          </button>
        ))}
      </div>

      <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm leading-6 text-slate-600">
        <p className="flex items-center gap-2 text-xs font-black uppercase text-slate-500">
          <ShieldCheck className="size-3.5 text-primary" />
          为什么现在这样排
        </p>
        <ul className="mt-2 grid gap-2 sm:grid-cols-2">
          {reasons.slice(0, 2).map((reason) => <li key={reason} className="rounded-xl bg-white px-3 py-2 shadow-sm">{reason}</li>)}
        </ul>
      </div>
    </section>
  )
}

function LearningSideRail({
  summary,
  groupLearningSummary,
  onOpenGroupSignals,
  onOpenExpressionLab,
  onOpenVocabularyManager,
  onOpenVocabularyTraining,
  onOpenProfile,
  onOpenRecords,
}: {
  summary: DashboardSummary
  groupLearningSummary: GroupLearningCardSummary
  onOpenGroupSignals: () => void
  onOpenExpressionLab: () => void
  onOpenVocabularyManager: () => void
  onOpenVocabularyTraining: () => void
  onOpenProfile: () => void
  onOpenRecords: () => void
}) {
  const latestActivity = summary.daily_activity.slice(-7)
  const maxLearningAmount = Math.max(...latestActivity.map((item) => item.count), 1)
  const groupCard = groupLearningCardCopy(groupLearningSummary)

  return (
    <aside className="flex h-full flex-col gap-4">
      <section className="rounded-[1.35rem] border border-slate-200 bg-white p-4 shadow-[0_10px_28px_rgba(15,23,42,0.05)]">
        <div className="flex items-center justify-between gap-3">
          <SectionHeading icon={<CalendarDays className="size-4" />} title="最近 7 天" />
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-black text-slate-600">{summary.stats.streak_days} 天连续</span>
        </div>
        <div className="mt-4 grid grid-cols-7 gap-2" aria-label="最近 7 天学习活跃度">
          {latestActivity.map((item) => {
            const intensity = item.count === 0 ? 0 : 0.18 + (item.count / maxLearningAmount) * 0.82
            return (
              <div
                key={item.date}
                className="aspect-square rounded-[4px] bg-slate-100 ring-1 ring-inset ring-slate-200/70"
                style={item.count === 0 ? undefined : { backgroundColor: `rgb(79 70 229 / ${intensity.toFixed(2)})` }}
                title={`${formatActivityDate(item.date)}，学习量 ${item.count}`}
              />
            )
          })}
        </div>
      </section>

      <section className="flex flex-1 flex-col rounded-[1.35rem] border border-slate-200 bg-white p-4 shadow-[0_10px_28px_rgba(15,23,42,0.05)]">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm font-black text-slate-950">辅助入口</p>
          <span className="text-xs font-bold text-slate-400">Tools</span>
        </div>
        <div className="mt-3 grid flex-1 content-start gap-2">
          <button
            type="button"
            onClick={onOpenExpressionLab}
            className="rounded-2xl border border-violet-200 bg-[linear-gradient(135deg,#f5f3ff,#ffffff_55%,#eef2ff)] p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-violet-300 hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            <span className="flex items-start justify-between gap-3">
              <span className="min-w-0">
                <span className="flex items-center gap-2 text-base font-black text-slate-950"><FlaskConical className="size-4 text-violet-600" />英语表达实验室</span>
                <span className="mt-2 block text-xs leading-5 text-slate-600">把不会说、写不准或想迁移的表达，变成比较、讲解和小练习。</span>
              </span>
              {groupLearningSummary.pendingCount > 0 ? <span className="rounded-full bg-violet-600 px-2.5 py-1 text-xs font-black text-white">{groupLearningSummary.pendingCount}</span> : null}
            </span>
            <span className="mt-4 flex items-center justify-between gap-3"><span className="text-xs font-bold text-slate-500">{groupLearningSummary.pendingCount > 0 ? `继续处理 ${groupLearningSummary.pendingCount} 条待学习线索` : '也可以手动输入表达'}</span><span className="inline-flex items-center gap-1 text-xs font-black text-violet-700">打开实验室<ArrowRight className="size-3.5" /></span></span>
          </button>
          <button
            type="button"
            onClick={onOpenGroupSignals}
            className="rounded-2xl border border-indigo-200 bg-[linear-gradient(135deg,#eef2ff,#f8fafc_55%,#f0f9ff)] p-4 text-left shadow-sm ring-1 ring-white/70 transition hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            <span className="flex items-start justify-between gap-3">
              <span className="min-w-0">
                <span className="flex items-center gap-2 text-base font-black text-slate-950">
                  <MessageCircle className="size-4 text-primary" />
                  群聊学习线索
                </span>
                <span className="mt-2 block text-xs leading-5 text-slate-600">
                  {groupCard.description}
                </span>
              </span>
              <span className={`rounded-full px-2.5 py-1 text-xs font-black ${groupCard.badgeClass}`}>
                {groupLearningSummary.pendingCount}
              </span>
            </span>
            <span className="mt-4 flex items-center justify-between gap-3">
              <span className="text-xs font-bold text-slate-500">{groupCard.meta}</span>
              <span className="inline-flex items-center gap-1 text-xs font-black text-primary">
                查看线索<ArrowRight className="size-3.5" />
              </span>
            </span>
          </button>
          <SideRailLink icon={<BookOpen className="size-4" />} label="词汇训练" detail="选择新词、复习或拼写" onClick={onOpenVocabularyTraining} />
          <SideRailLink icon={<Target className="size-4" />} label="词汇本管理" detail={`${summary.stats.total_vocab} 个词`} onClick={onOpenVocabularyManager} />
          <SideRailLink icon={<BrainCircuit className="size-4" />} label="学习画像" detail={`正确率 ${summary.stats.accuracy}%`} onClick={onOpenProfile} />
          <SideRailLink icon={<ClipboardList className="size-4" />} label="学习记录" detail="查看最近表现" onClick={onOpenRecords} />
        </div>
      </section>
    </aside>
  )
}

function SideRailLink({
  detail,
  icon,
  label,
  onClick,
}: {
  detail: string
  icon: ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-primary/30 hover:bg-slate-50 hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
    >
      <span className="flex min-w-0 items-center gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600 transition group-hover:bg-indigo-50 group-hover:text-primary">
          {icon}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-sm font-black text-slate-900">{label}</span>
          <span className="mt-0.5 block truncate text-xs font-medium text-slate-500">{detail}</span>
        </span>
      </span>
      <ArrowRight className="size-4 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-primary" />
    </button>
  )
}

function LearningPulseItem({
  detail,
  label,
  tone,
  value,
}: {
  detail: string
  label: string
  tone: 'neutral' | 'primary' | 'success' | 'warning'
  value: string | number
}) {
  const toneClass = {
    neutral: {
      badge: 'bg-slate-100 text-slate-600',
      bar: 'bg-slate-300',
    },
    primary: {
      badge: 'bg-indigo-50 text-indigo-700',
      bar: 'bg-indigo-500',
    },
    success: {
      badge: 'bg-emerald-50 text-emerald-700',
      bar: 'bg-emerald-500',
    },
    warning: {
      badge: 'bg-amber-50 text-amber-700',
      bar: 'bg-amber-500',
    },
  }[tone]

  return (
    <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white/85 px-4 py-3 shadow-sm">
      <span className={`absolute inset-x-0 top-0 h-0.5 ${toneClass.bar}`} />
      <p className="text-xs font-bold text-slate-500">{label}</p>
      <div className="mt-2 flex items-end justify-between gap-3">
        <p className="text-2xl font-black text-slate-950">{value}</p>
        <span className={`rounded-full px-2.5 py-1 text-xs font-black ${toneClass.badge}`}>{detail}</span>
      </div>
    </div>
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

export function LearningProfileView({
  learner,
  learnerProfile,
  summary,
  memorySummary,
  onBack,
  onOpenDailyLearning,
  onOpenRecords,
  onProfileUpdate = () => {},
}: {
  learner: Learner
  learnerProfile?: LearnerProfile | null
  summary: DashboardSummary
  memorySummary: MemorySummary | null
  onBack: () => void
  onOpenDailyLearning: () => void
  onOpenRecords: () => void
  onProfileUpdate?: (patch: Partial<LearnerProfile>) => void
}) {
  const [isLevelInfoOpen, setIsLevelInfoOpen] = useState(false)
  const reasons = buildFocusReasons(summary)
  const weaknesses = buildWeaknessList(summary, memorySummary)
  const abilityScores = buildAbilityScores(summary)
  const masteryBuckets = buildMasteryBuckets(summary)
  const recentActivity = memorySummary?.recent_events?.slice(0, 4) ?? []
  const hasMasteryData = masteryBuckets.some((bucket) => bucket.value > 0)
  const hasProfileData = weaknesses.length > 0 || recentActivity.length > 0 || abilityScores.length > 0 || hasMasteryData

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

      <ProfileSettingsCard
        learnerProfile={learnerProfile}
        onOpenLevelInfo={() => setIsLevelInfoOpen(true)}
        onProfileUpdate={onProfileUpdate}
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
            {abilityScores.length ? (
              <AbilityRadarChart items={abilityScores} />
            ) : (
              <p className="mt-3 text-sm leading-6 text-slate-500">还没有足够的能力证据。完成词汇复习、教材练习或专项练习后，这里会展示真实能力分。</p>
            )}
          </SurfaceCard>

          <SurfaceCard>
            <SectionHeading icon={<BookOpen className="size-4" />} title="掌握度分布" />
            {hasMasteryData ? (
              <MasteryDistributionChart buckets={masteryBuckets} />
            ) : (
              <p className="mt-3 text-sm leading-6 text-slate-500">还没有掌握度记录。开始学习教材知识点或加入词汇本后，这里会按真实掌握度分组。</p>
            )}
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
      <LevelStandardsDialog open={isLevelInfoOpen} onClose={() => setIsLevelInfoOpen(false)} />
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

function ProfileSettingsCard({
  learnerProfile,
  onOpenLevelInfo,
  onProfileUpdate,
}: {
  learnerProfile?: LearnerProfile | null
  onOpenLevelInfo: () => void
  onProfileUpdate: (patch: Partial<LearnerProfile>) => void
}) {
  return (
    <SurfaceCard>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <SectionHeading icon={<BrainCircuit className="size-4" />} title="目标与水平" />
        <div className="flex flex-wrap gap-2 text-xs font-bold text-slate-500">
          <span className="rounded-lg bg-slate-100 px-2.5 py-1">
            目标：{learningGoalLabel(learnerProfile?.target_exam)}
          </span>
          <span className="rounded-lg bg-slate-100 px-2.5 py-1">
            水平：{currentLevelLabel(learnerProfile?.current_level)}
          </span>
        </div>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-500">
        这两项会进入用户画像，后续语法、词汇、写作和对话 prompt 会按目标和当前水平调整。
      </p>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <ProfileSelectRow
          label="学习目标"
          name="profile_learning_goal"
          value={learnerProfile?.target_exam ?? ''}
          options={LEARNING_GOAL_OPTIONS}
          placeholder="未设置"
          onChange={(target_exam) => onProfileUpdate({ target_exam })}
        />
        <ProfileSelectRow
          label="当前水平"
          name="profile_current_level"
          value={learnerProfile?.current_level ?? ''}
          options={CURRENT_LEVEL_OPTIONS}
          placeholder="未设置"
          onChange={(current_level) => onProfileUpdate({ current_level })}
        />
      </div>
      <Button
        variant="secondary"
        onClick={onOpenLevelInfo}
        className="mt-4 px-3 py-2 text-xs"
      >
        <HelpCircle className="size-4" />
        查看分级标准
      </Button>
    </SurfaceCard>
  )
}

function ProfileSelectRow<TValue extends string>({
  label,
  name,
  onChange,
  options,
  placeholder,
  value,
}: {
  label: string
  name: string
  options: ReadonlyArray<{ label: string; value: TValue; description?: string }>
  placeholder: string
  value: TValue | ''
  onChange: (value: TValue | null) => void
}) {
  const selected = options.find((option) => option.value === value)

  return (
    <label className="block">
      <span className="text-sm font-black text-slate-800">{label}</span>
      <Select
        name={name}
        autoComplete="off"
        value={value}
        onChange={(event) => onChange(event.currentTarget.value ? event.currentTarget.value as TValue : null)}
        wrapperClassName="mt-2"
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </Select>
      {selected?.description ? (
        <span className="mt-1 block text-xs leading-5 text-slate-500">{selected.description}</span>
      ) : null}
    </label>
  )
}

function LevelStandardsDialog({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const titleId = useId()
  const { containerRef, handleKeyDown } = useFocusTrap<HTMLElement>({
    isActive: open,
    onEscape: onClose,
  })

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[90] flex items-end justify-center px-3 py-4 sm:items-center">
      <button
        type="button"
        aria-label="关闭当前水平说明"
        className="absolute inset-0 bg-slate-950/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        onClick={onClose}
      />
      <section
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        className="relative max-h-[calc(100dvh-2rem)] w-full max-w-2xl overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
          <div>
            <h3 id={titleId} className="text-lg font-black text-slate-950">当前水平怎么选</h3>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              BinnAgent 用 CEFR A1-C2 记录当前英语能力，考试名称单独作为学习目标保存。
            </p>
          </div>
          <IconButton label="关闭当前水平说明" onClick={onClose}>
            <X className="size-4" />
          </IconButton>
        </div>

        <div className="space-y-5 px-5 py-5">
          <div className="grid gap-3 sm:grid-cols-3">
            {LEVEL_STANDARD_NOTES.map((item) => (
              <div key={item.title} className="rounded-lg border border-indigo-100 bg-indigo-50/60 p-3">
                <p className="text-sm font-black text-indigo-900">{item.title}</p>
                <p className="mt-1 text-xs leading-5 text-indigo-800/80">{item.detail}</p>
              </div>
            ))}
          </div>

          <div className="grid gap-2">
            {CURRENT_LEVEL_OPTIONS.map((item) => (
              <div key={item.value} className="rounded-lg border border-slate-200 bg-white px-4 py-3">
                <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
                  <p className="text-sm font-black text-slate-950">{item.label}</p>
                  <p className="text-xs font-semibold text-slate-500">{levelReference(item.value)}</p>
                </div>
                <p className="mt-1 text-sm leading-6 text-slate-600">{item.description}</p>
              </div>
            ))}
          </div>

          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
            考试和 CEFR 没有严格一一对应关系。这里的参照只帮助初选；真正使用时，系统会结合后续练习结果继续调整推荐难度。
          </div>
        </div>

        <div className="flex justify-end border-t border-slate-100 px-5 py-4">
          <Button onClick={onClose}>知道了</Button>
        </div>
      </section>
    </div>
  )
}

function levelReference(value: string) {
  if (value === 'a1') return '零基础到入门'
  if (value === 'a2') return '初中基础 / 日常简单表达'
  if (value === 'b1') return '中考到高考衔接 / 常见话题'
  if (value === 'b2') return '高考较好 / 四六级或雅思托福备考常见起点'
  if (value === 'c1') return '雅思托福高分段 / 学术与职场表达'
  if (value === 'c2') return '接近熟练使用'
  return ''
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

function buildAbilityScores(summary: DashboardSummary) {
  return (summary.profile?.ability_scores ?? [])
    .filter((item) => item.evidence_count > 0)
    .map((item) => ({ label: item.label, value: clampScore(item.value) }))
}

function buildMasteryBuckets(summary: DashboardSummary) {
  const classNames: Record<string, string> = {
    新学: 'bg-slate-300',
    学习中: 'bg-amber-400',
    熟悉: 'bg-indigo-500',
    掌握: 'bg-emerald-500',
  }
  const buckets = summary.profile?.mastery_buckets ?? []
  return buckets.map((bucket) => ({
    label: bucket.label,
    value: bucket.value,
    className: classNames[bucket.label] ?? 'bg-slate-300',
  }))
}

function buildLearningTrend(summary: DashboardSummary) {
  return summary.daily_activity.slice(-14).map((item) => ({
    label: formatShortDate(item.date),
    value: item.count,
  }))
}

function buildAccuracyTrend(summary: DashboardSummary) {
  return (summary.profile?.trend ?? []).slice(-14).map((item) => ({
    label: formatShortDate(item.date),
    value: clampScore(item.accuracy),
  }))
}

function buildDueTrend(summary: DashboardSummary) {
  return (summary.profile?.trend ?? []).slice(-14).map((item) => ({
    label: formatShortDate(item.date),
    value: Math.max(0, item.due_reviews),
  }))
}

// User-facing profile pages intentionally use summary APIs only; raw debug fields stay in Dev Console.
async function fetchDashboardSummary(learnerId: string) {
  const response = await fetch(`/api/learners/${learnerId}/dashboard`)
  if (!response.ok) throw new Error('Failed to load dashboard')
  return normalizeDashboardSummary(await response.json())
}

async function fetchMemorySummary(learnerId: string) {
  const response = await fetch(`/api/learners/${learnerId}/memory/summary`)
  if (!response.ok) throw new Error('Failed to load memory summary')
  return normalizeMemorySummary(await response.json(), learnerId)
}

function normalizeDashboardSummary(value: unknown): DashboardSummary {
  const source = asRecord(value)
  const stats = asRecord(source.stats)
  const todayGoal = normalizeGoal(source.today_goal, '今日课程', 0, 1)
  const weeklyGoal = normalizeGoal(source.weekly_goal, '本周练习', 0, 5)
  const profile = asRecord(source.profile)

  return {
    stats: {
      today_reviews: safeNumber(stats.today_reviews),
      today_completed_reviews: safeNumber(stats.today_completed_reviews),
      today_ai_conversations: safeNumber(stats.today_ai_conversations),
      streak_days: safeNumber(stats.streak_days),
      accuracy: safeNumber(stats.accuracy),
      total_vocab: safeNumber(stats.total_vocab),
    },
    review_items: asArray(source.review_items).map((item, index) => {
      const row = asRecord(item)
      return {
        id: safeString(row.id, `review-${index}`),
        word: safeString(row.word, 'word'),
        phonetic: safeNullableString(row.phonetic),
        definition: safeNullableString(row.definition),
        example: safeNullableString(row.example),
        confidence: safeNumber(row.confidence),
      }
    }),
    error_patterns: asArray(source.error_patterns).map((item, index) => {
      const row = asRecord(item)
      return {
        id: safeString(row.id, `pattern-${index}`),
        name: safeString(row.name, '待巩固项目'),
        count: safeNumber(row.count),
        example: safeNullableString(row.example),
        severity: safeNullableString(row.severity),
      }
    }),
    today_goal: todayGoal,
    weekly_goal: weeklyGoal,
    daily_activity: asArray(source.daily_activity).map((item, index) => {
      const row = asRecord(item)
      return {
        date: safeString(row.date, `day-${index + 1}`),
        count: safeNumber(row.count),
      }
    }),
    profile: {
      ability_scores: asArray(profile.ability_scores).map((item, index) => {
        const row = asRecord(item)
        return {
          label: safeString(row.label, `能力 ${index + 1}`),
          value: safeNumber(row.value),
          evidence_count: safeNumber(row.evidence_count),
        }
      }),
      mastery_buckets: asArray(profile.mastery_buckets).map((item, index) => {
        const row = asRecord(item)
        return {
          label: safeString(row.label, `分组 ${index + 1}`),
          value: safeNumber(row.value),
        }
      }),
      trend: asArray(profile.trend).map((item, index) => {
        const row = asRecord(item)
        return {
          date: safeString(row.date, `trend-${index + 1}`),
          accuracy: safeNumber(row.accuracy),
          due_reviews: safeNumber(row.due_reviews),
        }
      }),
    },
  }
}

function normalizeMemorySummary(value: unknown, learnerId: string): MemorySummary {
  const source = asRecord(value)
  const learner = asRecord(source.learner)
  const stats = asRecord(source.stats)

  return {
    learner: {
      id: safeString(learner.id, learnerId),
      nickname: safeString(learner.nickname, '学习者'),
      email: safeNullableString(learner.email),
    },
    stats: {
      conversation_count: safeNumber(stats.conversation_count),
      message_count: safeNumber(stats.message_count),
      total_vocab: safeNumber(stats.total_vocab),
      due_reviews: safeNumber(stats.due_reviews),
      mastered_vocab: safeNumber(stats.mastered_vocab),
    },
    latest_thread_id: safeNullableString(source.latest_thread_id),
    latest_thread_title: safeNullableString(source.latest_thread_title),
    latest_thread_summary: safeNullableString(source.latest_thread_summary),
    error_patterns: asArray(source.error_patterns).map((item, index) => {
      const row = asRecord(item)
      return {
        id: safeString(row.id, `memory-pattern-${index}`),
        name: safeString(row.name, '待巩固项目'),
        count: safeNumber(row.count),
        severity: safeNullableString(row.severity),
      }
    }),
    recent_sessions: asArray(source.recent_sessions).map((item, index) => {
      const row = asRecord(item)
      return {
        id: safeString(row.id, `session-${index}`),
        summary: safeNullableString(row.summary),
        active_skill: safeNullableString(row.active_skill),
        completed_at: safeNullableString(row.completed_at),
      }
    }),
    recent_events: asArray(source.recent_events).map((item, index) => {
      const row = asRecord(item)
      return {
        id: safeString(row.id, `event-${index}`),
        event_type: safeString(row.event_type, 'event'),
        skill: safeString(row.skill, 'general'),
        source_type: safeString(row.source_type, 'unknown'),
        source_id: safeNullableString(row.source_id),
        confidence: safeNumber(row.confidence),
        occurred_at: safeString(row.occurred_at, ''),
        summary: safeString(row.summary, '学习记录已更新'),
      }
    }),
    active_weaknesses: asArray(source.active_weaknesses).filter((item): item is string => typeof item === 'string'),
  }
}

function normalizeGoal(value: unknown, fallbackLabel: string, fallbackCompleted: number, fallbackTotal: number) {
  const goal = asRecord(value)
  return {
    label: safeString(goal.label, fallbackLabel),
    completed: safeNumber(goal.completed, fallbackCompleted),
    total: Math.max(1, safeNumber(goal.total, fallbackTotal)),
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function safeString(value: unknown, fallback: string) {
  return typeof value === 'string' && value.trim() ? value : fallback
}

function safeNullableString(value: unknown) {
  return typeof value === 'string' && value.trim() ? value : null
}

function safeNumber(value: unknown, fallback = 0) {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

async function fetchGroupLearningCardSummary(learnerId: string): Promise<GroupLearningCardSummary> {
  const [sources, signalPage] = await Promise.all([
    listGroupLearningSources(learnerId),
    listGroupLearningSignals(learnerId, 'candidate', undefined, 1, 1, 'all'),
  ])
  return buildGroupLearningCardSummary(sources, signalPage.total)
}

function buildGroupLearningCardSummary(
  sources: GroupLearningSource[],
  pendingCount: number,
): GroupLearningCardSummary {
  const activeSources = sources.filter((source) => source.status === 'active')
  const participantCount = sources.reduce((sum, source) => sum + source.participant_count, 0)
  const latestSync = sources
    .map((source) => source.last_sync_at || source.last_seen_at || syncedAtFromSummary(source.last_import_summary))
    .filter((value): value is string => Boolean(value))
    .sort()
    .at(-1)
  const state: GroupLearningCardState = sources.length === 0
    ? 'not_configured'
    : activeSources.length === 0
      ? 'paused'
      : participantCount === 0
        ? 'unbound'
        : latestSync
          ? 'active'
          : 'pending_sync'

  return {
    state,
    sourceCount: sources.length,
    participantCount,
    pendingCount,
    latestSyncLabel: latestSync ? formatActivityDate(latestSync) : '尚未同步',
  }
}

function syncedAtFromSummary(summary: Record<string, unknown>) {
  const syncedAt = summary.synced_at
  return typeof syncedAt === 'string' && syncedAt.trim() ? syncedAt : null
}

function groupLearningCardCopy(summary: GroupLearningCardSummary) {
  const statusCopy = {
    not_configured: {
      description: '还没有配置飞书群来源；添加后才能捕捉表达、语法、单词和好句。',
      meta: '未配置来源 · 点击进入设置',
      badgeClass: 'bg-slate-200 text-slate-700',
    },
    paused: {
      description: '群聊读取已暂停，已有线索仍可查看和确认。',
      meta: `${summary.sourceCount} 个来源 · 读取已暂停`,
      badgeClass: 'bg-amber-100 text-amber-700',
    },
    unbound: {
      description: '已添加群来源，但还没有同步或绑定群成员。',
      meta: `${summary.sourceCount} 个来源 · 待绑定成员`,
      badgeClass: 'bg-amber-100 text-amber-700',
    },
    pending_sync: {
      description: '来源已启用，等待首次同步后开始生成候选线索。',
      meta: `${summary.sourceCount} 个来源 · ${summary.participantCount} 位成员 · ${summary.latestSyncLabel}`,
      badgeClass: 'bg-sky-100 text-sky-700',
    },
    active: {
      description: '从指定飞书群捕捉你想学的表达、语法、单词和好句。',
      meta: `待确认 ${summary.pendingCount} 条 · ${summary.sourceCount} 个来源 · ${summary.participantCount} 位成员`,
      badgeClass: summary.pendingCount > 0 ? 'bg-primary text-white' : 'bg-emerald-100 text-emerald-700',
    },
  } satisfies Record<GroupLearningCardState, { description: string; meta: string; badgeClass: string }>
  return statusCopy[summary.state]
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

function VocabularyListPagination({
  currentPage,
  onPageChange,
  pageSize,
  totalItems,
  totalPages,
}: {
  currentPage: number
  onPageChange: (page: number) => void
  pageSize: number
  totalItems: number
  totalPages: number
}) {
  const start = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1
  const end = Math.min(totalItems, currentPage * pageSize)

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-slate-100 bg-white px-3 py-2 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
      <p>
        显示 {start}-{end} / {totalItems} 个词
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          disabled={currentPage <= 1}
          onClick={() => onPageChange(Math.max(1, currentPage - 1))}
        >
          <ArrowLeft className="size-4" />
          上一页
        </Button>
        <span className="min-w-16 text-center font-bold text-slate-600">
          {currentPage}/{totalPages}
        </span>
        <Button
          variant="secondary"
          disabled={currentPage >= totalPages}
          onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
        >
          下一页
          <ArrowRight className="size-4" />
        </Button>
      </div>
    </div>
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
