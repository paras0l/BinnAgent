import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Archive,
  BookMarked,
  Check,
  Clipboard,
  Copy,
  FileDown,
  Plus,
  RotateCcw,
  Save,
  Search,
  Sparkles,
  Star,
  StarOff,
  Trash2,
} from 'lucide-react'
import type { Learner } from '@/types'
import { useToast } from '@/hooks/useToast'

interface WritingPhrasebookPageProps {
  learner: Learner
  onBack: () => void
}

interface WritingPhrase {
  id: string
  text: string
  chinese_meaning?: string | null
  explanation?: string | null
  usage_scene?: string | null
  usage_position?: string | null
  tags: string[]
  examples: Array<{ sentence: string; translation?: string | null }>
  notes: string[]
  mistakes: string[]
  difficulty: number
  is_favorite: boolean
  is_archived: boolean
  review_enabled: boolean
  source_type: string
}

interface PhraseCandidate {
  text: string
  chinese_meaning?: string | null
  usage_scene?: string | null
  usage_position?: string | null
  tags: string[]
  examples: Array<{ sentence: string; translation?: string | null }>
  usage_notes: string[]
  mistakes: string[]
  quality_score: number
  warnings: string[]
}

interface PhraseExercise {
  id: string
  phrase_id: string
  exercise_type: 'recognition' | 'blank' | 'replacement'
  prompt: string
  answer: string
  options: string[]
  explanation?: string | null
}

interface PhraseForm {
  text: string
  chinese_meaning: string
  explanation: string
  usage_scene: string
  usage_position: string
  tags_text: string
  examples_text: string
  notes_text: string
  mistakes_text: string
  difficulty: number
  is_favorite: boolean
  review_enabled: boolean
}

const FUNCTION_TAGS = [
  '开头引入',
  '分层递进',
  '举例说明',
  '对比转折',
  '原因结果',
  '强调重点',
  '观点表达',
  '总结升华',
  '图表描述',
  '翻译表达',
  '议论文万能句',
  '我的收藏',
]

const TOPIC_TAGS = ['教育', '科技', '环保', '健康', '校园生活', '社会现象', '文化交流', '个人成长', '职业发展', '网络学习']

const TYPE_TAGS = ['固定搭配', '连接表达', '从句结构', '非谓语结构', '强调句', '被动表达', '比较结构', '让步结构', '因果结构', '高级替换']

const EMPTY_FORM: PhraseForm = {
  text: '',
  chinese_meaning: '',
  explanation: '',
  usage_scene: '',
  usage_position: 'body',
  tags_text: '分层递进, 连接表达',
  examples_text: '',
  notes_text: '',
  mistakes_text: '',
  difficulty: 2,
  is_favorite: false,
  review_enabled: false,
}

const PROMPTS = [
  {
    id: 'generate',
    label: '生成某类好句',
    text: `请作为 CET-4/CET-6 英语写作老师，帮我生成一组适合考试作文使用的高质量句式。

要求：
1. 主题方向：online learning
2. 句式功能：分层递进
3. 不要只给 First, Second, Third 这类基础表达。
4. 每个句式必须包含：
   - 英文句式
   - 中文含义
   - 适用场景
   - 适合放在开头/主体/结尾哪个位置
   - 1 个 CET 写作例句
   - 使用注意事项
   - 常见错误
5. 输出 8-12 条，难度从基础到进阶排列。
6. 不要写成长篇作文，只输出可收藏的句式卡片。`,
  },
  {
    id: 'extract',
    label: '从范文提取',
    text: `请作为英语写作表达分析助手，从下面这篇作文/范文中提取值得背诵和迁移的句式、固定搭配和高质量表达。

请按以下结构输出：
1. 原句
2. 中文含义
3. 句式功能：开头引入 / 分层递进 / 举例说明 / 对比转折 / 原因结果 / 强调重点 / 总结升华
4. 可替换模板：把原句改写成可迁移的句型框架
5. 适用场景
6. 使用注意事项
7. 常见错误
8. 一个新的 CET 写作例句

材料如下：

{粘贴作文/范文}`,
  },
  {
    id: 'optimize',
    label: '优化收藏',
    text: `请作为英语写作老师，帮我检查下面这些句式是否适合 CET 写作收藏和背诵。

请对每条句式给出：
1. 是否推荐收藏：推荐 / 可用但需谨慎 / 不推荐
2. 原因
3. 更自然或更适合考试的版本
4. 中文含义
5. 适用位置：开头 / 主体 / 结尾
6. 适用场景
7. 常见误用
8. 一个简单练习题，用来检测我是否会用这个句式

我的句式如下：

{粘贴句式列表}`,
  },
]

