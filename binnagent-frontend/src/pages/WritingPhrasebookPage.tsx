import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  Archive,
  BookMarked,
  Check,
  Clipboard,
  Copy,
  Edit3,
  FileDown,
  Library,
  PenLine,
  Plus,
  RotateCcw,
  Save,
  Search,
  Sparkles,
  Star,
  StarOff,
  Target,
  Trash2,
  X,
} from 'lucide-react'
import { FeatureHero } from '@/components/layout/FeatureHero'
import { PageShell } from '@/components/layout/PageShell'
import { WorkspaceTabs, type WorkspaceTab } from '@/components/layout/WorkspaceTabs'
import { FilterChip } from '@/components/ui/FilterChip'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import { useToast } from '@/hooks/useToast'
import type { Learner } from '@/types'

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

type Workspace = 'library' | 'import' | 'practice' | 'writing'
type QuickFilter = 'all' | 'favorite' | 'review' | 'archived'

const FUNCTION_TAGS = ['开头引入', '分层递进', '举例说明', '对比转折', '原因结果', '强调重点', '观点表达', '总结升华', '图表描述', '翻译表达', '议论文万能句']
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

const PROMPTS = [
  {
    id: 'generate',
    label: '生成某类好句',
    hint: '按主题和功能生成 8-12 条可收藏句式。',
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
    hint: '把范文里的可迁移表达拆成句式资产。',
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
    label: '优化我的收藏',
    hint: '检查句式是否自然、适合 CET、值得练习。',
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

const WORKSPACE_TABS: WorkspaceTab<Workspace>[] = [
  { id: 'library', label: '收藏馆', description: '浏览与理解', icon: <Library className="h-4 w-4" /> },
  { id: 'import', label: '导入好句', description: 'Prompt 与回填', icon: <FileDown className="h-4 w-4" /> },
  { id: 'practice', label: '练习检测', description: '从收藏到掌握', icon: <Target className="h-4 w-4" /> },
  { id: 'writing', label: '写作调用', description: '按场景选句', icon: <PenLine className="h-4 w-4" /> },
]

const QUICK_FILTERS: Array<{ id: QuickFilter; label: string }> = [
  { id: 'all', label: '全部' },
  { id: 'favorite', label: '收藏' },
  { id: 'review', label: '待复习' },
  { id: 'archived', label: '已归档' },
]

export function WritingPhrasebookPage({ learner, onBack }: WritingPhrasebookPageProps) {
  const { showToast } = useToast()
  const [workspace, setWorkspace] = useState<Workspace>('library')
  const [phrases, setPhrases] = useState<WritingPhrase[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [quickFilter, setQuickFilter] = useState<QuickFilter>('all')
  const [activeTag, setActiveTag] = useState('全部')
  const [isMoreFiltersOpen, setIsMoreFiltersOpen] = useState(false)
  const [form, setForm] = useState<PhraseForm>(EMPTY_FORM)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [importText, setImportText] = useState('')
  const [importTopic, setImportTopic] = useState('online learning')
  const [selectedPromptId, setSelectedPromptId] = useState(PROMPTS[0].id)
  const [candidates, setCandidates] = useState<PhraseCandidate[]>([])
  const [selectedCandidates, setSelectedCandidates] = useState<Set<number>>(new Set())
  const [exercises, setExercises] = useState<PhraseExercise[]>([])
  const [activeExerciseIndex, setActiveExerciseIndex] = useState(0)
  const [attemptAnswers, setAttemptAnswers] = useState<Record<string, string>>({})

  const selectedPhrase = useMemo(
    () => phrases.find((phrase) => phrase.id === selectedId) ?? null,
    [phrases, selectedId]
  )
  const selectedPrompt = PROMPTS.find((prompt) => prompt.id === selectedPromptId) ?? PROMPTS[0]

  const stats = useMemo(
    () => ({
      total: phrases.filter((phrase) => !phrase.is_archived).length,
      review: phrases.filter((phrase) => phrase.review_enabled && !phrase.is_archived).length,
      favorite: phrases.filter((phrase) => phrase.is_favorite && !phrase.is_archived).length,
      archived: phrases.filter((phrase) => phrase.is_archived).length,
    }),
    [phrases]
  )

  const visiblePhrases = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return phrases
      .filter((phrase) => {
        if (quickFilter === 'archived') return phrase.is_archived
        if (phrase.is_archived) return false
        if (quickFilter === 'favorite') return phrase.is_favorite
        if (quickFilter === 'review') return phrase.review_enabled
        return true
      })
      .filter((phrase) => activeTag === '全部' || phrase.tags.includes(activeTag))
      .filter((phrase) => {
        if (!normalizedQuery) return true
        return [phrase.text, phrase.chinese_meaning, phrase.usage_scene, phrase.usage_position, phrase.tags.join(' ')]
          .join(' ')
          .toLowerCase()
          .includes(normalizedQuery)
      })
  }, [activeTag, phrases, query, quickFilter])

  const phrasesByPosition = useMemo(() => {
    const groups: Record<string, WritingPhrase[]> = { opening: [], body: [], closing: [], translation: [] }
    for (const phrase of phrases) {
      if (phrase.is_archived) continue
      const key = phrase.usage_position || 'body'
      if (groups[key]) groups[key].push(phrase)
      else groups.body.push(phrase)
    }
    return groups
  }, [phrases])

  const loadPhrases = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`/api/learners/${learner.id}/writing-phrases?include_archived=true`)
      if (!response.ok) throw new Error('Failed to load writing phrases')
      const data: WritingPhrase[] = await response.json()
      setPhrases(data)
      setSelectedId((prev) => prev ?? data.find((phrase) => !phrase.is_archived)?.id ?? data[0]?.id ?? null)
    } catch (err) {
      console.error('Writing phrase load error:', err)
      showToast('好句收藏馆暂时无法加载，稍后可重试。', { variant: 'error' })
    } finally {
      setIsLoading(false)
    }
  }, [learner.id, showToast])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadPhrases(), 0)
    return () => window.clearTimeout(timer)
  }, [loadPhrases])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setForm(phraseToForm(selectedPhrase))
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
      showToast('示例句式创建失败，稍后再试。', { variant: 'error' })
      return
    }
    const created: WritingPhrase = await response.json()
    setPhrases((prev) => [created, ...prev])
    setSelectedId(created.id)
    setWorkspace('library')
    showToast('已创建示例句式，可以从详情里开始练习。', { variant: 'success' })
  }

  const openNewPhrase = () => {
    setSelectedId(null)
    setForm(EMPTY_FORM)
    setIsEditOpen(true)
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
      setIsEditOpen(false)
      showToast('句式已保存，可在练习检测中继续巩固。', { variant: 'success' })
    } catch (err) {
      console.error('Writing phrase save error:', err)
      showToast('保存失败，请检查内容后重试。', { variant: 'error' })
    } finally {
      setIsSaving(false)
    }
  }

  const patchSelectedPhrase = async (payload: Partial<WritingPhrase>) => {
    if (!selectedPhrase) return
    const response = await fetch(`/api/learners/${learner.id}/writing-phrases/${selectedPhrase.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!response.ok) {
      showToast('状态更新失败，当前内容已保留。', { variant: 'error' })
      return
    }
    const saved: WritingPhrase = await response.json()
    setPhrases((prev) => [saved, ...prev.filter((phrase) => phrase.id !== saved.id)])
    setSelectedId(saved.id)
  }

  const handleDelete = async () => {
    if (!selectedPhrase) return
    const response = await fetch(`/api/learners/${learner.id}/writing-phrases/${selectedPhrase.id}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      showToast('删除失败，稍后可重试。', { variant: 'error' })
      return
    }
    setPhrases((prev) => prev.filter((phrase) => phrase.id !== selectedPhrase.id))
    setSelectedId(null)
    setIsEditOpen(false)
    showToast('句式已删除。', { variant: 'success' })
  }

  const copyPrompt = async () => {
    const copied = await copyText(selectedPrompt.text)
    showToast(
      copied ? 'Prompt 已复制，生成结果可回到本页粘贴提取。' : '浏览器阻止了自动复制，请手动选中 Prompt 文本复制。',
      { variant: copied ? 'success' : 'warning' }
    )
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
      showToast('提取候选句式失败，请确认粘贴内容包含句式字段。', { variant: 'error' })
      return
    }
    const data: { candidates: PhraseCandidate[] } = await response.json()
    setCandidates(data.candidates)
    setSelectedCandidates(new Set(data.candidates.map((_, index) => index)))
    showToast(`已提取 ${data.candidates.length} 条候选句式，可勾选收藏。`, { variant: 'success' })
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
      setWorkspace('library')
      showToast(`已收藏 ${saved.length} 条候选句式，可在“练习检测”中开始复习。`, { variant: 'success' })
    } catch (err) {
      console.error('Candidate save error:', err)
      showToast('候选句式保存失败，请稍后重试。', { variant: 'error' })
    }
  }

  const generateExercises = async (phraseId = selectedPhrase?.id) => {
    if (!phraseId) return
    const response = await fetch(`/api/learners/${learner.id}/writing-phrases/${phraseId}/exercises`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exercise_types: ['recognition', 'blank', 'replacement'] }),
    })
    if (!response.ok) {
      showToast('练习生成失败，请稍后重试。', { variant: 'error' })
      return
    }
    const data: PhraseExercise[] = await response.json()
    setExercises(data)
    setActiveExerciseIndex(0)
    setWorkspace('practice')
  }

  const submitAttempt = async (exercise: PhraseExercise) => {
    const answer = attemptAnswers[exercise.id] ?? ''
    if (!answer.trim()) {
      showToast('请先输入或选择答案。', { variant: 'warning' })
      return
    }
    const response = await fetch(`/api/learners/${learner.id}/writing-phrases/${exercise.phrase_id}/attempts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        exercise_id: exercise.id,
        exercise_type: exercise.exercise_type,
        answer,
      }),
    })
    if (!response.ok) {
      showToast('练习记录失败，答案仍保留在页面中。', { variant: 'error' })
      return
    }
    const data: { is_correct: boolean; score: number } = await response.json()
    showToast(data.is_correct ? '回答正确，已记录本次掌握情况。' : '已记录本次练习，可以查看答案后再试。', {
      variant: data.is_correct ? 'success' : 'info',
    })
  }

  const activeExercise = exercises[activeExerciseIndex]

  return (
    <PageShell>
      <button onClick={onBack} className="w-fit text-sm font-medium text-primary hover:underline">
        返回探索
      </button>

      <FeatureHero
        eyebrow="Writing Phrasebook"
        title="写作好句收藏馆"
        description="把可迁移表达沉淀成自己的写作资产：先理解何时使用，再编辑完善、加入复习，并通过练习真正用出来。"
        stats={[
          { label: '总句式', value: stats.total },
          { label: '待复习', value: stats.review, tone: 'primary' },
          { label: '已收藏', value: stats.favorite, tone: 'warning' },
          { label: '已归档', value: stats.archived },
        ]}
        actions={
          <>
            <button onClick={openNewPhrase} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:border-indigo-200 hover:text-indigo-600">
              <Plus className="h-4 w-4" />
              新增句式
            </button>
            <button onClick={() => setWorkspace('import')} className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
              <FileDown className="h-4 w-4" />
              导入好句
            </button>
          </>
        }
      />

      <WorkspaceTabs tabs={WORKSPACE_TABS} activeTab={workspace} onChange={setWorkspace} />

      {workspace === 'library' && (
        <LibraryWorkspace
          activeTag={activeTag}
          isLoading={isLoading}
          isMoreFiltersOpen={isMoreFiltersOpen}
          onCreateDemo={() => void handleCreateDemo()}
          onEdit={() => setIsEditOpen(true)}
          onGenerateExercises={() => void generateExercises()}
          onPatchSelected={(payload) => void patchSelectedPhrase(payload)}
          onQuickFilterChange={setQuickFilter}
          onQueryChange={setQuery}
          onSelectPhrase={setSelectedId}
          onTagChange={setActiveTag}
          onToggleMoreFilters={() => setIsMoreFiltersOpen((prev) => !prev)}
          phrases={visiblePhrases}
          quickFilter={quickFilter}
          query={query}
          selectedPhrase={selectedPhrase}
          selectedId={selectedId}
        />
      )}

      {workspace === 'import' && (
        <ImportWorkspace
          candidates={candidates}
          importText={importText}
          importTopic={importTopic}
          onCopyPrompt={() => void copyPrompt()}
          onImport={() => void handleImport()}
          onImportTextChange={setImportText}
          onImportTopicChange={setImportTopic}
          onPromptChange={setSelectedPromptId}
          onSaveCandidates={() => void handleSaveCandidates()}
          onToggleCandidate={(index, checked) => {
            const next = new Set(selectedCandidates)
            if (checked) next.add(index)
            else next.delete(index)
            setSelectedCandidates(next)
          }}
          selectedCandidates={selectedCandidates}
          selectedPrompt={selectedPrompt}
          selectedPromptId={selectedPromptId}
        />
      )}

      {workspace === 'practice' && (
        <PracticeWorkspace
          activeExercise={activeExercise}
          activeExerciseIndex={activeExerciseIndex}
          answers={attemptAnswers}
          exercises={exercises}
          onAnswerChange={(exerciseId, answer) => setAttemptAnswers((prev) => ({ ...prev, [exerciseId]: answer }))}
          onGenerate={() => void generateExercises()}
          onNext={() => setActiveExerciseIndex((prev) => Math.min(prev + 1, exercises.length - 1))}
          onPrevious={() => setActiveExerciseIndex((prev) => Math.max(prev - 1, 0))}
          onSubmit={(exercise) => void submitAttempt(exercise)}
          phrases={phrases.filter((phrase) => !phrase.is_archived)}
          selectedPhrase={selectedPhrase}
          onSelectPhrase={setSelectedId}
        />
      )}

      {workspace === 'writing' && <WritingAssistWorkspace phrasesByPosition={phrasesByPosition} />}

      {isEditOpen && (
        <PhraseEditDrawer
          form={form}
          isSaving={isSaving}
          isSelected={Boolean(selectedPhrase)}
          onChange={setForm}
          onClose={() => setIsEditOpen(false)}
          onDelete={() => void handleDelete()}
          onSave={() => void handleSave()}
        />
      )}
    </PageShell>
  )
}

function phraseToForm(phrase: WritingPhrase | null): PhraseForm {
  if (!phrase) return EMPTY_FORM
  return {
    text: phrase.text,
    chinese_meaning: phrase.chinese_meaning ?? '',
    explanation: phrase.explanation ?? '',
    usage_scene: phrase.usage_scene ?? '',
    usage_position: phrase.usage_position ?? 'body',
    tags_text: phrase.tags.join(', '),
    examples_text: phrase.examples.map((example) => example.sentence).join('\n'),
    notes_text: phrase.notes.join('\n'),
    mistakes_text: phrase.mistakes.join('\n'),
    difficulty: phrase.difficulty,
    is_favorite: phrase.is_favorite,
    review_enabled: phrase.review_enabled,
  }
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.setAttribute('readonly', 'true')
    textarea.style.position = 'fixed'
    textarea.style.left = '-9999px'
    document.body.appendChild(textarea)
    textarea.select()
    const copied = document.execCommand('copy')
    document.body.removeChild(textarea)
    return copied
  }
}

function LibraryWorkspace({
  activeTag,
  isLoading,
  isMoreFiltersOpen,
  onCreateDemo,
  onEdit,
  onGenerateExercises,
  onPatchSelected,
  onQuickFilterChange,
  onQueryChange,
  onSelectPhrase,
  onTagChange,
  onToggleMoreFilters,
  phrases,
  quickFilter,
  query,
  selectedPhrase,
  selectedId,
}: {
  activeTag: string
  isLoading: boolean
  isMoreFiltersOpen: boolean
  onCreateDemo: () => void
  onEdit: () => void
  onGenerateExercises: () => void
  onPatchSelected: (payload: Partial<WritingPhrase>) => void
  onQuickFilterChange: (filter: QuickFilter) => void
  onQueryChange: (query: string) => void
  onSelectPhrase: (id: string) => void
  onTagChange: (tag: string) => void
  onToggleMoreFilters: () => void
  phrases: WritingPhrase[]
  quickFilter: QuickFilter
  query: string
  selectedPhrase: WritingPhrase | null
  selectedId: string | null
}) {
  return (
    <div className="grid gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
      <SurfaceCard className="space-y-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-primary"
            placeholder="搜索句式、标签、使用场景"
          />
        </div>
        <div className="flex gap-2 overflow-x-auto pb-1">
          {QUICK_FILTERS.map((filter) => (
            <FilterChip key={filter.id} active={quickFilter === filter.id} onClick={() => onQuickFilterChange(filter.id)}>
              {filter.label}
            </FilterChip>
          ))}
        </div>
        <div>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-xs font-semibold text-slate-500">常用标签</h2>
            <button onClick={onToggleMoreFilters} className="text-xs font-medium text-primary">
              {isMoreFiltersOpen ? '收起' : '更多筛选'}
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {['全部', ...FUNCTION_TAGS.slice(0, 7)].map((tag) => (
              <FilterChip key={tag} active={activeTag === tag} onClick={() => onTagChange(tag)}>
                {tag}
              </FilterChip>
            ))}
          </div>
          {isMoreFiltersOpen && (
            <div className="mt-3 space-y-3 border-t border-slate-100 pt-3">
              <TagRow label="话题" tags={TOPIC_TAGS} activeTag={activeTag} onSelect={onTagChange} />
              <TagRow label="类型" tags={TYPE_TAGS} activeTag={activeTag} onSelect={onTagChange} />
            </div>
          )}
        </div>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-950">句式卡片</h2>
          <span className="text-xs text-slate-500">{isLoading ? '加载中' : `${phrases.length} 条`}</span>
        </div>
        <div className="space-y-3 lg:max-h-[620px] lg:overflow-y-auto lg:pr-1">
          {phrases.length === 0 ? (
            <EmptyLibrary onCreateDemo={onCreateDemo} />
          ) : (
            phrases.map((phrase) => (
              <PhraseCard key={phrase.id} phrase={phrase} active={selectedId === phrase.id} onClick={() => onSelectPhrase(phrase.id)} />
            ))
          )}
        </div>
      </SurfaceCard>

      <PhraseDetailPanel
        phrase={selectedPhrase}
        onEdit={onEdit}
        onGenerateExercises={onGenerateExercises}
        onPatch={onPatchSelected}
      />
    </div>
  )
}

function PhraseCard({ phrase, active, onClick }: { phrase: WritingPhrase; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`w-full rounded-[13px] border p-4 text-left transition-colors ${
        active ? 'border-primary bg-primary/5' : 'border-slate-200 bg-white hover:border-indigo-200'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-base font-semibold leading-relaxed text-slate-950">{phrase.text}</p>
        {phrase.is_favorite ? <Star className="mt-1 h-4 w-4 shrink-0 fill-warning text-warning" /> : null}
      </div>
      <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-500">{phrase.chinese_meaning || phrase.usage_scene || '待补充中文含义和使用场景'}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {phrase.tags.slice(0, 3).map((tag) => (
          <span key={tag} className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
            {tag}
          </span>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
        <span>{positionLabel(phrase.usage_position)}</span>
        <span>难度 {phrase.difficulty}/5</span>
        {phrase.review_enabled && <span className="text-primary">待复习</span>}
      </div>
    </button>
  )
}

function PhraseDetailPanel({
  phrase,
  onEdit,
  onGenerateExercises,
  onPatch,
}: {
  phrase: WritingPhrase | null
  onEdit: () => void
  onGenerateExercises: () => void
  onPatch: (payload: Partial<WritingPhrase>) => void
}) {
  if (!phrase) {
    return (
      <SurfaceCard className="flex min-h-[520px] flex-col items-center justify-center text-center">
        <BookMarked className="h-10 w-10 text-slate-300" />
        <h2 className="mt-4 text-lg font-semibold text-slate-950">选择一句好句开始学习</h2>
        <p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">左侧列表负责快速识别，右侧详情会集中展示“何时用、何时不用、例句和误用”。</p>
      </SurfaceCard>
    )
  }

  return (
    <SurfaceCard className="space-y-5">
      <div className="flex flex-col gap-4 border-b border-slate-100 pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="mb-3 flex flex-wrap gap-2">
            {phrase.tags.slice(0, 4).map((tag) => (
              <span key={tag} className="rounded-md bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
                {tag}
              </span>
            ))}
          </div>
          <h2 className="text-2xl font-black leading-relaxed text-slate-950">{phrase.text}</h2>
          <p className="mt-2 text-base text-slate-600">{phrase.chinese_meaning || '待补充中文含义'}</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <IconButton title={phrase.is_favorite ? '取消收藏' : '收藏'} onClick={() => onPatch({ is_favorite: !phrase.is_favorite })}>
            {phrase.is_favorite ? <Star className="h-4 w-4 fill-warning text-warning" /> : <StarOff className="h-4 w-4" />}
          </IconButton>
          <IconButton title={phrase.review_enabled ? '移出复习' : '加入复习'} onClick={() => onPatch({ review_enabled: !phrase.review_enabled })}>
            <RotateCcw className="h-4 w-4" />
          </IconButton>
          <IconButton title={phrase.is_archived ? '取消归档' : '归档'} onClick={() => onPatch({ is_archived: !phrase.is_archived })}>
            <Archive className="h-4 w-4" />
          </IconButton>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <LearningInfo title="适合何时用" body={phrase.usage_scene || '适合的作文场景还没有补充。'} tone="primary" />
        <LearningInfo title="不适合何时用" body={phrase.mistakes[0] || '暂未记录常见误用。'} tone="warning" />
      </div>

      <DetailSection title="例句">
        {phrase.examples.length > 0 ? (
          phrase.examples.map((example) => (
            <div key={example.sentence} className="rounded-[13px] bg-slate-50 p-4">
              <p className="text-base font-semibold leading-relaxed text-slate-950">{example.sentence}</p>
              {example.translation && <p className="mt-2 text-sm text-slate-500">{example.translation}</p>}
            </div>
          ))
        ) : (
          <p className="text-sm text-slate-500">暂无例句。</p>
        )}
      </DetailSection>

      <div className="grid gap-4 md:grid-cols-2">
        <DetailSection title="注意事项">
          <Bullets items={phrase.notes} fallback="暂无注意事项。" />
        </DetailSection>
        <DetailSection title="可替换低级表达">
          <div className="flex flex-wrap gap-2">
            {['Also, ...', 'More importantly, ...', 'First, ...'].map((item) => (
              <span key={item} className="rounded-md bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
                {item}
              </span>
            ))}
          </div>
        </DetailSection>
      </div>

      <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-5">
        <button onClick={onEdit} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:border-indigo-200 hover:text-indigo-600">
          <Edit3 className="h-4 w-4" />
          编辑
        </button>
        <button onClick={onGenerateExercises} className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
          <Target className="h-4 w-4" />
          生成练习
        </button>
        <button onClick={() => onPatch({ review_enabled: true })} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:border-indigo-200 hover:text-indigo-600">
          <RotateCcw className="h-4 w-4" />
          加入复习
        </button>
      </div>
    </SurfaceCard>
  )
}

function ImportWorkspace({
  candidates,
  importText,
  importTopic,
  onCopyPrompt,
  onImport,
  onImportTextChange,
  onImportTopicChange,
  onPromptChange,
  onSaveCandidates,
  onToggleCandidate,
  selectedCandidates,
  selectedPrompt,
  selectedPromptId,
}: {
  candidates: PhraseCandidate[]
  importText: string
  importTopic: string
  onCopyPrompt: () => void
  onImport: () => void
  onImportTextChange: (value: string) => void
  onImportTopicChange: (value: string) => void
  onPromptChange: (id: string) => void
  onSaveCandidates: () => void
  onToggleCandidate: (index: number, checked: boolean) => void
  selectedCandidates: Set<number>
  selectedPrompt: (typeof PROMPTS)[number]
  selectedPromptId: string
}) {
  return (
    <div className="space-y-5">
      <SurfaceCard>
        <div className="grid gap-4 md:grid-cols-4">
          {['选择任务', '复制 Prompt', '粘贴输出', '确认收藏'].map((step, index) => (
            <div key={step} className="rounded-[13px] border border-slate-100 bg-slate-50 p-4">
              <p className="text-xs font-semibold text-primary">Step {index + 1}</p>
              <p className="mt-1 text-sm font-semibold text-slate-950">{step}</p>
            </div>
          ))}
        </div>
      </SurfaceCard>

      <div className="grid gap-5 lg:grid-cols-[330px_minmax(0,1fr)]">
        <SurfaceCard className="space-y-3">
          <h2 className="text-base font-semibold text-slate-950">任务类型</h2>
          {PROMPTS.map((prompt) => (
            <button
              key={prompt.id}
              onClick={() => onPromptChange(prompt.id)}
              className={`w-full rounded-[13px] border p-4 text-left transition-colors ${
                selectedPromptId === prompt.id ? 'border-primary bg-primary/5' : 'border-slate-200 hover:border-indigo-200'
              }`}
            >
              <p className="font-semibold text-slate-950">{prompt.label}</p>
              <p className="mt-1 text-sm leading-6 text-slate-500">{prompt.hint}</p>
            </button>
          ))}
        </SurfaceCard>

        <SurfaceCard className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-950">当前 Prompt</h2>
              <p className="text-sm text-slate-500">复制到外部模型，生成后把结果粘贴回来。</p>
            </div>
            <button onClick={onCopyPrompt} className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:border-indigo-200 hover:text-indigo-600">
              <Copy className="h-4 w-4" />
              复制 Prompt
            </button>
          </div>
          <pre className="max-h-56 overflow-auto rounded-[13px] bg-slate-950 p-4 text-sm leading-6 text-slate-100 whitespace-pre-wrap">
            {selectedPrompt.text}
          </pre>
          <div className="grid gap-3 sm:grid-cols-[220px_minmax(0,1fr)]">
            <input value={importTopic} onChange={(event) => onImportTopicChange(event.target.value)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-primary" placeholder="主题标签" />
            <textarea value={importText} onChange={(event) => onImportTextChange(event.target.value)} className="min-h-28 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm leading-6 outline-none focus:border-primary" placeholder="粘贴外部模型输出" />
          </div>
          <button onClick={onImport} className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            <FileDown className="h-4 w-4" />
            提取候选句式
          </button>
        </SurfaceCard>
      </div>

      {candidates.length > 0 && (
        <SurfaceCard className="space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-950">候选句式</h2>
              <p className="text-sm text-slate-500">勾选后批量收藏，不建议收藏的句式会显示提示。</p>
            </div>
            <button onClick={onSaveCandidates} className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
              <Check className="h-4 w-4" />
              收藏选中
            </button>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {candidates.map((candidate, index) => (
              <label key={`${candidate.text}-${index}`} className="rounded-[13px] border border-slate-200 p-4">
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={selectedCandidates.has(index)}
                    onChange={(event) => onToggleCandidate(index, event.target.checked)}
                    className="mt-1"
                  />
                  <div className="min-w-0">
                    <p className="text-base font-semibold leading-relaxed text-slate-950">{candidate.text}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-500">{candidate.chinese_meaning || candidate.usage_scene}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {candidate.tags.slice(0, 4).map((tag) => (
                        <span key={tag} className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                          {tag}
                        </span>
                      ))}
                    </div>
                    {candidate.warnings.length > 0 && <p className="mt-2 text-xs font-medium text-warning">{candidate.warnings[0]}</p>}
                  </div>
                </div>
              </label>
            ))}
          </div>
        </SurfaceCard>
      )}
    </div>
  )
}

