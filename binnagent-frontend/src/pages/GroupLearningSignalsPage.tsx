import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  BookMarked,
  Check,
  ChevronRight,
  CirclePause,
  Database,
  FileText,
  Filter,
  GraduationCap,
  Highlighter,
  Inbox,
  MessageCircle,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Tags,
  Trash2,
  UserRoundCheck,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { FilterChip } from '@/components/ui/FilterChip'
import { StatusBanner } from '@/components/ui/StatusBanner'
import { useToast } from '@/hooks/useToast'
import {
  deleteGroupLearningSignal,
  listGroupLearningSignals,
  listGroupLearningSources,
  syncGroupLearningSourceNow,
  updateGroupLearningSource,
  updateGroupLearningSignal,
  type GroupLearningSignal as ApiGroupLearningSignal,
  type GroupLearningSource,
} from '@/services/groupLearningApi'
import type { Learner } from '@/types'

type SignalStatus = 'candidate' | 'accepted' | 'dismissed'
type SignalCategory =
  | 'all'
  | 'expression_gap'
  | 'grammar'
  | 'intent'
  | 'vocabulary'
  | 'sentence'
  | 'note'
  | 'dismissed'

interface GroupLearningSignal {
  id: string
  type: 'grammar_error' | 'grammar_correct_usage' | 'expression_gap' | 'desired_vocabulary' | 'desired_grammar' | 'good_sentence' | 'note_candidate'
  category: Exclude<SignalCategory, 'all' | 'dismissed'>
  status: SignalStatus
  title: string
  sourceText: string
  explanation: string
  recommendation: string
  target: string
  confidence: number
  sourceTime: string
  actionLabel: string
  accentClass: string
}

const filters: Array<{ id: SignalCategory; label: string }> = [
  { id: 'all', label: '全部' },
  { id: 'expression_gap', label: '表达缺口' },
  { id: 'grammar', label: '语法线索' },
  { id: 'intent', label: '想学内容' },
  { id: 'vocabulary', label: '词汇候选' },
  { id: 'sentence', label: '好句候选' },
  { id: 'note', label: '笔记候选' },
  { id: 'dismissed', label: '已忽略' },
]

interface GroupLearningSignalsPageProps {
  learner: Learner
  onBack: () => void
  onOpenSettings: () => void
}