const DEMO_PHRASE: Omit<WritingPhrase, 'id' | 'is_archived' | 'source_type'> = {
  text: 'What is more noteworthy is that...',
  chinese_meaning: '更值得注意的一点是……',
  explanation: '用于在第二层论证中引出更重要、更深层的观点。',
  usage_scene: '当你已经提出第一个原因，还想补充一个更重要的原因时使用。',
  usage_position: 'body',
  tags: ['强调重点', '分层递进', '议论文万能句'],
  examples: [
    {
      sentence: 'What is more noteworthy is that online learning also requires strong self-discipline.',
      translation: '更值得注意的是，在线学习也需要强大的自律能力。',
    },
  ],
  notes: ['后面接完整句子，不要直接接名词短语。'],
  mistakes: ['不要用于作文第一句话；不要用于简单列举三个平级原因。'],
  difficulty: 3,
  is_favorite: true,
  review_enabled: true,
}

export function WritingPhrasebookPage({ learner, onBack }: WritingPhrasebookPageProps) {
  const { showToast } = useToast()
  const [phrases, setPhrases] = useState<WritingPhrase[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [activeTag, setActiveTag] = useState('全部')
  const [showArchived, setShowArchived] = useState(false)
  const [form, setForm] = useState<PhraseForm>(EMPTY_FORM)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [importText, setImportText] = useState('')
  const [importTopic, setImportTopic] = useState('online learning')
  const [candidates, setCandidates] = useState<PhraseCandidate[]>([])
  const [selectedCandidates, setSelectedCandidates] = useState<Set<number>>(new Set())
  const [exercises, setExercises] = useState<PhraseExercise[]>([])
  const [attemptAnswers, setAttemptAnswers] = useState<Record<string, string>>({})

  const selectedPhrase = useMemo(
    () => phrases.find((phrase) => phrase.id === selectedId) ?? null,
    [phrases, selectedId]
  )

  const visiblePhrases = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return phrases
      .filter((phrase) => showArchived || !phrase.is_archived)
      .filter((phrase) => activeTag === '全部' || phrase.tags.includes(activeTag))
      .filter((phrase) => {
        if (!normalizedQuery) return true
        return [
          phrase.text,
          phrase.chinese_meaning,
          phrase.usage_scene,
          phrase.usage_position,
          phrase.tags.join(' '),
        ]
          .join(' ')
          .toLowerCase()
          .includes(normalizedQuery)
      })
  }, [activeTag, phrases, query, showArchived])

  const loadPhrases = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`/api/learners/${learner.id}/writing-phrases?include_archived=${showArchived}`)
      if (!response.ok) throw new Error('Failed to load writing phrases')
      const data: WritingPhrase[] = await response.json()
      setPhrases(data)
      setSelectedId((prev) => prev ?? data[0]?.id ?? null)
    } catch (err) {
      console.error('Writing phrase load error:', err)
      showToast('好句收藏馆暂时无法加载。', { variant: 'error' })
    } finally {
      setIsLoading(false)
    }
  }, [learner.id, showArchived, showToast])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadPhrases(), 0)
    return () => window.clearTimeout(timer)
  }, [loadPhrases])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (!selectedPhrase) {
        setForm(EMPTY_FORM)
        setExercises([])
        return
      }
      setForm({
        text: selectedPhrase.text,
        chinese_meaning: selectedPhrase.chinese_meaning ?? '',
        explanation: selectedPhrase.explanation ?? '',
        usage_scene: selectedPhrase.usage_scene ?? '',
        usage_position: selectedPhrase.usage_position ?? 'body',
        tags_text: selectedPhrase.tags.join(', '),
        examples_text: selectedPhrase.examples.map((example) => example.sentence).join('\n'),
        notes_text: selectedPhrase.notes.join('\n'),
        mistakes_text: selectedPhrase.mistakes.join('\n'),
        difficulty: selectedPhrase.difficulty,
        is_favorite: selectedPhrase.is_favorite,
        review_enabled: selectedPhrase.review_enabled,
      })
      setExercises([])
    }, 0)
    return () => window.clearTimeout(timer)
  }, [selectedPhrase])

  const parseLines = (value: string) =>
    value
      .split(/\n|,/)
      .map((item) => item.trim())
      .filter(Boolean)

  const formPayload = () => ({
    text: form.text,
    chinese_meaning: form.chinese_meaning || null,
    explanation: form.explanation || null,
    usage_scene: form.usage_scene || null,
    usage_position: form.usage_position || null,
    tags: parseLines(form.tags_text),
    examples: form.examples_text
      .split('\n')
      .map((sentence) => sentence.trim())
      .filter(Boolean)
      .map((sentence) => ({ sentence })),
    notes: parseLines(form.notes_text),
    mistakes: parseLines(form.mistakes_text),
    difficulty: form.difficulty,
    is_favorite: form.is_favorite,
    review_enabled: form.review_enabled,
  })

  const handleCreateDemo = async () => {
    const response = await fetch(`/api/learners/${learner.id}/writing-phrases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...DEMO_PHRASE, source_type: 'seed' }),
    })
    if (!response.ok) {
      showToast('示例句式创建失败。', { variant: 'error' })
      return
    }
    const created: WritingPhrase = await response.json()
    setPhrases((prev) => [created, ...prev])
    setSelectedId(created.id)
  }

  const handleSave = async () => {
    if (!form.text.trim()) {
      showToast('英文句式不能为空。', { variant: 'warning' })
      return
    }
    setIsSaving(true)
    try {
      const endpoint = selectedPhrase
        ? `/api/learners/${learner.id}/writing-phrases/${selectedPhrase.id}`
        : `/api/learners/${learner.id}/writing-phrases`
      const response = await fetch(endpoint, {
        method: selectedPhrase ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formPayload()),
      })
      if (!response.ok) throw new Error('Failed to save phrase')
      const saved: WritingPhrase = await response.json()
      setPhrases((prev) => [saved, ...prev.filter((phrase) => phrase.id !== saved.id)])
      setSelectedId(saved.id)
      showToast('句式已保存。', { variant: 'success' })
    } catch (err) {
      console.error('Writing phrase save error:', err)
      showToast('保存失败，请检查内容后重试。', { variant: 'error' })
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!selectedPhrase) return
    const response = await fetch(`/api/learners/${learner.id}/writing-phrases/${selectedPhrase.id}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      showToast('删除失败。', { variant: 'error' })
      return
    }
    setPhrases((prev) => prev.filter((phrase) => phrase.id !== selectedPhrase.id))
    setSelectedId(null)
    showToast('句式已删除。', { variant: 'success' })
  }

  const copyPrompt = async (text: string) => {
    await navigator.clipboard.writeText(text)
    showToast('Prompt 已复制，可以粘贴到外部模型。', { variant: 'success' })
  }

  const handleImport = async () => {
    if (!importText.trim()) {
      showToast('请先粘贴外部模型结果。', { variant: 'warning' })
      return
    }
    const response = await fetch(`/api/learners/${learner.id}/writing-phrases/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source: 'external_model',
        raw_text: importText,
        topic: importTopic,
        import_mode: 'extract_phrases',
      }),
    })
    if (!response.ok) {
      showToast('提取候选句式失败。', { variant: 'error' })
      return
    }
    const data: { candidates: PhraseCandidate[] } = await response.json()
    setCandidates(data.candidates)
    setSelectedCandidates(new Set(data.candidates.map((_, index) => index)))
    showToast(`已提取 ${data.candidates.length} 条候选句式。`, { variant: 'success' })
  }

  const saveCandidate = async (candidate: PhraseCandidate) => {
    const response = await fetch(`/api/learners/${learner.id}/writing-phrases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: candidate.text,
        chinese_meaning: candidate.chinese_meaning,
        usage_scene: candidate.usage_scene,
        usage_position: candidate.usage_position,
        tags: candidate.tags,
        examples: candidate.examples,
        notes: candidate.usage_notes,
        mistakes: candidate.mistakes,
        source_type: 'external_model',
        source_raw_text: importText,
        difficulty: Math.max(1, Math.round(candidate.quality_score * 5)),
        is_favorite: false,
        review_enabled: true,
      }),
    })
    if (!response.ok) throw new Error('Failed to save candidate')
    return (await response.json()) as WritingPhrase
  }

  const handleSaveCandidates = async () => {
    try {
      const saved: WritingPhrase[] = []
      for (const index of selectedCandidates) {
        saved.push(await saveCandidate(candidates[index]))
      }
      setPhrases((prev) => [...saved, ...prev])
      if (saved[0]) setSelectedId(saved[0].id)
      showToast(`已收藏 ${saved.length} 条候选句式。`, { variant: 'success' })
    } catch (err) {
      console.error('Candidate save error:', err)
      showToast('候选句式保存失败。', { variant: 'error' })
    }
  }

  const generateExercises = async () => {
    if (!selectedPhrase) return
    const response = await fetch(`/api/learners/${learner.id}/writing-phrases/${selectedPhrase.id}/exercises`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exercise_types: ['recognition', 'blank', 'replacement'] }),
    })
    if (!response.ok) {
      showToast('练习生成失败。', { variant: 'error' })
      return
    }
    setExercises(await response.json())
  }

  const submitAttempt = async (exercise: PhraseExercise) => {
    if (!selectedPhrase) return
    const answer = attemptAnswers[exercise.id] ?? ''
    const response = await fetch(`/api/learners/${learner.id}/writing-phrases/${selectedPhrase.id}/attempts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        exercise_id: exercise.id,
        exercise_type: exercise.exercise_type,
        answer,
      }),
    })
    if (!response.ok) {
      showToast('练习记录失败。', { variant: 'error' })
      return
    }
    const data: { is_correct: boolean; score: number } = await response.json()
    showToast(data.is_correct ? '回答正确，已记录。' : '已记录本次练习。', {
      variant: data.is_correct ? 'success' : 'info',
    })
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-5 p-6">
      <header className="flex flex-col gap-4 border-b pb-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <button onClick={onBack} className="text-sm font-medium text-primary hover:underline">
            返回探索
          </button>
          <div className="mt-3 flex items-center gap-2 text-primary">
            <BookMarked className="h-5 w-5" />
            <span className="text-sm font-semibold">写作</span>
          </div>
          <h1 className="mt-1 text-2xl font-bold text-foreground">写作好句收藏馆</h1>
          <p className="mt-1 text-sm text-muted-foreground">收藏、改写、练习和掌握常见写作句式</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => {
              setSelectedId(null)
              setForm(EMPTY_FORM)
            }}
            className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium hover:bg-muted"
          >
            <Plus className="h-4 w-4" />
            新增
          </button>
          <button
            onClick={() => void handleSave()}
            disabled={isSaving}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60"
          >
            <Save className="h-4 w-4" />
            保存
          </button>
        </div>
      </header>

      <div className="grid gap-5 xl:grid-cols-[260px_minmax(0,1fr)_360px]">
        <aside className="space-y-4">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="w-full rounded-lg border bg-background py-2 pl-9 pr-3 text-sm outline-none focus:border-primary"
              placeholder="搜索句式、标签、场景"
            />
          </div>
          <TagGroup title="功能标签" tags={['全部', ...FUNCTION_TAGS]} activeTag={activeTag} onSelect={setActiveTag} />
          <TagGroup title="话题标签" tags={TOPIC_TAGS} activeTag={activeTag} onSelect={setActiveTag} />
          <TagGroup title="句式类型" tags={TYPE_TAGS} activeTag={activeTag} onSelect={setActiveTag} />
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input type="checkbox" checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} />
            显示已归档
          </label>
        </aside>

        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">句式卡片</h2>
            <span className="text-xs text-muted-foreground">{isLoading ? '加载中' : `${visiblePhrases.length} 条`}</span>
          </div>
          {visiblePhrases.length === 0 ? (
            <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
              还没有句式。可以新增一条，或先创建示例句式开始练习。
              <button onClick={() => void handleCreateDemo()} className="mt-4 inline-flex items-center gap-2 rounded-lg border px-3 py-2 font-medium text-foreground hover:bg-muted">
                <Sparkles className="h-4 w-4" />
                创建示例
              </button>
            </div>
          ) : (
            visiblePhrases.map((phrase) => (
              <button
                key={phrase.id}
                onClick={() => setSelectedId(phrase.id)}
                className={`w-full rounded-lg border p-4 text-left transition-colors hover:border-primary/60 ${
                  selectedId === phrase.id ? 'border-primary bg-primary/5' : 'bg-card'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="text-base font-semibold text-foreground">{phrase.text}</p>
                  {phrase.is_favorite ? <Star className="h-4 w-4 shrink-0 fill-warning text-warning" /> : <StarOff className="h-4 w-4 shrink-0 text-muted-foreground" />}
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{phrase.chinese_meaning || phrase.usage_scene || '待补充中文含义和使用场景'}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {phrase.tags.slice(0, 4).map((tag) => (
                    <span key={tag} className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                      {tag}
                    </span>
                  ))}
                </div>
              </button>
            ))
          )}
        </section>

        <aside className="space-y-5">
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-foreground">{selectedPhrase ? '编辑句式' : '新增句式'}</h2>
              {selectedPhrase && (
                <div className="flex gap-1">
                  <button
                    onClick={() => setForm((prev) => ({ ...prev, is_favorite: !prev.is_favorite }))}
                    className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-warning"
                    title={form.is_favorite ? '取消收藏' : '收藏'}
                  >
                    {form.is_favorite ? <Star className="h-4 w-4 fill-warning text-warning" /> : <StarOff className="h-4 w-4" />}
                  </button>
                  <button
                    onClick={() => {
                      setForm((prev) => ({ ...prev, review_enabled: !prev.review_enabled }))
                    }}
                    className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-primary"
                    title={form.review_enabled ? '移出复习' : '加入复习'}
                  >
                    <RotateCcw className="h-4 w-4" />
                  </button>
                  <button onClick={() => void handleDelete()} className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-error" title="删除">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>
            <Field label="英文句式" value={form.text} onChange={(value) => setForm((prev) => ({ ...prev, text: value }))} textarea />
            <Field label="中文含义" value={form.chinese_meaning} onChange={(value) => setForm((prev) => ({ ...prev, chinese_meaning: value }))} />
            <Field label="解释说明" value={form.explanation} onChange={(value) => setForm((prev) => ({ ...prev, explanation: value }))} textarea />
            <Field label="适用场景" value={form.usage_scene} onChange={(value) => setForm((prev) => ({ ...prev, usage_scene: value }))} textarea />
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm">
                <span className="font-medium text-foreground">使用位置</span>
                <select value={form.usage_position} onChange={(event) => setForm((prev) => ({ ...prev, usage_position: event.target.value }))} className="mt-1 w-full rounded-lg border bg-background px-3 py-2 outline-none focus:border-primary">
                  <option value="opening">开头</option>
                  <option value="body">主体</option>
                  <option value="closing">结尾</option>
                  <option value="translation">翻译</option>
                </select>
              </label>
              <label className="text-sm">
                <span className="font-medium text-foreground">难度</span>
                <input type="number" min={1} max={5} value={form.difficulty} onChange={(event) => setForm((prev) => ({ ...prev, difficulty: Number(event.target.value) }))} className="mt-1 w-full rounded-lg border bg-background px-3 py-2 outline-none focus:border-primary" />
              </label>
            </div>
            <Field label="标签" value={form.tags_text} onChange={(value) => setForm((prev) => ({ ...prev, tags_text: value }))} />
            <Field label="例句" value={form.examples_text} onChange={(value) => setForm((prev) => ({ ...prev, examples_text: value }))} textarea />
            <Field label="注意事项" value={form.notes_text} onChange={(value) => setForm((prev) => ({ ...prev, notes_text: value }))} textarea />
            <Field label="常见错误" value={form.mistakes_text} onChange={(value) => setForm((prev) => ({ ...prev, mistakes_text: value }))} textarea />
            <div className="flex gap-2">
              <button onClick={() => void handleSave()} disabled={isSaving} className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60">
                <Save className="h-4 w-4" />
                保存句式
              </button>
              {selectedPhrase && (
                <button
                  onClick={async () => {
                    const response = await fetch(`/api/learners/${learner.id}/writing-phrases/${selectedPhrase.id}`, {
                      method: 'PATCH',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ is_archived: !selectedPhrase.is_archived }),
                    })
                    if (response.ok) void loadPhrases()
                  }}
                  className="rounded-lg border px-3 py-2 text-muted-foreground hover:bg-muted"
                  title={selectedPhrase.is_archived ? '取消归档' : '归档'}
                >
                  <Archive className="h-4 w-4" />
                </button>
              )}
            </div>
          </section>

          <section className="space-y-3 border-t pt-5">
            <h2 className="text-sm font-semibold text-foreground">外部模型 Prompt</h2>
            {PROMPTS.map((prompt) => (
              <button key={prompt.id} onClick={() => void copyPrompt(prompt.text)} className="flex w-full items-center justify-between rounded-lg border px-3 py-2 text-sm hover:bg-muted">
                <span>{prompt.label}</span>
                <Copy className="h-4 w-4 text-muted-foreground" />
              </button>
            ))}
          </section>

          <section className="space-y-3 border-t pt-5">
            <h2 className="text-sm font-semibold text-foreground">粘贴回填</h2>
            <input value={importTopic} onChange={(event) => setImportTopic(event.target.value)} className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:border-primary" placeholder="主题标签，例如 online learning" />
            <textarea value={importText} onChange={(event) => setImportText(event.target.value)} className="min-h-28 w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:border-primary" placeholder="粘贴外部模型输出" />
            <button onClick={() => void handleImport()} className="inline-flex w-full items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium hover:bg-muted">
              <FileDown className="h-4 w-4" />
              提取候选句式
            </button>
            {candidates.length > 0 && (
              <div className="space-y-2">
                {candidates.map((candidate, index) => (
                  <label key={`${candidate.text}-${index}`} className="block rounded-lg border p-3 text-sm">
                    <div className="flex items-start gap-2">
                      <input
                        type="checkbox"
                        checked={selectedCandidates.has(index)}
                        onChange={(event) => {
                          const next = new Set(selectedCandidates)
                          if (event.target.checked) next.add(index)
                          else next.delete(index)
                          setSelectedCandidates(next)
                        }}
                      />
                      <div>
                        <p className="font-medium text-foreground">{candidate.text}</p>
                        <p className="mt-1 text-muted-foreground">{candidate.chinese_meaning || candidate.usage_scene}</p>
                      </div>
                    </div>
                  </label>
                ))}
                <button onClick={() => void handleSaveCandidates()} className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
                  <Check className="h-4 w-4" />
                  收藏选中
                </button>
              </div>
            )}
          </section>

          <section className="space-y-3 border-t pt-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-foreground">练习检测</h2>
              <button onClick={() => void generateExercises()} disabled={!selectedPhrase} className="rounded-lg border px-3 py-2 text-xs font-medium hover:bg-muted disabled:opacity-50">
                生成
              </button>
            </div>
            {exercises.map((exercise) => (
              <div key={exercise.id} className="rounded-lg border p-3 text-sm">
                <p className="text-xs font-medium text-primary">{exerciseTypeLabel(exercise.exercise_type)}</p>
                <p className="mt-2 whitespace-pre-wrap text-foreground">{exercise.prompt}</p>
                {exercise.options.length > 0 && (
                  <div className="mt-2 space-y-1 text-muted-foreground">
                    {exercise.options.map((option) => (
                      <button key={option} onClick={() => setAttemptAnswers((prev) => ({ ...prev, [exercise.id]: option }))} className="block w-full rounded-md border px-2 py-1 text-left hover:bg-muted">
                        {option}
                      </button>
                    ))}
                  </div>
                )}
                <input value={attemptAnswers[exercise.id] ?? ''} onChange={(event) => setAttemptAnswers((prev) => ({ ...prev, [exercise.id]: event.target.value }))} className="mt-2 w-full rounded-lg border bg-background px-3 py-2 outline-none focus:border-primary" placeholder="输入答案" />
                <button onClick={() => void submitAttempt(exercise)} className="mt-2 inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium hover:bg-muted">
                  <Clipboard className="h-4 w-4" />
                  记录练习
                </button>
              </div>
            ))}
            {exercises.length === 0 && <p className="text-sm text-muted-foreground">选择一句好句后可生成识别、填空、替换练习。</p>}
          </section>
        </aside>
      </div>
    </div>
  )
}

