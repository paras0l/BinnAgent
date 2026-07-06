import { useCallback, useEffect, useState, type ReactNode } from 'react'
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  BrainCircuit,
  CalendarDays,
  Clock3,
  RefreshCw,
  Sparkles,
  Target,
} from 'lucide-react'
import { FeatureHero } from '@/components/layout/FeatureHero'
import { PageShell } from '@/components/layout/PageShell'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import type { DashboardSummary, Learner, MemorySummary } from '@/types'
import type { VocabularyPracticeMode } from '@/pages/VocabularyPracticePage'
import { LearningProfileView, LearningRecordsView } from '@/pages/DashboardPage'
import { useToast } from '@/hooks/useToast'

type LearningCenterView = 'home' | 'profile' | 'records'

interface LearningCenterPageProps {
  learner: Learner
  onOpenDailyLearning: () => void
  onStartVocabularyPractice: (mode: VocabularyPracticeMode) => void
}

export function LearningCenterPage({
  learner,
  onOpenDailyLearning,
  onStartVocabularyPractice,
}: LearningCenterPageProps) {
  const { showToast } = useToast()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [memorySummary, setMemorySummary] = useState<MemorySummary | null>(null)
  const [activeView, setActiveView] = useState<LearningCenterView>('home')
  const [isLoading, setIsLoading] = useState(true)

  const loadLearningCenter = useCallback(async () => {
    setIsLoading(true)
    try {
      const [dashboardResult, memoryResult] = await Promise.allSettled([
        fetchDashboardSummary(learner.id),
        fetchMemorySummary(learner.id),
      ])

      if (dashboardResult.status === 'rejected') throw dashboardResult.reason
      setSummary(dashboardResult.value)
      setMemorySummary(memoryResult.status === 'fulfilled' ? memoryResult.value : null)
    } catch (error) {
      console.error('Learning center load error:', error)
      showToast('学习中心暂时无法加载，请稍后重试。', { variant: 'error' })
      setSummary(null)
    } finally {
      setIsLoading(false)
    }
  }, [learner.id, showToast])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadLearningCenter(), 0)
    return () => window.clearTimeout(timer)
  }, [loadLearningCenter])

  if (isLoading && !summary) {
    return <LoadingState title="正在加载学习中心" description="正在读取今日入口、学习记录和学习画像摘要..." />
  }

  if (!summary) {
    return (
      <ErrorState
        title="学习中心暂时无法加载"
        description="可以重新加载学习中心，或先进入 AI 对话继续学习。"
        action={<Button onClick={() => void loadLearningCenter()}><RefreshCw className="size-4" />重新加载</Button>}
      />
    )
  }

  if (activeView === 'profile') {
    return (
      <LearningProfileView
        learner={learner}
        summary={summary}
        memorySummary={memorySummary}
        onBack={() => setActiveView('home')}
        onOpenDailyLearning={onOpenDailyLearning}
        onOpenRecords={() => setActiveView('records')}
      />
    )
  }

  if (activeView === 'records') {
    return (
      <LearningRecordsView
        summary={summary}
        memorySummary={memorySummary}
        onBack={() => setActiveView('home')}
        onOpenProfile={() => setActiveView('profile')}
      />
    )
  }

  return (
    <LearningCenterHome
      learnerName={learner.nickname}
      memorySummary={memorySummary}
      summary={summary}
      onOpenDailyLearning={onOpenDailyLearning}
      onOpenProfile={() => setActiveView('profile')}
      onOpenRecords={() => setActiveView('records')}
      onStartVocabularyPractice={onStartVocabularyPractice}
    />
  )
}