export function GroupLearningSignalsPage({ learner, onBack, onOpenSettings }: GroupLearningSignalsPageProps) {
  const { showToast } = useToast()
  const [signals, setSignals] = useState<GroupLearningSignal[]>([])
  const [sources, setSources] = useState<GroupLearningSource[]>([])
  const [activeFilter, setActiveFilter] = useState<SignalCategory>('all')
  const [query, setQuery] = useState('')
  const [isPaused, setIsPaused] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const loadSignals = useCallback(async () => {
    setIsLoading(true)
    try {
      const items = await listGroupLearningSignals(learner.id, 'all')
      setSignals(items.filter((item) => item.status !== 'deleted').map(toSignalCard))
    } catch (error) {
      showToast(error instanceof Error ? error.message : '加载群聊学习线索失败。', { variant: 'error' })
    } finally {
      setIsLoading(false)
    }
  }, [learner.id, showToast])

  const loadSources = useCallback(async () => {
    try {
      const items = await listGroupLearningSources(learner.id)
      setSources(items)
      setIsPaused(items.length > 0 && items.every((source) => source.status !== 'active'))
    } catch {
      setSources([])
    }
  }, [learner.id])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadSignals()
      void loadSources()
    }, 0)
    return () => window.clearTimeout(timer)
  }, [loadSignals, loadSources])

  const stats = useMemo(() => {
    const candidates = signals.filter((signal) => signal.status === 'candidate')
    return {
      pending: candidates.length,
      accepted: signals.filter((signal) => signal.status === 'accepted').length,
      today: signals.filter((signal) => signal.sourceTime.startsWith('今天')).length,
      confidence: Math.round(
        candidates.reduce((sum, signal) => sum + signal.confidence, 0) / Math.max(candidates.length, 1) * 100,
      ),
    }
  }, [signals])

  const visibleSignals = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return signals.filter((signal) => {
      const matchesFilter =
        activeFilter === 'all'
          ? signal.status !== 'dismissed'
          : activeFilter === 'dismissed'
            ? signal.status === 'dismissed'
            : signal.category === activeFilter && signal.status !== 'dismissed'
      if (!matchesFilter) return false
      if (!normalizedQuery) return true
      return `${signal.title} ${signal.sourceText} ${signal.recommendation}`.toLowerCase().includes(normalizedQuery)
    })
  }, [activeFilter, query, signals])

  const sourceSummary = useMemo(() => {
    const participantCount = sources.reduce((sum, source) => sum + source.participant_count, 0)
    const retentionDays = sources[0]?.raw_retention_days ?? 7
    const latestSeen = sources
      .map((source) => source.last_seen_at)
      .filter((value): value is string => Boolean(value))
      .sort()
      .at(-1)
    return {
      boundaryItems: [
        `飞书群来源 ${sources.length} 个`,
        `已发现成员 ${participantCount} 位`,
        `原始消息保留 ${retentionDays} 天`,
        '未映射成员默认忽略',
      ],
      latestSeenLabel: latestSeen ? formatSignalTime(latestSeen) : '尚未同步',
    }
  }, [sources])

  const updateSignalStatus = async (id: string, status: SignalStatus) => {
    const action = status === 'accepted' ? 'accept' : status === 'dismissed' ? 'dismiss' : 'restore'
    try {
      const updated = await updateGroupLearningSignal(learner.id, id, action)
      setSignals((items) => items.map((item) => item.id === id ? toSignalCard(updated) : item))
      return true
    } catch (error) {
      showToast(error instanceof Error ? error.message : '更新线索失败。', { variant: 'error' })
      return false
    }
  }

  const deleteSignal = async (id: string) => {
    try {
      await deleteGroupLearningSignal(learner.id, id)
      setSignals((items) => items.filter((item) => item.id !== id))
      showToast('已删除这条群聊学习线索。', { variant: 'success' })
    } catch (error) {
      showToast(error instanceof Error ? error.message : '删除线索失败。', { variant: 'error' })
    }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#f6f7f9]">
      <div className="mx-auto box-border flex w-full max-w-[1440px] flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
        <section className="overflow-hidden rounded-lg border border-slate-200 bg-white text-slate-950 shadow-sm">
          <div className="grid gap-8 p-5 sm:p-7 lg:grid-cols-[minmax(0,1fr)_420px] lg:p-8">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="secondary" onClick={onBack}>
                  <ArrowLeft className="size-4" />
                  返回学习中心
                </Button>
                <span className="rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-xs font-bold text-primary">
                  后台学习能力
                </span>
              </div>
              <p className="mt-8 text-xs font-black uppercase tracking-[0.28em] text-primary">Group Learning Signals</p>
              <h1 className="mt-3 max-w-3xl text-4xl font-black leading-tight sm:text-5xl">
                群聊学习线索
              </h1>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-500 sm:text-base">
                从指定飞书群捕捉你想学的表达、语法、单词和好句。默认只读，线索确认后才写入长期学习资产。
              </p>
              <div className="mt-7 grid gap-3 sm:grid-cols-4">
                <HeroMetric label="待确认" value={stats.pending} tone="indigo" />
                <HeroMetric label="今日新增" value={stats.today} tone="amber" />
                <HeroMetric label="已接受" value={stats.accepted} tone="sky" />
                <HeroMetric label="平均可信度" value={`${stats.confidence}%`} tone="emerald" />
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-black text-slate-950">读取边界</p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">指定飞书群、成员映射、短期保留。</p>
                </div>
                <ShieldCheck className="size-6 text-primary" />
              </div>
              <div className="mt-4 grid gap-2">
                {sourceSummary.boundaryItems.map((item) => (
                  <div key={item} className="flex items-center gap-2 rounded-lg border border-slate-100 bg-white px-3 py-2 text-sm text-slate-700">
                    <Check className="size-4 text-primary" />
                    {item}
                  </div>
                ))}
              </div>
              <div className="mt-4 flex gap-2">
                <Button
                  variant="secondary"
                  className="flex-1"
                  onClick={onOpenSettings}
                >
                  <Settings className="size-4" />
                  设置
                </Button>
                <Button
                  variant="secondary"
                  className="flex-1"
                  onClick={() => {
                    const nextStatus = isPaused ? 'active' : 'paused'
                    void Promise.all(sources.map((source) => updateGroupLearningSource(learner.id, source.id, { status: nextStatus })))
                      .then(() => {
                        setIsPaused(!isPaused)
                        void loadSources()
                        showToast(isPaused ? '已恢复群聊线索读取。' : '已暂停群聊线索读取。', {
                          variant: isPaused ? 'success' : 'warning',
                        })
                      })
                      .catch((error: unknown) => {
                        showToast(error instanceof Error ? error.message : '更新读取状态失败。', { variant: 'error' })
                      })
                  }}
                >
                  <CirclePause className="size-4" />
                  {isPaused ? '恢复读取' : '暂停读取'}
                </Button>
              </div>
            </div>
          </div>
        </section>

        <StatusBanner
          tone={isPaused ? 'warning' : 'success'}
          title={isPaused ? '读取已暂停' : '同步正常'}
          action={<Button variant="secondary" onClick={() => {
            const activeSources = sources.filter((source) => source.status === 'active' && source.platform === 'feishu')
            if (!activeSources.length) {
              showToast('请先添加并启用一个飞书群来源。', { variant: 'warning' })
              return
            }
            void Promise.all(activeSources.map((source) => syncGroupLearningSourceNow(learner.id, source.id)))
              .then((summaries) => {
                const isPlaceholder = summaries.every((summary) => summary.placeholder)
                const generated = summaries.reduce((sum, summary) => sum + summary.generated_signal_count, 0)
                showToast(
                  isPlaceholder ? '同步占位已记录；配置 MCP 后会读取飞书消息。' : `同步完成，生成 ${generated} 条候选线索。`,
                  { variant: isPlaceholder ? 'warning' : 'success' },
                )
                void loadSources()
                void loadSignals()
              })
              .catch((error: unknown) => {
                showToast(error instanceof Error ? error.message : '手动同步失败。', { variant: 'error' })
              })
          }}><RefreshCw className="size-4" />同步一次</Button>}
        >
          {isPaused ? '系统不会读取新群消息，已有线索仍可确认或删除。' : `最后同步：${sourceSummary.latestSeenLabel}。新消息会先去重，再进入线索抽取。`}
        </StatusBanner>

        <section className="grid min-w-0 items-start gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="min-w-0 space-y-4">
            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <Inbox className="size-5 text-primary" />
                    <h2 className="text-xl font-black text-slate-950">线索收件箱</h2>
                  </div>
                  <p className="mt-1 text-sm leading-6 text-slate-500">接受后进入学习推荐、词汇候选、好句收藏或画像证据。</p>
                </div>
                <label className="relative block min-w-0 lg:w-72">
                  <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    className="min-h-10 w-full rounded-lg border border-slate-200 bg-slate-50 py-2.5 pl-9 pr-3 text-sm outline-none transition focus:border-primary focus:bg-white focus:ring-2 focus:ring-primary/20"
                    placeholder="搜索线索、原文或推荐..."
                    aria-label="搜索群聊学习线索"
                  />
                </label>
              </div>

              <div className="mt-4 flex gap-2 overflow-x-auto pb-1" aria-label="线索分组">
                {filters.map((filter) => (
                  <FilterChip key={filter.id} active={activeFilter === filter.id} onClick={() => setActiveFilter(filter.id)}>
                    {filter.label}
                  </FilterChip>
                ))}
              </div>
            </div>

            <div className="grid gap-3">
              {visibleSignals.length ? visibleSignals.map((signal) => (
                <SignalCard
                  key={signal.id}
                  signal={signal}
                  onAccept={() => {
                    void updateSignalStatus(signal.id, 'accepted').then((ok) => {
                      if (ok) showToast(`已${signal.actionLabel}。`, { variant: 'success' })
                    })
                  }}
                  onDelete={() => void deleteSignal(signal.id)}
                  onDismiss={() => {
                    void updateSignalStatus(signal.id, 'dismissed').then((ok) => {
                      if (ok) showToast('已忽略这条线索。', { variant: 'success' })
                    })
                  }}
                  onRestore={() => {
                    void updateSignalStatus(signal.id, 'candidate').then((ok) => {
                      if (ok) showToast('已恢复到待确认。', { variant: 'success' })
                    })
                  }}
                />
              )) : (
                <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center">
                  <Filter className="mx-auto size-8 text-slate-400" />
                  <p className="mt-3 text-sm font-black text-slate-950">{isLoading ? '正在加载线索' : '没有匹配的线索'}</p>
                  <p className="mt-1 text-sm text-slate-500">{isLoading ? '稍等一下，正在读取后端收件箱。' : '导入已映射成员的群消息后，这里会出现候选线索。'}</p>
                </div>
              )}
            </div>
          </div>

          <aside className="space-y-4">
            <SourceSetupPanel sources={sources} />
            <PipelinePanel />
          </aside>
        </section>
      </div>
    </div>
  )
}