function PracticeWorkspace({
  activeExercise,
  activeExerciseIndex,
  answers,
  exercises,
  onAnswerChange,
  onGenerate,
  onNext,
  onPrevious,
  onSelectPhrase,
  onSubmit,
  phrases,
  selectedPhrase,
}: {
  activeExercise?: PhraseExercise
  activeExerciseIndex: number
  answers: Record<string, string>
  exercises: PhraseExercise[]
  onAnswerChange: (exerciseId: string, answer: string) => void
  onGenerate: () => void
  onNext: () => void
  onPrevious: () => void
  onSelectPhrase: (id: string) => void
  onSubmit: (exercise: PhraseExercise) => void
  phrases: WritingPhrase[]
  selectedPhrase: WritingPhrase | null
}) {
  return (
    <div className="grid gap-5 lg:grid-cols-[330px_minmax(0,1fr)]">
      <SurfaceCard className="space-y-4">
        <div>
          <h2 className="text-base font-semibold text-slate-950">选择练习句式</h2>
          <p className="mt-1 text-sm text-slate-500">优先练习已加入复习或最近收藏的表达。</p>
        </div>
        <div className="space-y-2 lg:max-h-[520px] lg:overflow-y-auto">
          {phrases.map((phrase) => (
            <button
              key={phrase.id}
              onClick={() => onSelectPhrase(phrase.id)}
              className={`w-full rounded-[13px] border p-3 text-left text-sm ${
                selectedPhrase?.id === phrase.id ? 'border-primary bg-primary/5' : 'border-slate-200 hover:border-indigo-200'
              }`}
            >
              <p className="font-semibold text-slate-950">{phrase.text}</p>
              <p className="mt-1 line-clamp-1 text-slate-500">{phrase.chinese_meaning || phrase.usage_scene}</p>
            </button>
          ))}
        </div>
        <button onClick={onGenerate} disabled={!selectedPhrase} className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
          <Target className="h-4 w-4" />
          生成三类练习
        </button>
      </SurfaceCard>

      <SurfaceCard className="min-h-[520px]">
        {!activeExercise ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <Target className="h-10 w-10 text-slate-300" />
            <h2 className="mt-4 text-lg font-semibold text-slate-950">一屏一题，开始检测掌握</h2>
            <p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">选择一句收藏表达后生成识别、填空、替换三类题，练习结果会写入 attempt。</p>
          </div>
        ) : (
          <div className="mx-auto flex max-w-2xl flex-col gap-5">
            <div className="flex items-center justify-between">
              <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">{exerciseTypeLabel(activeExercise.exercise_type)}</span>
              <span className="text-xs font-medium text-slate-500">
                {activeExerciseIndex + 1} / {exercises.length}
              </span>
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-500">题目</p>
              <p className="mt-2 whitespace-pre-wrap text-xl font-semibold leading-relaxed text-slate-950">{activeExercise.prompt}</p>
            </div>
            {activeExercise.options.length > 0 && (
              <div className="grid gap-2">
                {activeExercise.options.map((option) => (
                  <button key={option} onClick={() => onAnswerChange(activeExercise.id, option)} className="rounded-[13px] border border-slate-200 p-3 text-left text-sm text-slate-700 hover:border-indigo-200 hover:text-indigo-600">
                    {option}
                  </button>
                ))}
              </div>
            )}
            <textarea
              value={answers[activeExercise.id] ?? ''}
              onChange={(event) => onAnswerChange(activeExercise.id, event.target.value)}
              className="min-h-28 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm leading-6 outline-none focus:border-primary"
              placeholder="输入你的答案或造句"
            />
            <div className="flex flex-wrap gap-2">
              <button onClick={() => onSubmit(activeExercise)} className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
                <Clipboard className="h-4 w-4" />
                提交并记录
              </button>
              <button onClick={onPrevious} disabled={activeExerciseIndex === 0} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:border-indigo-200 hover:text-indigo-600 disabled:opacity-50">
                上一题
              </button>
              <button onClick={onNext} disabled={activeExerciseIndex >= exercises.length - 1} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:border-indigo-200 hover:text-indigo-600 disabled:opacity-50">
                下一题
              </button>
            </div>
          </div>
        )}
      </SurfaceCard>
    </div>
  )
}

