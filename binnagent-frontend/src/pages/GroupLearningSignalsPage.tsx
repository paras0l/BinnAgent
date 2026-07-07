import { useMemo, useState } from 'react'
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

const initialSignals: GroupLearningSignal[] = [
  {
    id: 'sig-expression-absolute',
    type: 'expression_gap',
    category: 'expression_gap',
    status: 'candidate',
    title: '委婉反驳 / hedging',
    sourceText: '这个观点太绝对了',
    explanation: '这像是一个中文表达缺口，适合沉淀成英语观点表达。',
    recommendation: 'That claim may be too strong. / I think this view needs more nuance.',
    target: '写入好句候选、语法推荐和表达练习',
    confidence: 0.86,
    sourceTime: '今天 20:31',
    actionLabel: '加入学习计划',
    accentClass: 'border-indigo-200 bg-indigo-50 text-indigo-800',
  },
  {
    id: 'sig-grammar-agree',
    type: 'grammar_error',
    category: 'grammar',
    status: 'candidate',
    title: 'agree 不需要 be',
    sourceText: 'I am agree with you.',
    explanation: 'agree 是动词，这里不需要 be。这个错误适合作为轻量复习证据。',
    recommendation: 'I agree with you. / I am in agreement with you.',
    target: '写入学习画像弱点和 GrammarPage 推荐',
    confidence: 0.93,
    sourceTime: '今天 20:18',
    actionLabel: '加入语法推荐',
    accentClass: 'border-rose-200 bg-rose-50 text-rose-800',
  },
  {
    id: 'sig-vocab-nuance',
    type: 'desired_vocabulary',
    category: 'vocabulary',
    status: 'candidate',
    title: 'nuance',
    sourceText: '#单词 nuance',
    explanation: '用户主动标记了想学单词，可信度高，可以直接进入词汇候选。',
    recommendation: 'nuance: 细微差别；可搭配 subtle nuance / add nuance。',
    target: '写入词汇候选和词汇详解入口',
    confidence: 0.98,
    sourceTime: '昨天 22:07',
    actionLabel: '加入词汇候选',
    accentClass: 'border-indigo-200 bg-indigo-50 text-indigo-800',
  },
  {
    id: 'sig-sentence-consistent',
    type: 'good_sentence',
    category: 'sentence',
    status: 'candidate',
    title: 'What matters most is not A, but B.',
    sourceText: '#收藏 What matters most is not how fast you learn, but how consistently you practice.',
    explanation: '这是可迁移的作文句式，适合进入好句收藏候选。',
    recommendation: '强调重点 / 对比结构，可用于观点强调和学习反思。',
    target: '写入好句收藏馆和写作短语本',
    confidence: 0.91,
    sourceTime: '昨天 21:42',
    actionLabel: '加入好句',
    accentClass: 'border-amber-200 bg-amber-50 text-amber-800',
  },
  {
    id: 'sig-grammar-perfect',
    type: 'grammar_correct_usage',
    category: 'grammar',
    status: 'candidate',
    title: '现在完成进行时正确使用',
    sourceText: 'I have been learning English for two months.',
    explanation: '自然聊天里的正确使用证据，权重低于正式练习，但可辅助画像判断。',
    recommendation: 'present perfect continuous +1；for + 时间段 +1；自然证据权重 0.3。',
    target: '写入语法熟练度弱证据',
    confidence: 0.79,
    sourceTime: '周一 19:11',
    actionLabel: '记录证据',
    accentClass: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  },
  {
    id: 'sig-note-simple',
    type: 'note_candidate',
    category: 'note',
    status: 'dismissed',
    title: '口语主题笔记',
    sourceText: '下次想聊电影和旅行主题',
    explanation: '可以作为泛读与口语话题候选，但这条暂时被忽略。',
    recommendation: '旅行经历、电影评价、偏好表达。',
    target: '写入个人笔记候选',
    confidence: 0.64,
    sourceTime: '上周五 18:02',
    actionLabel: '恢复线索',
    accentClass: 'border-slate-200 bg-slate-50 text-slate-700',
  },
]

interface GroupLearningSignalsPageProps {
  onBack: () => void
  onOpenSettings: () => void
}

