import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  BookOpen,
  CheckCircle2,
  Clock3,
  Headphones,
  Mic,
  PenLine,
  Search,
  Sparkles,
  Star,
  StarOff,
  Timer,
  Wrench,
} from 'lucide-react'
import type { AppTab, ExplorePreference, Learner } from '@/types'

type FeatureCategory = 'all' | 'listening' | 'speaking' | 'reading' | 'writing' | 'vocabulary' | 'grammar' | 'exam'
type FeatureStatus = 'ready' | 'todo'
type FeatureAction = 'chat' | 'session' | 'tool' | 'todo'

interface ExplorePageProps {
  learner: Learner
  isLocked?: boolean
  onLockedAction?: () => void
  onTabChange: (tab: AppTab) => void
  onDraftPrompt: (prompt: string, skillFocus?: string | null) => void
}

interface ExploreFeature {
  id: string
  category: Exclude<FeatureCategory, 'all'>
  title: string
  description: string
  whenToUse: string
  outcome: string
  status: FeatureStatus
  action: FeatureAction
  prompt?: string
  toolTarget?: 'dashboard' | 'pronunciation' | 'grammar'
}

const CATEGORIES: Array<{ id: FeatureCategory; label: string }> = [
  { id: 'all', label: '全部' },
  { id: 'listening', label: '听力' },
  { id: 'speaking', label: '口语' },
  { id: 'reading', label: '阅读' },
  { id: 'writing', label: '写作' },
  { id: 'vocabulary', label: '词汇' },
  { id: 'grammar', label: '语法' },
  { id: 'exam', label: '考试冲刺' },
]

