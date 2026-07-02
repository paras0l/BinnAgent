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
import { FeatureHero } from '@/components/layout/FeatureHero'
import { PageShell } from '@/components/layout/PageShell'
import { Button } from '@/components/ui/Button'
import { FilterChip } from '@/components/ui/FilterChip'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import { ReasonCard } from '@/components/learning/ReasonCard'
import type { AppTab, ExplorePreference, Learner, PronunciationWorkspace } from '@/types'
import { useToast } from '@/hooks/useToast'
import { GrammarPage } from '@/pages/GrammarPage'
import { ReadingWorkshopPage } from '@/pages/ReadingWorkshopPage'
import { VocabularyDetailPage } from '@/pages/VocabularyDetailPage'
import { WordPartsPage } from '@/pages/WordPartsPage'
import { WritingPhrasebookPage } from '@/pages/WritingPhrasebookPage'

type FeatureCategory = 'all' | 'listening' | 'speaking' | 'reading' | 'writing' | 'vocabulary' | 'grammar' | 'exam'
type FeatureStatus = 'ready' | 'todo'
type FeatureAction = 'chat' | 'session' | 'tool' | 'vocabulary-detail' | 'todo'

interface ExplorePageProps {
  learner: Learner
  isLocked?: boolean
  onLockedAction?: () => void
  onTabChange: (tab: AppTab) => void
  onDraftPrompt: (prompt: string, skillFocus?: string | null) => void
  onOpenPronunciationWorkspace: (workspace: PronunciationWorkspace) => void
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
  toolTarget?: 'dashboard' | 'pronunciation' | 'grammar' | 'writing-phrasebook' | 'word-parts' | 'reading-workshop'
  pronunciationWorkspace?: PronunciationWorkspace
}