function LearningCenterHome({
  learnerName,
  memorySummary,
  summary,
  onOpenDailyLearning,
  onOpenProfile,
  onOpenRecords,
  onStartVocabularyPractice,
}: {
  learnerName: string
  memorySummary: MemorySummary | null
  summary: DashboardSummary
  onOpenDailyLearning: () => void
  onOpenProfile: () => void
  onOpenRecords: () => void
  onStartVocabularyPractice: (mode: VocabularyPracticeMode) => void
}) {
  const todayPercent = toPercent(summary.today_goal.completed, summary.today_goal.total)
  const weeklyPercent = toPercent(summary.weekly_goal.completed, summary.weekly_goal.total)
  const dueReviews = summary.stats.today_reviews
  const suggestedVocabularyMode: VocabularyPracticeMode = dueReviews > 0 ? 'review' : 'new'
  const focusReasons = buildFocusReasons(summary)
  const profileSignals = buildProfileSignals(summary, memorySummary)
  const primaryAction = dueReviews > 0
    ? {
        label: '先复习到期词汇',
        description: `${dueReviews} 个词今天到期，先主动回忆可以减少遗忘。`,
        onClick: () => onStartVocabularyPractice('review'),
        icon: <Clock3 className="size-5" />,
      }
    : {
        label: '开始今日学习',
        description: summary.today_goal.completed < summary.today_goal.total
          ? `今日目标还剩 ${summary.today_goal.total - summary.today_goal.completed} 项，适合继续教材主线。`
          : '今天没有积压任务，可以用一节短课保持学习节奏。',
        onClick: onOpenDailyLearning,
        icon: <BookOpen className="size-5" />,
      }

  return (
    <PageShell>
      <FeatureHero
        eyebrow="Learning Center"
        title="学习中心"
        description={`${learnerName}，这里是今天的学习入口。重功能已收进对应页面，先选一个方向开始。`}
        stats={[
          { label: '今日目标', value: `${summary.today_goal.completed}/${summary.today_goal.total}`, tone: todayPercent >= 100 ? 'success' : 'primary' },
          { label: '待复习', value: dueReviews, tone: dueReviews > 0 ? 'warning' : 'success' },
          { label: '连续学习', value: `${summary.stats.streak_days} 天` },
          { label: '正确率', value: `${summary.stats.accuracy}%`, tone: summary.stats.accuracy >= 80 ? 'success' : 'primary' },
        ]}
        actions={
          <Button onClick={primaryAction.onClick}>
            {primaryAction.icon}
            {primaryAction.label}
          </Button>
        }
      />

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
          <TodayFocusCard
            description={primaryAction.description}
            reasons={focusReasons}
            todayPercent={todayPercent}
            todayGoal={summary.today_goal}
            onPrimaryAction={primaryAction.onClick}
            primaryActionLabel={primaryAction.label}
          />

          <section aria-label="学习入口" className="grid gap-4 md:grid-cols-2">
            <LearningEntryCard
              icon={BookOpen}
              title="教材学习"
              description="进入当前单元，完成今日课程、教材练习和单元词汇。"
              meta={`${summary.today_goal.completed}/${summary.today_goal.total} 项今日目标`}
              actionLabel="进入教材"
              onClick={onOpenDailyLearning}
            />
            <LearningEntryCard
              icon={Clock3}
              title="词汇练习"
              description={dueReviews > 0 ? '处理到期复习；如果没有到期词，再认识新词。' : '今天没有积压复习，可以认识一组新词。'}
              meta={dueReviews > 0 ? `${dueReviews} 个待复习` : `${summary.stats.total_vocab} 个词汇资产`}
              actionLabel={dueReviews > 0 ? '开始复习' : '认识新词'}
              onClick={() => onStartVocabularyPractice(suggestedVocabularyMode)}
            />
            <LearningEntryCard
              icon={BrainCircuit}
              title="学习画像"
              description="查看能力分布、薄弱点和下一步建议。"
              meta={`${summary.error_patterns.length} 类近期薄弱点`}
              actionLabel="查看画像"
              onClick={onOpenProfile}
            />
            <LearningEntryCard
              icon={CalendarDays}
              title="学习记录"
              description="回顾最近学习节奏、练习动态和连续学习情况。"
              meta={`${summary.stats.streak_days} 天连续学习`}
              actionLabel="查看记录"
              onClick={onOpenRecords}
            />
          </section>
        </div>

        <aside className="space-y-5">
          <ProgressSnapshotCard todayPercent={todayPercent} weeklyPercent={weeklyPercent} />
          <ActivityPreviewCard summary={summary} onOpenRecords={onOpenRecords} />
        </aside>
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <ProfilePreviewCard signals={profileSignals} onOpenProfile={onOpenProfile} />
        <ReviewLoadCard summary={summary} onStartVocabularyPractice={onStartVocabularyPractice} />
      </section>
    </PageShell>
  )
}