const FEATURES: ExploreFeature[] = [
  {
    id: 'daily-lesson',
    category: 'exam',
    title: '开始今日课程',
    description: '让 Agent 根据当前目标安排一次综合学习任务。',
    whenToUse: '不知道今天该学什么，想要直接进入一次完整练习时使用。',
    outcome: '生成今日目标、练习材料和反馈，并沉淀最近学习记录。',
    status: 'ready',
    action: 'session',
  },
  {
    id: 'vocab-review',
    category: 'vocabulary',
    title: '复习待掌握词汇',
    description: '进入学习中心复习系统安排的词卡。',
    whenToUse: '看到待复习数量增加，或想巩固最近遇到的词时使用。',
    outcome: '更新词汇熟练度、复习间隔和正确率。',
    status: 'ready',
    action: 'tool',
    toolTarget: 'dashboard',
  },
  {
    id: 'add-vocabulary',
    category: 'vocabulary',
    title: 'AI 词汇讲解沉淀',
    description: '懒人模式：把单词、句子或段落发给 AI，自动讲解重点词。',
    whenToUse: '不想手动逐个添加，想让 AI 从材料里提炼重点词并解释时使用。',
    outcome: 'AI 会讲解词义、用法和例句；高置信词汇会通过记忆抽取进入词汇记忆。',
    status: 'ready',
    action: 'chat',
    prompt: '请作为 CET 词汇教练，帮我从下面的单词、句子或阅读段落中提炼值得记忆的重点词。请按「单词 / 中文释义 / 常见搭配 / 例句 / 记忆提示」输出，并优先解释四六级高频词。材料如下：\n\n',
  },
  {
    id: 'vocabulary-manager',
    category: 'vocabulary',
    title: '词汇本管理',
    description: '手动模式：进入学习中心精确添加新词、查看待复习词卡。',
    whenToUse: '已经知道要保存哪个单词，或想手动维护词汇本和复习计划时使用。',
    outcome: '手动创建真实词卡，并通过学习中心进行复习评分。',
    status: 'ready',
    action: 'tool',
    toolTarget: 'dashboard',
  },
  {
    id: 'cet-reading',
    category: 'reading',
    title: 'CET 阅读定位训练',
    description: '让 AI 出一题阅读定位题，并逐步讲解解题路径。',
    whenToUse: '做阅读时经常找不到依据句，或容易忽略转折、因果时使用。',
    outcome: '训练定位、排除干扰项和错因复盘。',
    status: 'ready',
    action: 'chat',
    prompt: '请作为 CET-6 阅读教练，给我一题转折定位题。先出题和选项，等我作答后再逐步讲解依据句、干扰项和错因。',
  },
  {
    id: 'essay-review',
    category: 'writing',
    title: '作文批改',
    description: '让 AI 按四六级写作标准批改结构、语法和用词。',
    whenToUse: '写完一段作文但不确定语法、结构和表达是否自然时使用。',
    outcome: '得到分项反馈，并沉淀可迁移错因。',
    status: 'ready',
    action: 'chat',
    prompt: '请作为 CET-4/CET-6 写作老师批改我的作文。请按结构、语法、词汇、内容四项反馈，并提炼我的主要错因。作文如下：\n\n',
  },
  {
    id: 'grammar-explain',
    category: 'grammar',
    title: '语法微知识点',
    description: '按分类选择一个小语法点，用外部 AI 生成精讲 HTML。',
    whenToUse: '遇到主将从现、because 与 because of、which/that 选择这类小规则，想集中学透时使用。',
    outcome: '复制受控 prompt，跳转 DeepSeek 等网站生成 HTML，回到原页面阅读精讲。',
    status: 'ready',
    action: 'tool',
    toolTarget: 'grammar',
  },
  {
    id: 'translation-practice',
    category: 'writing',
    title: '翻译练习',
    description: '进行中文到英文的四六级翻译训练。',
    whenToUse: '想练习长句拆分、词组搭配和中式英语修正时使用。',
    outcome: '获得参考译文、表达替换和错误分析。',
    status: 'ready',
    action: 'chat',
    prompt: '请给我一段 CET-6 风格中文翻译题。等我翻译后，请从准确性、语法、词汇和表达自然度四方面反馈。',
  },
  {
    id: 'speaking-roleplay',
    category: 'speaking',
    title: '口语场景模拟',
    description: '用文本方式模拟口语对话场景。',
    whenToUse: '想练习自我介绍、校园交流、观点表达，但暂时不需要录音评分时使用。',
    outcome: '获得可跟读表达、追问和口语替换句。',
    status: 'ready',
    action: 'chat',
    prompt: '请和我进行 CET 口语场景模拟。主题是校园学习计划。你先扮演考官提问，每次只问一个问题，并在我回答后给出更自然的表达建议。',
  },
  {
    id: 'phonetic-association',
    category: 'speaking',
    title: '音标图像联想训练',
    description: '用 48 张图像联想卡片记住常见音标，并跟读重点音素。',
    whenToUse: '音标不熟、单词发音常靠猜，或想系统补一遍口语基础时使用。',
    outcome: '进入音标训练页，完成卡片、跟读、连读弱读、重音和语调练习。',
    status: 'ready',
    action: 'tool',
    toolTarget: 'pronunciation',
  },
  {
    id: 'listening-intensive',
    category: 'listening',
    title: '听力音频精听',
    description: '上传或选择音频后做逐句精听、听写和跟读。',
    whenToUse: '听力材料听不清、想做逐句听写和弱读分析时使用。',
    outcome: '后续会支持音频、转写、逐句讲解和复听计划。',
    status: 'todo',
    action: 'todo',
  },
  {
    id: 'speaking-record-score',
    category: 'speaking',
    title: '口语录音评分',
    description: '录音后分析发音、流利度和表达自然度。',
    whenToUse: '想知道自己的发音、停顿和语调问题时使用。',
    outcome: '功能待接入录音采集和语音评分模型。',
    status: 'todo',
    action: 'todo',
  },
  {
    id: 'mock-exam-timer',
    category: 'exam',
    title: '真题套卷计时',
    description: '按考试时间完成一套题，并输出分项报告。',
    whenToUse: '考前需要模拟真实时间压力和定位薄弱模块时使用。',
    outcome: '功能待接入真题套卷、计时器和报告生成。',
    status: 'todo',
    action: 'todo',
  },
  {
    id: 'error-drill-generator',
    category: 'exam',
    title: '错题专项训练',
    description: '根据错因自动生成专项训练。',
    whenToUse: '错因 Top 5 已经沉淀，希望针对薄弱点集中练习时使用。',
    outcome: '功能待接入错因到题目生成的完整链路。',
    status: 'todo',
    action: 'todo',
  },
]