function TagGroup({
  title,
  tags,
  activeTag,
  onSelect,
}: {
  title: string
  tags: string[]
  activeTag: string
  onSelect: (tag: string) => void
}) {
  return (
    <section>
      <h2 className="mb-2 text-xs font-semibold text-foreground">{title}</h2>
      <div className="flex flex-wrap gap-2">
        {tags.map((tag) => (
          <button
            key={tag}
            onClick={() => onSelect(tag)}
            className={`rounded-md border px-2 py-1 text-xs transition-colors ${
              activeTag === tag ? 'border-primary bg-primary/10 text-primary' : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            }`}
          >
            {tag}
          </button>
        ))}
      </div>
    </section>
  )
}

function Field({
  label,
  value,
  onChange,
  textarea = false,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  textarea?: boolean
}) {
  const className = 'mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:border-primary'
  return (
    <label className="block text-sm">
      <span className="font-medium text-foreground">{label}</span>
      {textarea ? (
        <textarea value={value} onChange={(event) => onChange(event.target.value)} className={`${className} min-h-20`} />
      ) : (
        <input value={value} onChange={(event) => onChange(event.target.value)} className={className} />
      )}
    </label>
  )
}

function exerciseTypeLabel(type: PhraseExercise['exercise_type']) {
  if (type === 'recognition') return '识别题'
  if (type === 'blank') return '填空题'
  return '替换题'
}