function TodayFocusCard({
  description,
  reasons,
  todayGoal,
  todayPercent,
  primaryActionLabel,
  onPrimaryAction,
}: {
  description: string
  reasons: string[]
  todayGoal: DashboardSummary['today_goal']
  todayPercent: number
  primaryActionLabel: string
  onPrimaryAction: () => void
}) {
  return (
    <SurfaceCard className="overflow-hidden border-primary/20 p-0">
      <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="p-5 sm:p-6">
          <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-primary">
            <Sparkles className="size-4" />
            今日主入口
          </div>
          <h2 className="mt-3 text-2xl font-black tracking-tight text-slate-950">从一个明确动作开始</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">{description}</p>

          <div className="mt-5 grid gap-3 md:grid-cols-2">
            {reasons.slice(0, 2).map((reason) => (
              <div key={reason} className="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
                <p className="text-xs font-black text-slate-500">推荐依据</p>
                <p className="mt-1 text-sm font-semibold leading-6 text-slate-700">{reason}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col justify-between border-t border-slate-100 bg-slate-50/70 p-5 lg:border-l lg:border-t-0">
          <div>
            <p className="text-xs font-black uppercase text-slate-500">{todayGoal.label}</p>
            <div className="mt-4 flex items-center gap-4">
              <ProgressRing value={todayPercent} />
              <div>
                <p className="text-2xl font-black text-slate-950">{todayGoal.completed}/{todayGoal.total}</p>
                <p className="mt-1 text-xs font-semibold text-slate-500">今日完成进度</p>
              </div>
            </div>
          </div>
          <Button className="mt-5 w-full justify-between" onClick={onPrimaryAction}>
            {primaryActionLabel}
            <ArrowRight className="size-4" />
          </Button>
        </div>
      </div>
    </SurfaceCard>
  )
}

function LearningEntryCard({
  actionLabel,
  description,
  icon: Icon,
  meta,
  onClick,
  title,
}: {
  actionLabel: string
  description: string
  icon: typeof BookOpen
  meta: string
  onClick: () => void
  title: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group rounded-[13px] border border-slate-200 bg-white p-5 text-left shadow-[0_4px_14px_rgba(15,23,42,0.05)] transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary/50"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary transition group-hover:scale-105 group-hover:bg-primary group-hover:text-white">
          <Icon className="size-5" />
        </div>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-black text-slate-500">{meta}</span>
      </div>
      <h3 className="mt-4 text-lg font-black text-slate-950">{title}</h3>
      <p className="mt-2 min-h-12 text-sm leading-6 text-slate-500">{description}</p>
      <div className="mt-5 inline-flex items-center gap-2 text-sm font-black text-primary">
        {actionLabel}
        <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" />
      </div>
    </button>
  )
}

function ProgressSnapshotCard({ todayPercent, weeklyPercent }: { todayPercent: number; weeklyPercent: number }) {
  return (
    <SurfaceCard>
      <SectionHeading icon={<Target className="size-4" />} title="目标进度" />
      <div className="mt-5 grid grid-cols-2 gap-4">
        <ProgressRingBlock label="今日" value={todayPercent} />
        <ProgressRingBlock label="本周" value={weeklyPercent} />
      </div>
      <p className="mt-4 rounded-xl bg-slate-50 px-3 py-2 text-xs font-semibold leading-5 text-slate-500">
        学习中心只展示轻量概览；具体练习和管理都在入口卡片后面的页面完成。
      </p>
    </SurfaceCard>
  )
}

function ActivityPreviewCard({ summary, onOpenRecords }: { summary: DashboardSummary; onOpenRecords: () => void }) {
  const activity = summary.daily_activity.slice(-14)
  const maxLearningAmount = Math.max(...activity.map((item) => item.count), 1)
  return (
    <SurfaceCard>
      <div className="flex items-center justify-between gap-3">
        <SectionHeading icon={<CalendarDays className="size-4" />} title="最近活跃" />
        <p className="text-xs font-black text-slate-500">{summary.stats.streak_days} 天连续</p>
      </div>
      <div className="mt-5 grid grid-cols-7 gap-2" aria-label="最近 14 天活跃度">
        {activity.map((item) => {
          const intensity = item.count === 0 ? 0 : 0.14 + (item.count / maxLearningAmount) * 0.86
          const label = `${formatActivityDate(item.date)}，学习量 ${item.count}`
          return (
            <div
              key={item.date}
              className="aspect-square rounded-[5px] bg-slate-100 ring-1 ring-inset ring-slate-200/70 transition hover:scale-110 hover:ring-primary/40"
              style={item.count === 0 ? undefined : { backgroundColor: `rgb(99 102 241 / ${intensity.toFixed(2)})` }}
              title={label}
              aria-label={label}
            />
          )
        })}
      </div>
      <Button variant="secondary" className="mt-5 w-full justify-between" onClick={onOpenRecords}>
        查看完整记录
        <ArrowRight className="size-4" />
      </Button>
    </SurfaceCard>
  )
}

function ProfilePreviewCard({
  signals,
  onOpenProfile,
}: {
  signals: SkillSignal[]
  onOpenProfile: () => void
}) {
  return (
    <SurfaceCard>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <SectionHeading icon={<BrainCircuit className="size-4" />} title="学习画像预览" />
          <p className="mt-2 text-sm leading-6 text-slate-500">用图表先看能力轮廓，详细薄弱点和建议进入画像页。</p>
        </div>
        <Button variant="secondary" onClick={onOpenProfile}>
          查看画像
          <ArrowRight className="size-4" />
        </Button>
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
        <SkillRadarChart signals={signals} />
        <div className="grid content-center gap-3 sm:grid-cols-2">
          {signals.map((signal) => (
            <div key={signal.label} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-black text-slate-500">{signal.label}</p>
                <p className="text-sm font-black text-slate-950">{signal.value}%</p>
              </div>
              <ProgressBar value={signal.value} className="mt-2" />
            </div>
          ))}
        </div>
      </div>
    </SurfaceCard>
  )
}

function ReviewLoadCard({
  summary,
  onStartVocabularyPractice,
}: {
  summary: DashboardSummary
  onStartVocabularyPractice: (mode: VocabularyPracticeMode) => void
}) {
  const totalReviewActions = summary.stats.today_reviews + summary.stats.today_completed_reviews
  const completedPercent = toPercent(summary.stats.today_completed_reviews, totalReviewActions)
  return (
    <SurfaceCard>
      <SectionHeading icon={<BarChart3 className="size-4" />} title="复习负荷" />
      <div className="mt-4 space-y-4">
        <LoadBar
          label="已完成"
          value={summary.stats.today_completed_reviews}
          percent={completedPercent}
        />
        <LoadBar
          label="待复习"
          value={summary.stats.today_reviews}
          percent={toPercent(summary.stats.today_reviews, totalReviewActions)}
          muted
        />
      </div>
      <Button
        className="mt-5 w-full justify-between"
        variant={summary.stats.today_reviews > 0 ? 'primary' : 'secondary'}
        onClick={() => onStartVocabularyPractice(summary.stats.today_reviews > 0 ? 'review' : 'new')}
      >
        {summary.stats.today_reviews > 0 ? '处理到期复习' : '认识一组新词'}
        <ArrowRight className="size-4" />
      </Button>
    </SurfaceCard>
  )
}

function ProgressRingBlock({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50 p-3 text-center">
      <ProgressRing value={value} size="md" />
      <p className="mt-3 text-sm font-black text-slate-950">{label}</p>
      <p className="mt-1 text-xs font-semibold text-slate-500">{value}%</p>
    </div>
  )
}

function ProgressRing({ value, size = 'lg' }: { value: number; size?: 'md' | 'lg' }) {
  const safeValue = Math.max(0, Math.min(100, value))
  const sizeClass = size === 'lg' ? 'size-20' : 'size-16'
  return (
    <div
      className={`grid ${sizeClass} place-items-center rounded-full`}
      style={{ background: `conic-gradient(rgb(79 70 229) ${safeValue * 3.6}deg, rgb(226 232 240) 0deg)` }}
      aria-label={`完成 ${safeValue}%`}
    >
      <div className="grid size-[72%] place-items-center rounded-full bg-white text-sm font-black text-slate-950">
        {safeValue}%
      </div>
    </div>
  )
}

function SkillRadarChart({ signals }: { signals: SkillSignal[] }) {
  const points = radarPoints(signals.map((item) => item.value), 96, 100)
  const guidePoints = [0.25, 0.5, 0.75, 1].map((scale) => radarPoints(signals.map(() => scale * 100), 96, 100))
  return (
    <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
      <svg viewBox="0 0 220 220" role="img" aria-label="学习能力雷达图" className="mx-auto size-56 max-w-full">
        {guidePoints.map((pointSet) => (
          <polygon key={pointSet} points={pointSet} fill="none" stroke="rgb(226 232 240)" strokeWidth="1" />
        ))}
        {signals.map((signal, index) => {
          const [x, y] = radarPoint(index, signals.length, 100, 96)
          return (
            <g key={signal.label}>
              <line x1="110" y1="110" x2={x} y2={y} stroke="rgb(226 232 240)" strokeWidth="1" />
              <text x={x} y={y} textAnchor={x > 112 ? 'start' : x < 108 ? 'end' : 'middle'} dominantBaseline="middle" className="fill-slate-500 text-[10px] font-bold">
                {signal.label}
              </text>
            </g>
          )
        })}
        <polygon points={points} fill="rgb(99 102 241 / 0.18)" stroke="rgb(79 70 229)" strokeWidth="2" />
        {signals.map((signal, index) => {
          const [x, y] = radarPoint(index, signals.length, signal.value, 96)
          return <circle key={`${signal.label}-point`} cx={x} cy={y} r="3.2" fill="rgb(79 70 229)" />
        })}
      </svg>
    </div>
  )
}

function LoadBar({ label, muted = false, percent, value }: { label: string; muted?: boolean; percent: number; value: number }) {
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="font-bold text-slate-600">{label}</span>
        <span className="font-black text-slate-950">{value}</span>
      </div>
      <div className="mt-2 h-3 overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full transition-[width] duration-500 ${muted ? 'bg-amber-400' : 'bg-indigo-600'}`}
          style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
        />
      </div>
    </div>
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

interface SkillSignal {
  label: string
  value: number
}

function buildProfileSignals(summary: DashboardSummary, memorySummary: MemorySummary | null): SkillSignal[] {
  const masteredVocabulary = memorySummary?.stats.mastered_vocab ?? 0
  const vocabularyBase = summary.stats.total_vocab > 0
    ? Math.round((masteredVocabulary / summary.stats.total_vocab) * 100)
    : 24
  const accuracy = clamp(summary.stats.accuracy || 0, 18, 100)
  const activityScore = clamp(summary.stats.streak_days * 12, 12, 100)
  const reviewScore = summary.stats.today_reviews === 0
    ? 86
    : clamp(100 - summary.stats.today_reviews * 8, 20, 100)
  const recordScore = clamp((memorySummary?.recent_sessions.length ?? 0) * 18, 18, 100)
  const weaknessPenalty = clamp(100 - summary.error_patterns.length * 14, 20, 100)

  return [
    { label: '词汇', value: clamp(vocabularyBase, 18, 100) },
    { label: '语法', value: accuracy },
    { label: '阅读', value: recordScore },
    { label: '写作', value: weaknessPenalty },
    { label: '发音', value: activityScore },
    { label: '复习', value: reviewScore },
  ]
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

function radarPoints(values: number[], radius: number, maxValue: number) {
  return values.map((value, index) => radarPoint(index, values.length, value, radius, maxValue).join(',')).join(' ')
}

function radarPoint(index: number, total: number, value: number, radius: number, maxValue = 100): [number, number] {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2
  const ratio = Math.max(0, Math.min(maxValue, value)) / maxValue
  return [110 + Math.cos(angle) * radius * ratio, 110 + Math.sin(angle) * radius * ratio]
}

function toPercent(completed: number, total: number) {
  return total > 0 ? Math.round((completed / total) * 100) : 0
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, Math.round(value)))
}

function formatActivityDate(date: string) {
  return new Date(`${date}T00:00:00`).toLocaleDateString('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'short',
  })
}

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