export function ExplorePage({
  learner,
  isLocked = false,
  onLockedAction,
  onTabChange,
  onDraftPrompt,
}: ExplorePageProps) {
  const [preferences, setPreferences] = useState<ExplorePreference[]>([])
  const [category, setCategory] = useState<FeatureCategory>('all')
  const [query, setQuery] = useState('')
  const [message, setMessage] = useState('')
  const [isLoading, setIsLoading] = useState(true)

  const loadPreferences = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`/api/learners/${learner.id}/explore/preferences`)
      if (!response.ok) throw new Error('Failed to load explore preferences')
      const data: ExplorePreference[] = await response.json()
      setPreferences(data)
    } catch (err) {
      console.error('Explore preferences error:', err)
      setMessage('探索偏好暂时无法加载，功能入口仍可使用。')
    } finally {
      setIsLoading(false)
    }
  }, [learner.id])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadPreferences(), 0)
    return () => window.clearTimeout(timer)
  }, [loadPreferences])

  const preferenceMap = useMemo(
    () => new Map(preferences.map((preference) => [preference.feature_id, preference])),
    [preferences]
  )

  const visibleFeatures = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return FEATURES
      .filter((feature) => category === 'all' || feature.category === category)
      .filter((feature) => {
        if (!normalizedQuery) return true
        return [feature.title, feature.description, feature.whenToUse, feature.outcome]
          .join(' ')
          .toLowerCase()
          .includes(normalizedQuery)
      })
      .sort((a, b) => {
        const prefA = preferenceMap.get(a.id)
        const prefB = preferenceMap.get(b.id)
        const favoriteDelta = Number(Boolean(prefB?.is_favorite)) - Number(Boolean(prefA?.is_favorite))
        if (favoriteDelta !== 0) return favoriteDelta
        const priorityDelta = (prefB?.priority ?? 0) - (prefA?.priority ?? 0)
        if (priorityDelta !== 0) return priorityDelta
        const usedDelta = Date.parse(prefB?.last_used_at ?? '') - Date.parse(prefA?.last_used_at ?? '')
        if (!Number.isNaN(usedDelta) && usedDelta !== 0) return usedDelta
        return a.title.localeCompare(b.title)
      })
  }, [category, preferenceMap, query])

  const favorites = visibleFeatures.filter((feature) => preferenceMap.get(feature.id)?.is_favorite)

  const updatePreference = async (
    feature: ExploreFeature,
    payload: { is_favorite?: boolean; priority?: number; mark_used?: boolean }
  ) => {
    const response = await fetch(`/api/learners/${learner.id}/explore/preferences/${feature.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!response.ok) throw new Error('Failed to update explore preference')
    const updated: ExplorePreference = await response.json()
    setPreferences((prev) => {
      const others = prev.filter((item) => item.feature_id !== updated.feature_id)
      return [...others, updated]
    })
  }

  const handleToggleFavorite = async (feature: ExploreFeature) => {
    if (isLocked) {
      onLockedAction?.()
      setMessage('回答生成中，请先等待完成或点击取消。')
      return
    }
    const current = preferenceMap.get(feature.id)
    const nextFavorite = !current?.is_favorite
    try {
      await updatePreference(feature, {
        is_favorite: nextFavorite,
        priority: nextFavorite ? Math.max(current?.priority ?? 0, 100) : 0,
      })
    } catch (err) {
      console.error('Favorite update error:', err)
      setMessage('收藏状态保存失败，请稍后重试。')
    }
  }

  const handleLaunch = async (feature: ExploreFeature) => {
    if (isLocked) {
      onLockedAction?.()
      setMessage('回答生成中，请先等待完成或点击取消。')
      return
    }

    if (feature.status === 'todo' || feature.action === 'todo') {
      setMessage(`${feature.title}：功能待开发。${feature.outcome}`)
      return
    }

    try {
      await updatePreference(feature, { mark_used: true })
    } catch (err) {
      console.error('Feature usage update error:', err)
    }

    if (feature.action === 'chat' && feature.prompt) {
      onDraftPrompt(feature.prompt, feature.category === 'vocabulary' ? 'vocabulary_deposit' : null)
      onTabChange('chat')
      return
    }

    if (feature.action === 'tool' && feature.toolTarget) {
      onTabChange(feature.toolTarget)
      return
    }

    if (feature.action === 'session') {
      onDraftPrompt('开始今日课程。请根据我的学习记录安排一次适合 CET 的综合练习。')
      onTabChange('chat')
    }
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-6">
      <section className="rounded-xl border bg-card p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-2 text-primary">
              <Sparkles className="h-5 w-5" />
              <span className="text-sm font-semibold">探索</span>
            </div>
            <h1 className="mt-2 text-2xl font-bold text-foreground">选择一个学习技能入口</h1>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              按场景选择功能。可用功能会进入真实学习流程，复杂能力会明确标记待开发。
            </p>
          </div>
          <div className="relative w-full lg:w-80">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="w-full rounded-lg border bg-background py-2 pl-9 pr-3 text-sm outline-none transition-colors focus:border-primary"
              placeholder="搜索作文、阅读、词汇..."
            />
          </div>
        </div>

        <div className="mt-5 flex gap-2 overflow-x-auto pb-1">
          {CATEGORIES.map((item) => (
            <button
              key={item.id}
              onClick={() => setCategory(item.id)}
              className={`shrink-0 rounded-lg border px-3 py-2 text-sm transition-colors ${
                category === item.id
                  ? 'border-primary bg-primary/10 font-medium text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </section>

      {message && (
        <div className="rounded-lg border border-warning/30 bg-warning/5 px-4 py-3 text-sm text-foreground">
          {message}
        </div>
      )}

      {favorites.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold text-foreground">我的常用</h2>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {favorites.map((feature) => (
              <FeatureCard
                key={`favorite-${feature.id}`}
                feature={feature}
                isFavorite
                isLoading={isLoading}
                isLocked={isLocked}
                onLaunch={() => void handleLaunch(feature)}
                onToggleFavorite={() => void handleToggleFavorite(feature)}
              />
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="mb-3 text-sm font-semibold text-foreground">全部入口</h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visibleFeatures.map((feature) => (
            <FeatureCard
              key={feature.id}
              feature={feature}
              isFavorite={Boolean(preferenceMap.get(feature.id)?.is_favorite)}
              isLoading={isLoading}
              isLocked={isLocked}
              onLaunch={() => void handleLaunch(feature)}
              onToggleFavorite={() => void handleToggleFavorite(feature)}
            />
          ))}
        </div>
      </section>
    </div>
  )
}

function FeatureCard({
  feature,
  isFavorite,
  isLoading,
  isLocked,
  onLaunch,
  onToggleFavorite,
}: {
  feature: ExploreFeature
  isFavorite: boolean
  isLoading: boolean
  isLocked: boolean
  onLaunch: () => void
  onToggleFavorite: () => void
}) {
  const isTodo = feature.status === 'todo'
  return (
    <article className="flex min-h-[260px] flex-col rounded-xl border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <CategoryIcon category={feature.category} />
          </div>
          <div>
            <p className="text-xs text-muted-foreground">{labelForCategory(feature.category)}</p>
            <h3 className="text-base font-semibold text-foreground">{feature.title}</h3>
          </div>
        </div>
        <button
          onClick={onToggleFavorite}
          disabled={isLoading || isLocked}
          className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-warning disabled:opacity-50"
          title={isLocked ? '回答生成中，请先等待完成或取消' : isFavorite ? '取消收藏' : '收藏入口'}
        >
          {isFavorite ? <Star className="h-4 w-4 fill-warning text-warning" /> : <StarOff className="h-4 w-4" />}
        </button>
      </div>

      <p className="mt-3 text-sm text-muted-foreground">{feature.description}</p>
      <div className="mt-4 space-y-3 text-sm">
        <InfoLine label="什么时候用" text={feature.whenToUse} />
        <InfoLine label="会得到什么" text={feature.outcome} />
      </div>

      <div className="mt-auto flex items-center justify-between gap-3 pt-4">
        <span
          className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium ${
            isTodo
              ? 'bg-warning/10 text-warning'
              : 'bg-success/10 text-success'
          }`}
        >
          {isTodo ? <Clock3 className="h-3 w-3" /> : <CheckCircle2 className="h-3 w-3" />}
          {isTodo ? '功能待开发' : '可体验'}
        </span>
        <button
          onClick={onLaunch}
          disabled={isLocked}
          className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
            isTodo
              ? 'border text-muted-foreground hover:bg-muted'
              : 'bg-primary text-primary-foreground hover:bg-primary/90'
          } disabled:cursor-not-allowed disabled:opacity-50`}
          title={isLocked ? '回答生成中，请先等待完成或取消' : isTodo ? '查看说明' : '开始'}
        >
          {isTodo ? '查看说明' : '开始'}
        </button>
      </div>
    </article>
  )
}

function InfoLine({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <p className="text-xs font-medium text-foreground">{label}</p>
      <p className="mt-1 text-sm text-muted-foreground">{text}</p>
    </div>
  )
}

function CategoryIcon({ category }: { category: ExploreFeature['category'] }) {
  const className = 'h-4 w-4'
  if (category === 'listening') return <Headphones className={className} />
  if (category === 'speaking') return <Mic className={className} />
  if (category === 'reading') return <BookOpen className={className} />
  if (category === 'writing') return <PenLine className={className} />
  if (category === 'vocabulary') return <Sparkles className={className} />
  if (category === 'grammar') return <Wrench className={className} />
  return <Timer className={className} />
}

function labelForCategory(category: ExploreFeature['category']) {
  const labels = {
    listening: '听力',
    speaking: '口语',
    reading: '阅读',
    writing: '写作',
    vocabulary: '词汇',
    grammar: '语法',
    exam: '考试冲刺',
  }
  return labels[category]
}