function WritingAssistWorkspace({ phrasesByPosition }: { phrasesByPosition: Record<string, WritingPhrase[]> }) {
  const sections = [
    { id: 'opening', label: '开头', hint: '引出话题、提出背景、呈现争议' },
    { id: 'body', label: '主体', hint: '递进、转折、举例、强调重点' },
    { id: 'closing', label: '结尾', hint: '总结观点、升华意义、提出建议' },
  ]
  return (
    <SurfaceCard className="space-y-5">
      <div>
        <h2 className="text-base font-semibold text-slate-950">写作调用</h2>
        <p className="mt-1 text-sm leading-6 text-slate-500">按作文位置快速挑选可用句式。后续可以接入作文主题推荐和插入草稿。</p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {sections.map((section) => (
          <div key={section.id} className="rounded-[13px] border border-slate-200 p-4">
            <p className="font-semibold text-slate-950">{section.label}</p>
            <p className="mt-1 text-sm leading-6 text-slate-500">{section.hint}</p>
            <div className="mt-4 space-y-3">
              {(phrasesByPosition[section.id] ?? []).slice(0, 4).map((phrase) => (
                <div key={phrase.id} className="rounded-lg bg-slate-50 p-3">
                  <p className="text-sm font-semibold leading-6 text-slate-950">{phrase.text}</p>
                  <p className="mt-1 text-xs text-slate-500">{phrase.chinese_meaning || phrase.usage_scene}</p>
                </div>
              ))}
              {(phrasesByPosition[section.id] ?? []).length === 0 && <p className="text-sm text-slate-400">暂无该位置句式。</p>}
            </div>
          </div>
        ))}
      </div>
    </SurfaceCard>
  )
}