interface ExploreSkillStartResponse {
  episode_id: string
  task_spec: {
    task_id: string
    task_type: string
  } | null
  status: string
  answer_required: boolean
  prompt?: string | null
  initial_payload: Record<string, unknown>
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
    id: 'vocabulary-detail',
    category: 'vocabulary',
    title: '词汇详解',
    description: '输入一个单词或词组，生成聚焦词义、搭配、语境和易错点的微课。',
    whenToUse: '遇到一个词只知道中文意思，想进一步理解真实用法和常见搭配时使用。',
    outcome: '获得包含核心义项、搭配、分级例句、易混辨析和练习的 HTML 详解。',
    status: 'ready',
    action: 'vocabulary-detail',
  },
  {
    id: 'word-roots-affixes',
    category: 'vocabulary',
    title: '词根与词缀',
    description: '学习常见词根、前缀和后缀，掌握用构词法理解新词的方法。',
    whenToUse: '背单词总是靠中文意思硬记，或遇到新词想根据词形先猜含义时使用。',
    outcome: '建立常见词根词缀库，并在词汇详解和单词训练中看到拆词线索。',
    status: 'ready',
    action: 'tool',
    toolTarget: 'word-parts',
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
    id: 'reading-intensive-extensive',
    category: 'reading',
    title: '精读与泛读',
    description: '同一篇材料，精读看结构，泛读抓主旨。',
    whenToUse: '想提升阅读能力，而不是只做题；需要既能快速抓主旨，也能慢下来读懂难句时使用。',
    outcome: '获得主旨理解、段落功能、难句拆解、语法点提示，并能跳转到语法微知识点继续学习。',
    status: 'ready',
    action: 'tool',
    toolTarget: 'reading-workshop',
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
    id: 'writing-phrasebook',
    category: 'writing',
    title: '好句收藏馆',
    description: '收藏常用句式、固定搭配、递进表达和作文高分句，并通过练习真正掌握。',
    whenToUse: '想积累作文表达、替换低级连接词、整理外部模型生成的好句时使用。',
    outcome: '形成可编辑的个人句式资产库，并通过填空、替换、造句等练习检测掌握情况。',
    status: 'ready',
    action: 'tool',
    toolTarget: 'writing-phrasebook',
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
    pronunciationWorkspace: 'phonetic',
  },
  {
    id: 'shadowing-practice',
    category: 'speaking',
    title: '影子跟读训练',
    description: '听一句，跟一句，模仿真实表达的节奏、重音和语调。',
    whenToUse: '句子会读但不自然、语调平、停顿生硬，想模仿更地道表达时使用。',
    outcome: '获得分块跟读稿、重音提示、语调提示和可复习的口语训练记录。',
    status: 'ready',
    action: 'tool',
    toolTarget: 'pronunciation',
    pronunciationWorkspace: 'shadowing',
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

const FEATURE_SKILL_MAP: Record<string, string> = {
  'daily-lesson': 'knowledge_practice',
  'vocab-review': 'vocabulary_practice',
  'vocabulary-detail': 'vocabulary_practice',
  'word-roots-affixes': 'vocabulary_practice',
  'add-vocabulary': 'vocabulary_practice',
  'vocabulary-manager': 'vocabulary_practice',
  'essay-review': 'writing_phrase_practice',
  'writing-phrasebook': 'writing_phrase_practice',
  'grammar-explain': 'grammar_micro_lesson',
  'translation-practice': 'writing_phrase_practice',
}

export function ExplorePage({
  learner,
  isLocked = false,
  onLockedAction,
  onTabChange,
  onDraftPrompt,
  onOpenPronunciationWorkspace,
}: ExplorePageProps) {
  const { showToast } = useToast()
  const [preferences, setPreferences] = useState<ExplorePreference[]>([])
  const [category, setCategory] = useState<FeatureCategory>('all')
  const [query, setQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isVocabularyDetailOpen, setIsVocabularyDetailOpen] = useState(false)
  const [isGrammarOpen, setIsGrammarOpen] = useState(false)
  const [isReadingWorkshopOpen, setIsReadingWorkshopOpen] = useState(false)
  const [isWritingPhrasebookOpen, setIsWritingPhrasebookOpen] = useState(false)
  const [isWordPartsOpen, setIsWordPartsOpen] = useState(false)
  const [launchingFeatureId, setLaunchingFeatureId] = useState<string | null>(null)

  const loadPreferences = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`/api/learners/${learner.id}/explore/preferences`)
      if (!response.ok) throw new Error('Failed to load explore preferences')
      const data: ExplorePreference[] = await response.json()
      setPreferences(data)
    } catch (err) {
      console.error('Explore preferences error:', err)
      showToast('探索偏好暂时无法加载，功能入口仍可使用。', { variant: 'warning' })
    } finally {
      setIsLoading(false)
    }
  }, [learner.id, showToast])

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
  const recommendedFeatures = useMemo(() => {
    const preferred = FEATURES.filter((feature) => ['word-roots-affixes', 'writing-phrasebook', 'vocab-review'].includes(feature.id))
    return preferred.filter((feature) => category === 'all' || feature.category === category).slice(0, 3)
  }, [category])

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
      showToast('收藏状态保存失败，请稍后重试。', { variant: 'error' })
    }
  }

  const handleLaunch = async (feature: ExploreFeature) => {
    if (isLocked) {
      onLockedAction?.()
      return
    }

    if (feature.status === 'todo' || feature.action === 'todo') {
      showToast(`${feature.title}：功能待开发。${feature.outcome}`, {
        variant: 'info',
        duration: 6000,
      })
      return
    }

    const startedRuntime = await startExploreRuntime(feature)
    if (startedRuntime?.episode_id) {
      const url = new URL(window.location.href)
      url.hash = `episode_id=${startedRuntime.episode_id}`
      window.history.replaceState(null, '', url)
      showToast(`已创建 AgentEpisode：${startedRuntime.episode_id.slice(0, 8)}...`, {
        variant: startedRuntime.status === 'not_implemented' ? 'warning' : 'success',
      })
    }

    try {
      await updatePreference(feature, { mark_used: true })
    } catch (err) {
      console.error('Feature usage update error:', err)
    }

    if (feature.action === 'chat' && feature.prompt) {
      if (feature.id === 'essay-review') {
        onDraftPrompt(
          `${feature.prompt}\n\n如果作文中多次出现 First / Second / Third 或低级连接词，请推荐我进入“好句收藏馆”沉淀可替换句式。`,
          null
        )
      } else {
        onDraftPrompt(feature.prompt, feature.category === 'vocabulary' ? 'vocabulary_deposit' : null)
      }
      onTabChange('chat')
      return
    }

    if (feature.action === 'vocabulary-detail') {
      setIsVocabularyDetailOpen(true)
      return
    }

    if (feature.action === 'tool' && feature.toolTarget) {
      if (feature.toolTarget === 'grammar') {
        setIsGrammarOpen(true)
        return
      }
      if (feature.toolTarget === 'reading-workshop') {
        setIsReadingWorkshopOpen(true)
        return
      }
      if (feature.toolTarget === 'writing-phrasebook') {
        setIsWritingPhrasebookOpen(true)
        return
      }
      if (feature.toolTarget === 'word-parts') {
        setIsWordPartsOpen(true)
        return
      }
      if (feature.toolTarget === 'pronunciation') {
        onOpenPronunciationWorkspace(feature.pronunciationWorkspace ?? 'phonetic')
        return
      }
      onTabChange(feature.toolTarget)
      return
    }

    if (feature.action === 'session') {
      onDraftPrompt('开始今日课程。请根据我的学习记录安排一次适合 CET 的综合练习。')
      onTabChange('chat')
    }
  }

  const startExploreRuntime = async (feature: ExploreFeature): Promise<ExploreSkillStartResponse | null> => {
    const skillId = FEATURE_SKILL_MAP[feature.id]
    if (!skillId) return null
    setLaunchingFeatureId(feature.id)
    try {
      const response = await fetch(`/api/explore/skills/${skillId}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          learner_id: learner.id,
          metadata: {
            feature_id: feature.id,
            feature_title: feature.title,
            category: feature.category,
          },
        }),
      })
      if (!response.ok) throw new Error('Explore skill start failed')
      return await response.json() as ExploreSkillStartResponse
    } catch (err) {
      console.error('Explore skill runtime start error:', err)
      showToast('Runtime episode 创建失败，已继续打开原功能入口。', { variant: 'warning' })
      return null
    } finally {
      setLaunchingFeatureId(null)
    }
  }

  if (isVocabularyDetailOpen) {
    return (
      <VocabularyDetailPage learner={learner} term="" onBack={() => setIsVocabularyDetailOpen(false)} backLabel="返回探索" />
    )
  }

  if (isGrammarOpen) {
    return <GrammarPage learner={learner} onBack={() => setIsGrammarOpen(false)} />
  }

  if (isReadingWorkshopOpen) {
    return <ReadingWorkshopPage learner={learner} onBack={() => setIsReadingWorkshopOpen(false)} />
  }

  if (isWritingPhrasebookOpen) {
    return <WritingPhrasebookPage learner={learner} onBack={() => setIsWritingPhrasebookOpen(false)} />
  }

  if (isWordPartsOpen) {
    return <WordPartsPage learner={learner} onBack={() => setIsWordPartsOpen(false)} />
  }

  return (
    <PageShell>
      <FeatureHero
        eyebrow="Explore"
        title="探索专项技能"
        description="选择一个想加强的场景，进入对应练习；暂未开放的能力会清楚标记。"
        stats={[
          { label: '可用入口', value: FEATURES.filter((feature) => feature.status === 'ready').length, tone: 'success' },
          { label: '待开发', value: FEATURES.filter((feature) => feature.status === 'todo').length, tone: 'warning' },
          { label: '已收藏', value: favorites.length, tone: 'primary' },
          { label: '分类', value: CATEGORIES.length - 1 },
        ]}
        actions={
          <div className="relative w-full lg:w-80">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="w-full rounded-lg border bg-background py-2 pl-9 pr-3 text-sm outline-none transition-colors focus:border-primary"
              placeholder="搜索作文、阅读、词汇..."
            />
          </div>
        }
      />

      <SurfaceCard>
        <div className="flex gap-2 overflow-x-auto pb-1">
          {CATEGORIES.map((item) => (
            <FilterChip
              key={item.id}
              onClick={() => setCategory(item.id)}
              active={category === item.id}
            >
              {item.label}
            </FilterChip>
          ))}
        </div>
      </SurfaceCard>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-foreground">最近适合你</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {recommendedFeatures.map((feature) => (
            <ReasonCard
              key={`recommended-${feature.id}`}
              title={feature.title}
              reason={feature.whenToUse}
              evidence={[feature.category === 'vocabulary' ? '词汇复习是学习中心的高频任务' : feature.category === 'writing' ? '写作表达适合沉淀成可练习资产' : '语法微知识点适合短时间集中学透']}
              outcome={feature.outcome}
              action={<Button variant="secondary" onClick={() => void handleLaunch(feature)} disabled={isLocked || launchingFeatureId === feature.id}>进入工具</Button>}
            />
          ))}
        </div>
      </section>

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
                isLaunching={launchingFeatureId === feature.id}
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
              isLaunching={launchingFeatureId === feature.id}
              onLaunch={() => void handleLaunch(feature)}
              onToggleFavorite={() => void handleToggleFavorite(feature)}
            />
          ))}
        </div>
      </section>

    </PageShell>
  )
}

function FeatureCard({
  feature,
  isFavorite,
  isLoading,
  isLocked,
  isLaunching,
  onLaunch,
  onToggleFavorite,
}: {
  feature: ExploreFeature
  isFavorite: boolean
  isLoading: boolean
  isLocked: boolean
  isLaunching: boolean
  onLaunch: () => void
  onToggleFavorite: () => void
}) {
  const isTodo = feature.status === 'todo'
  return (
    <article className="flex min-h-[290px] flex-col rounded-[13px] border border-slate-200 bg-white p-4 shadow-[0_4px_14px_rgba(15,23,42,0.05)]">
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
        <Button
          onClick={onLaunch}
          disabled={isLocked || isLaunching}
          variant={isTodo ? 'secondary' : 'primary'}
          title={isLocked ? '回答生成中，请先等待完成或取消' : isTodo ? '查看说明' : '开始'}
        >
          {isLaunching ? '启动中' : isTodo ? '查看说明' : '开始'}
        </Button>
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