export function GroupLearningSignalsPage({ onBack, onOpenSettings }: GroupLearningSignalsPageProps) {
  const { showToast } = useToast()
  const [signals, setSignals] = useState<GroupLearningSignal[]>(initialSignals)
  const [activeFilter, setActiveFilter] = useState<SignalCategory>('all')
  const [query, setQuery] = useState('')
  const [isPaused, setIsPaused] = useState(false)

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

  const updateSignalStatus = (id: string, status: SignalStatus) => {
    setSignals((items) => items.map((item) => item.id === id ? { ...item, status } : item))
  }

  const deleteSignal = (id: string) => {
    setSignals((items) => items.filter((item) => item.id !== id))
    showToast('已删除这条群聊学习线索。', { variant: 'success' })
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#f6f7f9]">
      <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
        <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white text-slate-950 shadow-sm">
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
                从指定微信群捕捉你想学的表达、语法、单词和好句。这里只分析已绑定学习者的文本消息，不做群内公开纠错。
              </p>
              <div className="mt-7 grid gap-3 sm:grid-cols-4">
                <HeroMetric label="待确认" value={stats.pending} tone="indigo" />
                <HeroMetric label="今日新增" value={stats.today} tone="amber" />
                <HeroMetric label="已接受" value={stats.accepted} tone="sky" />
                <HeroMetric label="平均可信度" value={`${stats.confidence}%`} tone="emerald" />
              </div>
            </div>

            <div className="rounded-[24px] border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-black text-slate-950">读取边界</p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">白名单群组、成员映射、短期保留。</p>
                </div>
                <ShieldCheck className="size-6 text-primary" />
              </div>
              <div className="mt-4 grid gap-2">
                {['只读取 2 个白名单群', '只分析 1 个已绑定成员', '原始消息保留 7 天', '未映射成员默认忽略'].map((item) => (
                  <div key={item} className="flex items-center gap-2 rounded-xl border border-slate-100 bg-white px-3 py-2 text-sm text-slate-700">
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
                    setIsPaused((value) => !value)
                    showToast(isPaused ? '已恢复群聊线索读取。' : '已暂停群聊线索读取。', {
                      variant: isPaused ? 'success' : 'warning',
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
          action={<Button variant="secondary" onClick={() => showToast('已发起一次手动同步。', { variant: 'success' })}><RefreshCw className="size-4" />同步一次</Button>}
        >
          {isPaused ? '系统不会读取新群消息，已有线索仍可确认或删除。' : '最后同步：今天 20:42。新消息会先去重，再进入线索抽取。'}
        </StatusBanner>

        <section className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="space-y-4">
            <div className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-sm">
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
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-9 pr-3 text-sm outline-none transition focus:border-primary focus:bg-white focus:ring-2 focus:ring-primary/20"
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
                    updateSignalStatus(signal.id, 'accepted')
                    showToast(`已${signal.actionLabel}。`, { variant: 'success' })
                  }}
                  onDelete={() => deleteSignal(signal.id)}
                  onDismiss={() => {
                    updateSignalStatus(signal.id, 'dismissed')
                    showToast('已忽略这条线索。', { variant: 'success' })
                  }}
                  onRestore={() => {
                    updateSignalStatus(signal.id, 'candidate')
                    showToast('已恢复到待确认。', { variant: 'success' })
                  }}
                />
              )) : (
                <div className="rounded-[24px] border border-dashed border-slate-300 bg-white p-10 text-center">
                  <Filter className="mx-auto size-8 text-slate-400" />
                  <p className="mt-3 text-sm font-black text-slate-950">没有匹配的线索</p>
                  <p className="mt-1 text-sm text-slate-500">换一个分组或关键词看看。</p>
                </div>
              )}
            </div>
          </div>

          <aside className="space-y-4">
            <SourceSetupPanel />
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
    <article className="overflow-hidden rounded-[24px] border border-slate-200 bg-white shadow-sm transition hover:border-indigo-200 hover:shadow-md">
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
          <div className="mt-3 rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
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

function SourceSetupPanel() {
  return (
    <section className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-base font-black text-slate-950">来源与成员</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">第一版按指定群和已映射成员处理。</p>
        </div>
        <MessageCircle className="size-5 text-primary" />
      </div>

      <div className="mt-4 space-y-3">
        <SetupRow icon={<ShieldCheck className="size-4" />} label="白名单群组" value="七年级英语学习搭子群 / 写作互助群" />
        <SetupRow icon={<UserRoundCheck className="size-4" />} label="成员映射" value="小林 -> 当前 learner；2 位成员仅作上下文" />
        <SetupRow icon={<Database className="size-4" />} label="原始消息保留" value="7 天后自动清理，可随时删除缓存" />
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
    <section className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <FileText className="size-5 text-primary" />
        <h2 className="text-base font-black text-slate-950">处理 Pipeline</h2>
      </div>
      <div className="mt-4 grid gap-2">
        {steps.map((step, index) => (
          <div key={step.label} className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2">
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
    <div className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
      <p className="text-xs font-bold text-slate-500">{label}</p>
      <p className={`mt-1 text-3xl font-black ${toneClass}`}>{value}</p>
    </div>
  )
}

function InfoBlock({ icon, text, title }: { icon: React.ReactNode; text: string; title: string }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-3">
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
    <div className="grid grid-cols-[32px_minmax(0,1fr)] gap-3 rounded-xl border border-slate-100 bg-slate-50 p-3">
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