function PhraseEditDrawer({
  form,
  isSaving,
  isSelected,
  onChange,
  onClose,
  onDelete,
  onSave,
}: {
  form: PhraseForm
  isSaving: boolean
  isSelected: boolean
  onChange: (form: PhraseForm) => void
  onClose: () => void
  onDelete: () => void
  onSave: () => void
}) {
  const update = (payload: Partial<PhraseForm>) => onChange({ ...form, ...payload })
  return (
    <div className="fixed inset-0 z-[60] bg-slate-950/35">
      <div className="ml-auto flex h-full w-full max-w-2xl flex-col bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 p-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-primary">Edit Phrase</p>
            <h2 className="mt-1 text-xl font-black text-slate-950">{isSelected ? '编辑句式' : '新增句式'}</h2>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" title="关闭">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex-1 space-y-5 overflow-y-auto p-5">
          <FormSection title="基础信息">
            <Field label="英文句式" value={form.text} onChange={(value) => update({ text: value })} textarea />
            <Field label="中文含义" value={form.chinese_meaning} onChange={(value) => update({ chinese_meaning: value })} />
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm">
                <span className="font-medium text-slate-950">使用位置</span>
                <select value={form.usage_position} onChange={(event) => update({ usage_position: event.target.value })} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 outline-none focus:border-primary">
                  <option value="opening">开头</option>
                  <option value="body">主体</option>
                  <option value="closing">结尾</option>
                  <option value="translation">翻译</option>
                </select>
              </label>
              <label className="text-sm">
                <span className="font-medium text-slate-950">难度</span>
                <input type="number" min={1} max={5} value={form.difficulty} onChange={(event) => update({ difficulty: Number(event.target.value) })} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 outline-none focus:border-primary" />
              </label>
            </div>
          </FormSection>

          <FormSection title="使用说明">
            <Field label="解释说明" value={form.explanation} onChange={(value) => update({ explanation: value })} textarea />
            <Field label="适用场景" value={form.usage_scene} onChange={(value) => update({ usage_scene: value })} textarea />
            <Field label="注意事项" value={form.notes_text} onChange={(value) => update({ notes_text: value })} textarea />
            <Field label="常见错误" value={form.mistakes_text} onChange={(value) => update({ mistakes_text: value })} textarea />
          </FormSection>

          <FormSection title="例句与标签">
            <Field label="例句" value={form.examples_text} onChange={(value) => update({ examples_text: value })} textarea />
            <Field label="标签" value={form.tags_text} onChange={(value) => update({ tags_text: value })} />
            <div className="flex flex-wrap gap-4 text-sm text-slate-600">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={form.is_favorite} onChange={(event) => update({ is_favorite: event.target.checked })} />
                收藏
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={form.review_enabled} onChange={(event) => update({ review_enabled: event.target.checked })} />
                加入复习
              </label>
            </div>
          </FormSection>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 p-5">
          {isSelected ? (
            <button onClick={onDelete} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-500 hover:border-red-200 hover:text-error">
              <Trash2 className="h-4 w-4" />
              删除
            </button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <button onClick={onClose} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:border-indigo-200 hover:text-indigo-600">
              取消
            </button>
            <button onClick={onSave} disabled={isSaving} className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-60">
              <Save className="h-4 w-4" />
              保存
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function EmptyLibrary({ onCreateDemo }: { onCreateDemo: () => void }) {
  return (
    <div className="rounded-[13px] border border-dashed border-slate-200 p-6 text-sm text-slate-500">
      <Sparkles className="h-8 w-8 text-slate-300" />
      <p className="mt-3 font-semibold text-slate-950">还没有收藏句式</p>
      <p className="mt-1 leading-6">可以先创建示例，或从外部模型导入一组分层递进表达。</p>
      <button onClick={onCreateDemo} className="mt-4 inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 font-medium text-slate-700 hover:border-indigo-200 hover:text-indigo-600">
        <Sparkles className="h-4 w-4" />
        创建示例
      </button>
    </div>
  )
}

function TagRow({ label, tags, activeTag, onSelect }: { label: string; tags: string[]; activeTag: string; onSelect: (tag: string) => void }) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold text-slate-500">{label}</p>
      <div className="flex flex-wrap gap-2">
        {tags.map((tag) => (
          <FilterChip key={tag} active={activeTag === tag} onClick={() => onSelect(tag)}>
            {tag}
          </FilterChip>
        ))}
      </div>
    </div>
  )
}

function LearningInfo({ title, body, tone }: { title: string; body: string; tone: 'primary' | 'warning' }) {
  const toneClass = tone === 'primary' ? 'border-primary/20 bg-primary/5 text-primary' : 'border-warning/20 bg-warning/5 text-warning'
  return (
    <div className={`rounded-[13px] border p-4 ${toneClass}`}>
      <p className="text-xs font-semibold">{title}</p>
      <p className="mt-2 text-sm leading-6 text-slate-700">{body}</p>
    </div>
  )
}

function DetailSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-sm font-semibold text-slate-950">{title}</h3>
      {children}
    </section>
  )
}

function FormSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3 rounded-[13px] border border-slate-200 p-4">
      <h3 className="text-sm font-semibold text-slate-950">{title}</h3>
      {children}
    </section>
  )
}

function Bullets({ items, fallback }: { items: string[]; fallback: string }) {
  if (items.length === 0) return <p className="text-sm text-slate-500">{fallback}</p>
  return (
    <ul className="space-y-2 text-sm leading-6 text-slate-600">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  )
}

function IconButton({ title, children, onClick }: { title: string; children: ReactNode; onClick: () => void }) {
  return (
    <button onClick={onClick} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-primary" title={title}>
      {children}
    </button>
  )
}

function Field({ label, value, onChange, textarea = false }: { label: string; value: string; onChange: (value: string) => void; textarea?: boolean }) {
  const className = 'mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm leading-6 outline-none focus:border-primary'
  return (
    <label className="block text-sm">
      <span className="font-medium text-slate-950">{label}</span>
      {textarea ? (
        <textarea value={value} onChange={(event) => onChange(event.target.value)} className={`${className} min-h-24`} />
      ) : (
        <input value={value} onChange={(event) => onChange(event.target.value)} className={className} />
      )}
    </label>
  )
}

function positionLabel(position?: string | null) {
  if (position === 'opening') return '开头'
  if (position === 'closing') return '结尾'
  if (position === 'translation') return '翻译'
  return '主体'
}

function exerciseTypeLabel(type: PhraseExercise['exercise_type']) {
  if (type === 'recognition') return '识别题'
  if (type === 'blank') return '填空题'
  return '替换题'
}