function SignalCard({
  onAccept,
  onDelete,
  onDismiss,
  onRestore,
  signal,
}: {
  signal: GroupLearningSignal
  onAccept: () => void
  onDelete: () => void
  onDismiss: () => void
  onRestore: () => void
}) {
  const isDismissed = signal.status === 'dismissed'
  const isAccepted = signal.status === 'accepted'

  return (
    <article className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm transition hover:border-indigo-200 hover:shadow-md">
      <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="p-4 sm:p-5">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-3 py-1 text-xs font-black ${signal.accentClass}`}>
              {getSignalTypeLabel(signal.type)}
            </span>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">
              {signal.sourceTime}
            </span>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600">
              可信度 {Math.round(signal.confidence * 100)}%
            </span>
            {isAccepted ? <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-black text-emerald-700">已接受</span> : null}
            {isDismissed ? <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-black text-slate-500">已忽略</span> : null}
          </div>

          <h3 className="mt-4 text-xl font-black leading-tight text-slate-950">{signal.title}</h3>
          <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50 px-4 py-3">
            <p className="text-xs font-black uppercase tracking-wide text-slate-400">来源消息</p>
            <p className="mt-2 text-base font-bold leading-7 text-slate-900">“{signal.sourceText}”</p>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <InfoBlock icon={<Sparkles className="size-4" />} title="系统解释" text={signal.explanation} />
            <InfoBlock icon={<GraduationCap className="size-4" />} title="推荐动作" text={signal.recommendation} />
          </div>
        </div>

        <div className="border-t border-slate-100 bg-slate-50 p-4 lg:border-l lg:border-t-0">
          <p className="text-xs font-black uppercase tracking-wide text-slate-500">接受后写入</p>
          <p className="mt-2 text-sm font-bold leading-6 text-slate-800">{signal.target}</p>
          <div className="mt-5 grid gap-2">
            {isDismissed ? (
              <Button variant="secondary" className="justify-between" onClick={onRestore}>
                恢复线索<ChevronRight className="size-4" />
              </Button>
            ) : (
              <Button className="justify-between bg-primary hover:bg-primary/90" onClick={onAccept} disabled={isAccepted}>
                {isAccepted ? '已处理' : signal.actionLabel}<ChevronRight className="size-4" />
              </Button>
            )}
            {!isDismissed && !isAccepted ? (
              <Button variant="secondary" className="justify-between" onClick={onDismiss}>
                忽略<X className="size-4" />
              </Button>
            ) : null}
            <Button variant="danger" className="justify-between" onClick={onDelete}>
              删除<Trash2 className="size-4" />
            </Button>
          </div>
        </div>
      </div>
    </article>
  )
}

function SourceSetupPanel({ sources }: { sources: GroupLearningSource[] }) {
  const activeSources = sources.filter((source) => source.status === 'active')
  const participantCount = sources.reduce((sum, source) => sum + source.participant_count, 0)
  const retentionDays = sources[0]?.raw_retention_days ?? 7
  const sourceNames = sources.map((source) => source.display_name).join(' / ') || '还没有飞书群来源'

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-base font-black text-slate-950">来源与成员</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">第一版按指定群和已映射成员处理。</p>
        </div>
        <MessageCircle className="size-5 text-primary" />
      </div>

      <div className="mt-4 space-y-3">
        <SetupRow icon={<ShieldCheck className="size-4" />} label="飞书群来源" value={`${sourceNames}；${activeSources.length} 个活跃`} />
        <SetupRow icon={<UserRoundCheck className="size-4" />} label="成员映射" value={`${participantCount} 位已发现成员，只有 learner 且开启分析才会抽取`} />
        <SetupRow icon={<Database className="size-4" />} label="原始消息保留" value={`${retentionDays} 天后自动清理，可随时删除缓存`} />
        <SetupRow icon={<Tags className="size-4" />} label="标签识别" value="#单词 #语法 #收藏 #怎么说 #纠错" />
      </div>
    </section>
  )
}

function PipelinePanel() {
  const steps = [
    { icon: <MessageCircle className="size-4" />, label: '群消息读取' },
    { icon: <Highlighter className="size-4" />, label: '清洗与去重' },
    { icon: <UserRoundCheck className="size-4" />, label: '成员映射' },
    { icon: <Sparkles className="size-4" />, label: '线索抽取' },
    { icon: <BookMarked className="size-4" />, label: '写入学习资产' },
  ]

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <FileText className="size-5 text-primary" />
        <h2 className="text-base font-black text-slate-950">处理 Pipeline</h2>
      </div>
      <div className="mt-4 grid gap-2">
        {steps.map((step, index) => (
          <div key={step.label} className="flex items-center gap-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
            <span className="flex size-8 items-center justify-center rounded-lg bg-white text-primary shadow-sm">{step.icon}</span>
            <span className="min-w-0 flex-1 text-sm font-bold text-slate-800">{step.label}</span>
            <span className="text-xs font-black text-slate-400">{index + 1}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

function HeroMetric({
  label,
  tone,
  value,
}: {
  label: string
  tone: 'indigo' | 'amber' | 'sky' | 'emerald'
  value: string | number
}) {
  const toneClass = {
    indigo: 'text-primary',
    amber: 'text-amber-600',
    sky: 'text-sky-600',
    emerald: 'text-emerald-600',
  }[tone]

  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 px-4 py-3">
      <p className="text-xs font-bold text-slate-500">{label}</p>
      <p className={`mt-1 text-3xl font-black ${toneClass}`}>{value}</p>
    </div>
  )
}

function InfoBlock({ icon, text, title }: { icon: React.ReactNode; text: string; title: string }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-white p-3">
      <div className="flex items-center gap-2 text-primary">
        {icon}
        <p className="text-xs font-black uppercase tracking-wide">{title}</p>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-600">{text}</p>
    </div>
  )
}

function SetupRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="grid grid-cols-[32px_minmax(0,1fr)] gap-3 rounded-lg border border-slate-100 bg-slate-50 p-3">
      <span className="flex size-8 items-center justify-center rounded-lg bg-white text-primary shadow-sm">{icon}</span>
      <span className="min-w-0">
        <span className="block text-xs font-black text-slate-500">{label}</span>
        <span className="mt-1 block text-sm font-bold leading-6 text-slate-900">{value}</span>
      </span>
    </div>
  )
}

function getSignalTypeLabel(type: GroupLearningSignal['type']) {
  const labels: Record<GroupLearningSignal['type'], string> = {
    desired_grammar: '想学语法',
    desired_vocabulary: '想学单词',
    expression_gap: '表达缺口',
    good_sentence: '好句候选',
    grammar_correct_usage: '正确使用',
    grammar_error: '语法错误',
    note_candidate: '笔记候选',
  }
  return labels[type]
}

function toSignalCard(signal: ApiGroupLearningSignal): GroupLearningSignal {
  return {
    id: signal.id,
    type: toSignalType(signal.signal_type),
    category: toSignalCategory(signal.category),
    status: signal.status === 'accepted' ? 'accepted' : signal.status === 'dismissed' ? 'dismissed' : 'candidate',
    title: signal.target_label,
    sourceText: signal.evidence_text,
    explanation: signal.normalized_note || signal.recommendation_reason,
    recommendation: signal.recommendation_reason,
    target: targetDescription(signal),
    confidence: signal.confidence,
    sourceTime: formatSignalTime(signal.source_time || signal.created_at),
    actionLabel: actionLabel(signal.signal_type),
    accentClass: accentClass(signal.signal_type),
  }
}

function toSignalType(value: string): GroupLearningSignal['type'] {
  if (value === 'grammar_error' || value === 'grammar_correct_usage' || value === 'expression_gap' || value === 'desired_vocabulary' || value === 'desired_grammar' || value === 'good_sentence' || value === 'note_candidate') {
    return value
  }
  return 'note_candidate'
}

function toSignalCategory(value: string): GroupLearningSignal['category'] {
  if (value === 'expression_gap' || value === 'grammar' || value === 'intent' || value === 'vocabulary' || value === 'sentence' || value === 'note') {
    return value
  }
  return 'intent'
}

function targetDescription(signal: ApiGroupLearningSignal) {
  if (signal.applied_target_type) return `已写入 ${signal.applied_target_type}`
  if (signal.signal_type === 'desired_vocabulary') return '写入词汇候选和词汇详解入口'
  if (signal.signal_type === 'good_sentence' || signal.signal_type === 'expression_gap') return '写入好句候选和表达练习'
  if (signal.signal_type === 'grammar_error') return '写入语法推荐和学习画像弱点'
  if (signal.signal_type === 'grammar_correct_usage') return '写入语法熟练度弱证据'
  return '写入个人笔记候选'
}

function actionLabel(signalType: string) {
  if (signalType === 'desired_vocabulary') return '加入词汇候选'
  if (signalType === 'good_sentence') return '加入好句'
  if (signalType === 'grammar_error' || signalType === 'desired_grammar') return '加入语法推荐'
  if (signalType === 'grammar_correct_usage') return '记录证据'
  return '加入学习计划'
}

function accentClass(signalType: string) {
  if (signalType === 'grammar_error') return 'border-rose-200 bg-rose-50 text-rose-800'
  if (signalType === 'grammar_correct_usage') return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  if (signalType === 'good_sentence') return 'border-amber-200 bg-amber-50 text-amber-800'
  if (signalType === 'note_candidate') return 'border-slate-200 bg-slate-50 text-slate-700'
  return 'border-indigo-200 bg-indigo-50 text-indigo-800'
}

function formatSignalTime(value?: string | null) {
  if (!value) return '时间未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
