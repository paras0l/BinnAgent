import { useCallback, useEffect, useId, useMemo, useState } from 'react'
import {
  ArrowLeft,
  BookOpenCheck,
  CheckCircle2,
  ClipboardList,
  ExternalLink,
  FileText,
  Gauge,
  History,
  Highlighter,
  Layers3,
  ListChecks,
  PanelLeftOpen,
  PencilLine,
  RotateCw,
  Save,
  SearchCheck,
  Timer,
} from 'lucide-react'
import { FeatureHero } from '@/components/layout/FeatureHero'
import { PageShell } from '@/components/layout/PageShell'
import { WorkspaceTabs, type WorkspaceTab } from '@/components/layout/WorkspaceTabs'
import { ExerciseBlock } from '@/components/exercise/ExerciseBlock'
import { Button } from '@/components/ui/Button'
import { FormField } from '@/components/ui/FormField'
import { Select } from '@/components/ui/Select'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import { useFocusTrap } from '@/hooks/useFocusTrap'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import {
  READING_GOAL_LABELS,
  READING_GRAMMAR_OPTIONS,
  READING_LEVEL_LABELS,
  buildKeywordCandidates,
  buildSentenceFocusHints,
  countEnglishWords,
  estimateReadingMinutes,
  splitReadingSentences,
  suggestGrammarOptionIds,
  uniqueList,
  type ReadingGrammarOption,
  type ReadingKeywordCandidate,
  type ReadingLevel,
  type ReadingMaterial,
  type ReadingMaterialCompleteResponse,
  type ReadingMaterialHistoryItem,
  type ReadingSentence,
  type ReadingSentenceHint,
  type ReadingTitleSuggestionResponse,
  type ReadingTrainingGoal,
  type ReadingWorkspace,
} from '@/data/readingWorkshop'
import type { Learner } from '@/types'
import type { ExerciseTarget } from '@/types/exercises'
import { GrammarPage } from '@/pages/GrammarPage'

interface ReadingWorkshopPageProps {
  learner: Learner
  onBack: () => void
  initialMaterial?: ReadingMaterial
  initialMaterialId?: string | null
  initialSourceLabel?: string | null
}

interface ExtensiveNotes {
  gist: string
  attitude: string
  paragraphFunction: string
  centralSentence: string
}

interface IntensiveNotes {
  mainStructure: string
  phraseNotes: string
  evidenceNote: string
}

type TitleMode = 'empty' | 'auto' | 'user'
type TitleSuggestionStatus = 'idle' | 'checking' | 'suggested' | 'incomplete' | 'error'
type MaterialHistoryStatus = 'idle' | 'loading' | 'ready' | 'error'
type MaterialSaveStatus = 'idle' | 'saving' | 'saved' | 'error'
type MaterialCompleteStatus = 'idle' | 'saving' | 'completed' | 'error'

const SAMPLE_TEXT = `Many students believe that reading faster simply means moving their eyes quickly across a page. However, effective readers do more than race through words. They first notice the title, predict the topic, and look for sentences that show the writer's main point. When a sentence becomes difficult, they slow down, find the main verb, and separate extra information from the core meaning.`

const EMPTY_MATERIAL: ReadingMaterial = {
  title: '',
  text: '',
  level: 'general',
  goal: 'mixed',
  material_type: 'passage',
}

const EMPTY_EXTENSIVE_NOTES: ExtensiveNotes = {
  gist: '',
  attitude: '',
  paragraphFunction: '',
  centralSentence: '',
}

const EMPTY_INTENSIVE_NOTES: IntensiveNotes = {
  mainStructure: '',
  phraseNotes: '',
  evidenceNote: '',
}

const WORKSPACE_TABS: WorkspaceTab<ReadingWorkspace>[] = [
  { id: 'input', label: '材料输入', description: '标题与原文', icon: <FileText className="h-4 w-4" /> },
  { id: 'extensive', label: '泛读模式', description: '主旨与结构', icon: <Gauge className="h-4 w-4" /> },
  { id: 'intensive', label: '精读模式', description: '句子与语法', icon: <Highlighter className="h-4 w-4" /> },
  { id: 'review', label: '沉淀复盘', description: '本次记录', icon: <ClipboardList className="h-4 w-4" /> },
]

const READING_GRAMMAR_EXERCISE_TARGET_IDS: Record<string, string> = {
  主将从现: 'present-for-future',
  'because 与 because of': 'because-because-of',
  '定语从句中 which/that 的选择': 'which-that-relative',
}

export function ReadingWorkshopPage({
  learner,
  onBack,
  initialMaterial,
  initialMaterialId = null,
  initialSourceLabel = null,
}: ReadingWorkshopPageProps) {
  const hasInitialMaterial = Boolean(initialMaterial?.text.trim())
  const [workspace, setWorkspace] = useState<ReadingWorkspace>('input')
  const [material, setMaterial] = useState<ReadingMaterial>(() => (
    hasInitialMaterial
      ? { ...initialMaterial, material_type: initialMaterial?.material_type ?? 'passage' } as ReadingMaterial
      : EMPTY_MATERIAL
  ))
  const [extensiveNotes, setExtensiveNotes] = useState<ExtensiveNotes>(EMPTY_EXTENSIVE_NOTES)
  const [intensiveNotes, setIntensiveNotes] = useState<IntensiveNotes>(EMPTY_INTENSIVE_NOTES)
  const [titleMode, setTitleMode] = useState<TitleMode>(hasInitialMaterial && initialMaterial?.title ? 'auto' : 'empty')
  const [titleSuggestionStatus, setTitleSuggestionStatus] = useState<TitleSuggestionStatus>(
    hasInitialMaterial && initialMaterial?.title ? 'suggested' : 'idle'
  )
  const [autoTitleSourceText, setAutoTitleSourceText] = useState(hasInitialMaterial ? initialMaterial?.text ?? '' : '')
  const [materialHistory, setMaterialHistory] = useState<ReadingMaterialHistoryItem[]>([])
  const [activeMaterialId, setActiveMaterialId] = useState<string | null>(initialMaterialId)
  const [historyStatus, setHistoryStatus] = useState<MaterialHistoryStatus>('idle')
  const [saveStatus, setSaveStatus] = useState<MaterialSaveStatus>(initialMaterialId ? 'saved' : 'idle')
  const [completeStatus, setCompleteStatus] = useState<MaterialCompleteStatus>('idle')
  const [completionResult, setCompletionResult] = useState<ReadingMaterialCompleteResponse | null>(null)
  const [selectedSentenceId, setSelectedSentenceId] = useState<string | null>(hasInitialMaterial ? 'reading-sentence-1' : null)
  const [visitedSentenceIds, setVisitedSentenceIds] = useState<string[]>(hasInitialMaterial ? ['reading-sentence-1'] : [])
  const [selectedGrammarOptionIds, setSelectedGrammarOptionIds] = useState<string[]>([])
  const [openedGrammarTopics, setOpenedGrammarTopics] = useState<string[]>([])
  const [grammarTopic, setGrammarTopic] = useState<string | null>(null)

  const sentences = useMemo(() => splitReadingSentences(material.text), [material.text])
  const keywordCandidates = useMemo(() => buildKeywordCandidates(material.text), [material.text])
  const wordCount = useMemo(() => countEnglishWords(material.text), [material.text])
  const estimatedMinutes = useMemo(() => estimateReadingMinutes(material.text, material.level), [material.level, material.text])
  const selectedSentence = useMemo(
    () => sentences.find((sentence) => sentence.id === selectedSentenceId) ?? sentences[0] ?? null,
    [selectedSentenceId, sentences]
  )
  const selectedSentenceHints = useMemo(
    () => buildSentenceFocusHints(selectedSentence?.text ?? ''),
    [selectedSentence]
  )
  const suggestedGrammarOptionIds = useMemo(
    () => suggestGrammarOptionIds(selectedSentence?.text ?? ''),
    [selectedSentence]
  )
  const selectedGrammarOptions = useMemo(
    () => READING_GRAMMAR_OPTIONS.filter((option) => selectedGrammarOptionIds.includes(option.id)),
    [selectedGrammarOptionIds]
  )
  const visitedSentences = useMemo(
    () => visitedSentenceIds
      .map((id) => sentences.find((sentence) => sentence.id === id))
      .filter((sentence): sentence is ReadingSentence => Boolean(sentence)),
    [sentences, visitedSentenceIds]
  )
  const canUseMaterial = material.text.trim().length > 0

  const loadMaterialHistory = useCallback(async () => {
    setHistoryStatus('loading')
    try {
      const response = await fetch(`/api/learners/${learner.id}/reading-workshop/materials`)
      if (!response.ok) throw new Error('Failed to load reading material history')
      const data = (await response.json()) as ReadingMaterialHistoryItem[]
      setMaterialHistory(data)
      setHistoryStatus('ready')
    } catch (error) {
      console.error('Reading material history load error:', error)
      setHistoryStatus('error')
    }
  }, [learner.id])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadMaterialHistory(), 0)
    return () => window.clearTimeout(timer)
  }, [loadMaterialHistory])

  const saveCurrentMaterial = useCallback(async () => {
    const text = material.text.trim()
    if (!text) return null

    setSaveStatus('saving')
    try {
      const response = await fetch(`/api/learners/${learner.id}/reading-workshop/materials`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: material.title.trim() || null,
          text,
          level: material.level,
          goal: material.goal,
          material_type: material.material_type ?? 'passage',
        }),
      })
      if (!response.ok) throw new Error('Failed to save reading material')
      const saved = (await response.json()) as ReadingMaterialHistoryItem
      setActiveMaterialId(saved.id)
      setMaterialHistory((current) => [
        saved,
        ...current.filter((item) => item.id !== saved.id),
      ].slice(0, 20))
      setSaveStatus('saved')
      return saved
    } catch (error) {
      console.error('Reading material save error:', error)
      setSaveStatus('error')
      return null
    }
  }, [learner.id, material.goal, material.level, material.material_type, material.text, material.title])

  useEffect(() => {
    const text = material.text.trim()
    if (titleMode === 'user') return
    if (!text) return
    if (titleMode === 'auto' && autoTitleSourceText === text) return

    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setTitleSuggestionStatus('checking')
      fetch('/api/reading-workshop/title-suggestion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
        signal: controller.signal,
      })
        .then((response) => {
          if (!response.ok) throw new Error('Failed to suggest reading title')
          return response.json() as Promise<ReadingTitleSuggestionResponse>
        })
        .then((data) => {
          if (!data.is_complete || !data.suggested_title) {
            if (titleMode === 'auto') {
              setMaterial((current) => ({ ...current, title: '' }))
              setTitleMode('empty')
              setAutoTitleSourceText('')
            }
            setTitleSuggestionStatus('incomplete')
            return
          }
          setMaterial((current) => ({ ...current, title: data.suggested_title ?? current.title }))
          setTitleMode('auto')
          setAutoTitleSourceText(text)
          setTitleSuggestionStatus('suggested')
        })
        .catch((error) => {
          if (error instanceof DOMException && error.name === 'AbortError') return
          console.error('Reading title suggestion error:', error)
          setTitleSuggestionStatus('error')
        })
    }, 700)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [autoTitleSourceText, material.text, titleMode])

  const openWorkspace = (nextWorkspace: ReadingWorkspace) => {
    if (nextWorkspace === 'intensive' && sentences[0] && !selectedSentenceId) {
      setSelectedSentenceId(sentences[0].id)
      setVisitedSentenceIds((current) => uniqueList([...current, sentences[0].id]))
    }
    setWorkspace(nextWorkspace)
  }

  const startTraining = (nextWorkspace: ReadingWorkspace) => {
    void saveCurrentMaterial()
    openWorkspace(nextWorkspace)
  }

  const loadSampleMaterial = () => {
    setMaterial({
      title: 'How Effective Readers Work',
      text: SAMPLE_TEXT,
      level: 'general',
      goal: 'mixed',
      material_type: 'passage',
    })
    setActiveMaterialId(null)
    setTitleMode('auto')
    setTitleSuggestionStatus('suggested')
    setAutoTitleSourceText(SAMPLE_TEXT)
    setSelectedSentenceId('reading-sentence-1')
    setVisitedSentenceIds(['reading-sentence-1'])
    setWorkspace('input')
  }

  const updateTitle = (title: string) => {
    setTitleMode('user')
    setSaveStatus('idle')
    setCompleteStatus('idle')
    setCompletionResult(null)
    setMaterial((current) => ({ ...current, title }))
  }

  const updateText = (text: string) => {
    setSaveStatus('idle')
    setActiveMaterialId(null)
    setCompleteStatus('idle')
    setCompletionResult(null)
    if (!text.trim() && titleMode !== 'user') {
      setTitleMode('empty')
      setAutoTitleSourceText('')
      setTitleSuggestionStatus('idle')
      setMaterial((current) => ({ ...current, title: '', text }))
      return
    }
    setMaterial((current) => ({ ...current, text }))
  }

  const restoreMaterial = (item: ReadingMaterialHistoryItem) => {
    setMaterial({
      title: item.title ?? '',
      text: item.text,
      level: item.level,
      goal: item.goal,
      material_type: item.material_type,
    })
    setActiveMaterialId(item.id)
    setTitleMode(item.title ? 'user' : 'empty')
    setTitleSuggestionStatus(item.title ? 'suggested' : 'idle')
    setAutoTitleSourceText(item.title ? item.text : '')
    setSaveStatus('idle')
    setCompleteStatus('idle')
    setCompletionResult(null)
    setExtensiveNotes(EMPTY_EXTENSIVE_NOTES)
    setIntensiveNotes(EMPTY_INTENSIVE_NOTES)
    setSelectedSentenceId(null)
    setVisitedSentenceIds([])
    setSelectedGrammarOptionIds([])
    setOpenedGrammarTopics([])
    setWorkspace('input')
  }

  const selectSentence = (sentence: ReadingSentence) => {
    setSelectedSentenceId(sentence.id)
    setVisitedSentenceIds((current) => uniqueList([...current, sentence.id]))
  }

  const toggleGrammarOption = (optionId: string) => {
    setSelectedGrammarOptionIds((current) => (
      current.includes(optionId)
        ? current.filter((id) => id !== optionId)
        : uniqueList([...current, optionId])
    ))
  }

  const openGrammarOption = (option: ReadingGrammarOption) => {
    setSelectedGrammarOptionIds((current) => uniqueList([...current, option.id]))
    setOpenedGrammarTopics((current) => uniqueList([...current, option.grammarTopicTitle]))
    setGrammarTopic(option.grammarTopicTitle)
  }

  const completeReadingMaterial = useCallback(async () => {
    if (!material.text.trim()) return
    setCompleteStatus('saving')
    setCompletionResult(null)
    try {
      const saved = activeMaterialId ? null : await saveCurrentMaterial()
      const materialId = activeMaterialId ?? saved?.id
      if (!materialId) throw new Error('请先保存阅读材料。')
      const response = await fetch(`/api/learners/${learner.id}/reading-workshop/materials/${materialId}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          selected_sentence_count: visitedSentenceIds.length,
          grammar_topic_count: selectedGrammarOptionIds.length,
          notes: [
            extensiveNotes.gist ? `gist: ${extensiveNotes.gist}` : '',
            intensiveNotes.mainStructure ? `structure: ${intensiveNotes.mainStructure}` : '',
          ].filter(Boolean).join('\n') || null,
        }),
      })
      if (!response.ok) throw new Error('阅读完成记录保存失败。')
      const data = await response.json() as ReadingMaterialCompleteResponse
      setActiveMaterialId(data.material_id)
      setCompletionResult(data)
      setCompleteStatus('completed')
    } catch (error) {
      console.error('Reading completion error:', error)
      setCompleteStatus('error')
    }
  }, [
    activeMaterialId,
    extensiveNotes.gist,
    intensiveNotes.mainStructure,
    learner.id,
    material.text,
    saveCurrentMaterial,
    selectedGrammarOptionIds.length,
    visitedSentenceIds.length,
  ])

  if (grammarTopic) {
    return (
      <GrammarPage
        learner={learner}
        initialTopic={grammarTopic}
        onBack={() => {
          setGrammarTopic(null)
          setWorkspace('intensive')
        }}
        backLabel="返回精读与泛读"
      />
    )
  }

  return (
    <PageShell>
      <FeatureHero
        eyebrow="Reading Workshop"
        title="精读与泛读"
        description="同一篇材料，精读看结构，泛读抓主旨。先把阅读目标拆开，再把精读里卡住的语法点带到微知识点继续学。"
        stats={[
          { label: '词数', value: wordCount },
          { label: '句子', value: sentences.length },
          { label: '建议泛读', value: `${estimatedMinutes} 分钟`, tone: 'primary' },
          { label: '训练目标', value: READING_GOAL_LABELS[material.goal], tone: 'success' },
        ]}
        actions={
          <Button variant="secondary" onClick={onBack}>
            <ArrowLeft className="h-4 w-4" />
            返回探索
          </Button>
        }
      />

      <WorkspaceTabs tabs={WORKSPACE_TABS} activeTab={workspace} onChange={openWorkspace} />

      {workspace === 'input' && (
        <InputWorkspace
          material={material}
          canUseMaterial={canUseMaterial}
          onLoadSample={loadSampleMaterial}
          onRefreshHistory={loadMaterialHistory}
          onRestoreHistory={restoreMaterial}
          onSaveMaterial={() => void saveCurrentMaterial()}
          onStartTraining={startTraining}
          onTitleChange={updateTitle}
          onTextChange={updateText}
          onLevelChange={(level) => {
            setSaveStatus('idle')
            setActiveMaterialId(null)
            setCompleteStatus('idle')
            setCompletionResult(null)
            setMaterial((current) => ({ ...current, level }))
          }}
          onGoalChange={(goal) => {
            setSaveStatus('idle')
            setActiveMaterialId(null)
            setCompleteStatus('idle')
            setCompletionResult(null)
            setMaterial((current) => ({ ...current, goal }))
          }}
          historyItems={materialHistory}
          historyStatus={historyStatus}
          saveStatus={saveStatus}
          titleSuggestionStatus={titleSuggestionStatus}
        />
      )}

      {workspace === 'extensive' && (
        <ExtensiveWorkspace
          material={material}
          canUseMaterial={canUseMaterial}
          estimatedMinutes={estimatedMinutes}
          keywordCandidates={keywordCandidates}
          notes={extensiveNotes}
          wordCount={wordCount}
          onNotesChange={(key, value) => setExtensiveNotes((current) => ({ ...current, [key]: value }))}
          onOpenWorkspace={openWorkspace}
        />
      )}

      {workspace === 'intensive' && (
        <IntensiveWorkspace
          canUseMaterial={canUseMaterial}
          focusHints={selectedSentenceHints}
          learnerId={learner.id}
          notes={intensiveNotes}
          selectedGrammarOptionIds={selectedGrammarOptionIds}
          selectedSentence={selectedSentence}
          selectedSentenceId={selectedSentence?.id ?? null}
          sentences={sentences}
          suggestedGrammarOptionIds={suggestedGrammarOptionIds}
          onNotesChange={(key, value) => setIntensiveNotes((current) => ({ ...current, [key]: value }))}
          onOpenGrammar={openGrammarOption}
          onOpenWorkspace={openWorkspace}
          onSelectSentence={selectSentence}
          onToggleGrammarOption={toggleGrammarOption}
        />
      )}

      {workspace === 'review' && (
        <ReviewWorkspace
          extensiveNotes={extensiveNotes}
          intensiveNotes={intensiveNotes}
          keywordCandidates={keywordCandidates}
          material={material}
          openedGrammarTopics={openedGrammarTopics}
          selectedGrammarOptions={selectedGrammarOptions}
          selectedSentences={visitedSentences}
          sentences={sentences}
          wordCount={wordCount}
          completeStatus={completeStatus}
          completionResult={completionResult}
          sourceLabel={initialSourceLabel}
          onCompleteReading={() => void completeReadingMaterial()}
          onOpenGrammar={openGrammarOption}
          onOpenWorkspace={openWorkspace}
        />
      )}
    </PageShell>
  )
}

function InputWorkspace({
  material,
  canUseMaterial,
  onGoalChange,
  onLevelChange,
  onLoadSample,
  onRefreshHistory,
  onRestoreHistory,
  onSaveMaterial,
  onStartTraining,
  onTextChange,
  onTitleChange,
  historyItems,
  historyStatus,
  saveStatus,
  titleSuggestionStatus,
}: {
  material: ReadingMaterial
  canUseMaterial: boolean
  historyItems: ReadingMaterialHistoryItem[]
  historyStatus: MaterialHistoryStatus
  onGoalChange: (goal: ReadingTrainingGoal) => void
  onLevelChange: (level: ReadingLevel) => void
  onLoadSample: () => void
  onRefreshHistory: () => void
  onRestoreHistory: (item: ReadingMaterialHistoryItem) => void
  onSaveMaterial: () => void
  onStartTraining: (workspace: ReadingWorkspace) => void
  onTextChange: (text: string) => void
  onTitleChange: (title: string) => void
  saveStatus: MaterialSaveStatus
  titleSuggestionStatus: TitleSuggestionStatus
}) {
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const isHistoryDrawer = useMediaQuery('(max-width: 1279px)')
  const historyPanelId = useId()
  const historyTitleId = useId()
  const { containerRef: historyPanelRef, handleKeyDown: handleHistoryPanelKeyDown } = useFocusTrap<HTMLDivElement>({
    isActive: isHistoryDrawer && isHistoryOpen,
    onEscape: () => setIsHistoryOpen(false),
  })
  const titleDescription = {
    idle: '可选；粘贴完整材料后会自动建议标题，仍可手动修改。',
    checking: '正在根据材料建议标题，仍可手动填写。',
    suggested: '已自动建议标题，仍可手动修改。',
    incomplete: '可选；材料完整后会自动建议标题。',
    error: '自动标题暂时不可用，仍可手动填写。',
  } satisfies Record<TitleSuggestionStatus, string>
  const saveStatusLabel = {
    idle: '保存材料',
    saving: '正在保存',
    saved: '已保存',
    error: '保存失败',
  } satisfies Record<MaterialSaveStatus, string>

  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <SurfaceCard>
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-black text-slate-950">阅读材料</h2>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <FormField
            label="标题"
            name="reading_material_title"
            autoComplete="off"
            description={titleDescription[titleSuggestionStatus]}
            value={material.title}
            onChange={(event) => onTitleChange(event.target.value)}
            placeholder="例如 The Future of Libraries…"
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="难度">
              <Select
                name="reading_material_level"
                autoComplete="off"
                className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                value={material.level}
                onChange={(event) => onLevelChange(event.target.value as ReadingLevel)}
              >
                {(Object.entries(READING_LEVEL_LABELS) as Array<[ReadingLevel, string]>).map(([id, label]) => (
                  <option key={id} value={id}>{label}</option>
                ))}
              </Select>
            </FormField>
            <FormField label="训练目标">
              <Select
                name="reading_training_goal"
                autoComplete="off"
                className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                value={material.goal}
                onChange={(event) => onGoalChange(event.target.value as ReadingTrainingGoal)}
              >
                {(Object.entries(READING_GOAL_LABELS) as Array<[ReadingTrainingGoal, string]>).map(([id, label]) => (
                  <option key={id} value={id}>{label}</option>
                ))}
              </Select>
            </FormField>
          </div>
        </div>
        <div className="mt-4">
          <FormField
            as="textarea"
            label="英文材料"
            name="reading_material_text"
            autoComplete="off"
            value={material.text}
            onChange={(event) => onTextChange(event.target.value)}
            placeholder="Paste an English paragraph here…"
            className="h-64 resize-y"
          />
        </div>
        <div className="mt-5 flex flex-wrap gap-3">
          <Button disabled={!canUseMaterial} onClick={() => onStartTraining(material.goal === 'intensive' ? 'intensive' : 'extensive')}>
            <BookOpenCheck className="h-4 w-4" />
            开始训练
          </Button>
          <Button
            variant="secondary"
            disabled={!canUseMaterial || saveStatus === 'saving'}
            onClick={onSaveMaterial}
          >
            {saveStatus === 'saved' ? <CheckCircle2 className="h-4 w-4" /> : <Save className="h-4 w-4" />}
            {saveStatusLabel[saveStatus]}
          </Button>
          <Button variant="secondary" onClick={onLoadSample}>
            <PencilLine className="h-4 w-4" />
            填入示例
          </Button>
        </div>
      </SurfaceCard>

      <Button
        variant="secondary"
        className="xl:hidden"
        onClick={() => setIsHistoryOpen((current) => !current)}
        aria-expanded={isHistoryOpen}
        aria-controls={historyPanelId}
      >
        <PanelLeftOpen className="h-4 w-4" />
        {isHistoryOpen ? '收起材料历史' : '展开材料历史'}
      </Button>

      {isHistoryDrawer && isHistoryOpen ? (
        <button
          type="button"
          aria-label="收起材料历史"
          onClick={() => setIsHistoryOpen(false)}
          className="fixed inset-x-0 bottom-0 top-16 z-30 bg-slate-950/30 transition-opacity duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary motion-reduce:transition-none xl:hidden"
        />
      ) : null}
      <div
        id={historyPanelId}
        ref={isHistoryDrawer ? historyPanelRef : undefined}
        role={isHistoryDrawer ? 'dialog' : undefined}
        aria-modal={isHistoryDrawer ? 'true' : undefined}
        aria-labelledby={isHistoryDrawer ? historyTitleId : undefined}
        tabIndex={isHistoryDrawer ? -1 : undefined}
        onKeyDown={isHistoryDrawer ? handleHistoryPanelKeyDown : undefined}
        className={isHistoryOpen
          ? 'fixed bottom-0 right-0 top-16 z-40 w-[min(88vw,24rem)] overflow-y-auto overscroll-contain transition-[transform,opacity] duration-200 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-primary motion-reduce:transition-none xl:static xl:w-auto xl:overflow-visible'
          : 'hidden xl:block'
        }
      >
        <SurfaceCard className="flex min-h-full flex-col justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Layers3 className="h-5 w-5 text-success" />
              <h2 className="text-lg font-black text-slate-950">训练顺序</h2>
            </div>
            <div className="mt-5 space-y-3">
              <ModeStep title="泛读" text="先限制时间，判断主旨、态度和段落功能。" />
              <ModeStep title="精读" text="再选择难句，拆主干、修饰语和语法卡点。" />
              <ModeStep title="沉淀" text="最后留下本次材料、句子和去学过的语法点。" />
            </div>
          </div>
          <div className="mt-5 rounded-lg border border-primary/20 bg-primary/5 p-4 text-sm leading-6 text-primary">
            精读和泛读处理同一篇材料，但训练目标不同：泛读少看细节，精读少求速度。
          </div>

          <div className="mt-5 border-t border-slate-200 pt-5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <History className="h-5 w-5 text-primary" />
                <h2 id={historyTitleId} className="text-lg font-black text-slate-950">材料历史</h2>
              </div>
              <button
                type="button"
                aria-label="刷新历史记录"
                className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-slate-100 hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                onClick={onRefreshHistory}
                title="刷新历史记录"
              >
                <RotateCw className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-4 max-h-[420px] space-y-3 overflow-y-auto pr-1">
              {historyStatus === 'loading' ? (
                <p className="rounded-lg border border-dashed border-slate-200 p-3 text-sm text-muted-foreground">
                  正在加载历史材料…
                </p>
              ) : historyStatus === 'error' ? (
                <p className="rounded-lg border border-dashed border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                  历史材料暂时无法加载。
                </p>
              ) : historyItems.length > 0 ? (
                historyItems.map((item) => (
                  <HistoryItem
                    key={item.id}
                    item={item}
                    onRestore={() => {
                      onRestoreHistory(item)
                      setIsHistoryOpen(false)
                    }}
                  />
                ))
              ) : (
                <p className="rounded-lg border border-dashed border-slate-200 p-3 text-sm leading-6 text-muted-foreground">
                  还没有历史材料。开始训练或点击保存后会出现在这里。
                </p>
              )}
            </div>
          </div>
        </SurfaceCard>
      </div>
    </section>
  )
}

function ExtensiveWorkspace({
  material,
  canUseMaterial,
  estimatedMinutes,
  keywordCandidates,
  notes,
  wordCount,
  onNotesChange,
  onOpenWorkspace,
}: {
  material: ReadingMaterial
  canUseMaterial: boolean
  estimatedMinutes: number
  keywordCandidates: ReadingKeywordCandidate[]
  notes: ExtensiveNotes
  wordCount: number
  onNotesChange: (key: keyof ExtensiveNotes, value: string) => void
  onOpenWorkspace: (workspace: ReadingWorkspace) => void
}) {
  if (!canUseMaterial) {
    return <EmptyMaterialCard onOpenInput={() => onOpenWorkspace('input')} />
  }

  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_390px]">
      <SurfaceCard>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-primary">Extensive Reading</p>
            <h2 className="mt-1 text-lg font-black text-slate-950">{material.title.trim() || '未命名阅读材料'}</h2>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm sm:w-56">
            <MetricTile label="词数" value={wordCount} />
            <MetricTile label="建议" value={`${estimatedMinutes} 分钟`} />
          </div>
        </div>

        <div className="mt-5 max-h-[460px] overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm leading-7 text-slate-700">
          {material.text}
        </div>
      </SurfaceCard>

      <div className="grid gap-5">
        <SurfaceCard>
          <div className="flex items-center gap-2">
            <Timer className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-black text-slate-950">泛读任务</h2>
          </div>
          <div className="mt-4 space-y-4">
            <FormField
              as="textarea"
              label="主旨判断"
              name="reading_gist_note"
              autoComplete="off"
              value={notes.gist}
              onChange={(event) => onNotesChange('gist', event.target.value)}
              placeholder="这段材料主要讲什么…"
            />
            <FormField
              label="作者态度"
              name="reading_attitude_note"
              autoComplete="off"
              value={notes.attitude}
              onChange={(event) => onNotesChange('attitude', event.target.value)}
              placeholder="支持 / 反对 / 中立，以及依据…"
            />
            <FormField
              label="段落功能"
              name="reading_paragraph_function_note"
              autoComplete="off"
              value={notes.paragraphFunction}
              onChange={(event) => onNotesChange('paragraphFunction', event.target.value)}
              placeholder="引入问题 / 解释原因 / 举例 / 总结…"
            />
            <FormField
              label="中心句"
              name="reading_central_sentence_note"
              autoComplete="off"
              value={notes.centralSentence}
              onChange={(event) => onNotesChange('centralSentence', event.target.value)}
              placeholder="哪一句最能概括段落中心…"
            />
          </div>
        </SurfaceCard>

        <SurfaceCard>
          <div className="flex items-center gap-2">
            <SearchCheck className="h-5 w-5 text-success" />
            <h2 className="text-lg font-black text-slate-950">关键词圈定</h2>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {keywordCandidates.length > 0 ? (
              keywordCandidates.map((keyword) => (
                <span key={keyword.word} className="rounded-md bg-success/10 px-2.5 py-1 text-xs font-bold text-success">
                  {keyword.word}
                  {keyword.count > 1 ? ` x${keyword.count}` : ''}
                </span>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">材料较短时，可先手动圈出重复出现的名词和动词。</p>
            )}
          </div>
          <Button className="mt-5 w-full" variant="secondary" onClick={() => onOpenWorkspace('intensive')}>
            <Highlighter className="h-4 w-4" />
            进入精读拆句
          </Button>
        </SurfaceCard>
      </div>
    </section>
  )
}

function IntensiveWorkspace({
  canUseMaterial,
  focusHints,
  learnerId,
  notes,
  selectedGrammarOptionIds,
  selectedSentence,
  selectedSentenceId,
  sentences,
  suggestedGrammarOptionIds,
  onNotesChange,
  onOpenGrammar,
  onOpenWorkspace,
  onSelectSentence,
  onToggleGrammarOption,
}: {
  canUseMaterial: boolean
  focusHints: ReadingSentenceHint[]
  learnerId: string
  notes: IntensiveNotes
  selectedGrammarOptionIds: string[]
  selectedSentence: ReadingSentence | null
  selectedSentenceId: string | null
  sentences: ReadingSentence[]
  suggestedGrammarOptionIds: string[]
  onNotesChange: (key: keyof IntensiveNotes, value: string) => void
  onOpenGrammar: (option: ReadingGrammarOption) => void
  onOpenWorkspace: (workspace: ReadingWorkspace) => void
  onSelectSentence: (sentence: ReadingSentence) => void
  onToggleGrammarOption: (optionId: string) => void
}) {
  const [isSentenceListOpen, setIsSentenceListOpen] = useState(false)
  const isSentenceListDrawer = useMediaQuery('(max-width: 1279px)')
  const sentenceListPanelId = useId()
  const sentenceListTitleId = useId()
  const { containerRef: sentenceListPanelRef, handleKeyDown: handleSentenceListPanelKeyDown } = useFocusTrap<HTMLDivElement>({
    isActive: isSentenceListDrawer && isSentenceListOpen,
    onEscape: () => setIsSentenceListOpen(false),
  })
  if (!canUseMaterial) {
    return <EmptyMaterialCard onOpenInput={() => onOpenWorkspace('input')} />
  }

  const selectedGrammarOptions = READING_GRAMMAR_OPTIONS.filter((option) =>
    selectedGrammarOptionIds.includes(option.id)
  )

  return (
    <section className="grid gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
      <Button
        variant="secondary"
        className="xl:hidden"
        onClick={() => setIsSentenceListOpen((current) => !current)}
        aria-expanded={isSentenceListOpen}
        aria-controls={sentenceListPanelId}
      >
        <PanelLeftOpen className="h-4 w-4" />
        {isSentenceListOpen ? '收起句子列表' : '展开句子列表'}
      </Button>

      {isSentenceListDrawer && isSentenceListOpen ? (
        <button
          type="button"
          aria-label="收起句子列表"
          onClick={() => setIsSentenceListOpen(false)}
          className="fixed inset-x-0 bottom-0 top-16 z-30 bg-slate-950/30 transition-opacity duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary motion-reduce:transition-none xl:hidden"
        />
      ) : null}
      <div
        id={sentenceListPanelId}
        ref={isSentenceListDrawer ? sentenceListPanelRef : undefined}
        role={isSentenceListDrawer ? 'dialog' : undefined}
        aria-modal={isSentenceListDrawer ? 'true' : undefined}
        aria-labelledby={isSentenceListDrawer ? sentenceListTitleId : undefined}
        tabIndex={isSentenceListDrawer ? -1 : undefined}
        onKeyDown={isSentenceListDrawer ? handleSentenceListPanelKeyDown : undefined}
        className={isSentenceListOpen
          ? 'fixed bottom-0 left-0 top-16 z-40 w-[min(88vw,24rem)] overflow-y-auto overscroll-contain transition-[transform,opacity] duration-200 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-primary motion-reduce:transition-none xl:static xl:w-auto xl:overflow-visible'
          : 'hidden xl:block'
        }
      >
        <SurfaceCard className="min-h-full">
          <div className="flex items-center gap-2">
            <ListChecks className="h-5 w-5 text-primary" />
            <h2 id={sentenceListTitleId} className="text-lg font-black text-slate-950">选择精读句子</h2>
          </div>
          <div className="mt-4 max-h-[620px] space-y-2 overflow-y-auto pr-1">
            {sentences.map((sentence) => (
              <button
                key={sentence.id}
                type="button"
                onClick={() => {
                  onSelectSentence(sentence)
                  setIsSentenceListOpen(false)
                }}
                className={`w-full rounded-lg border p-3 text-left text-sm leading-6 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
                  selectedSentenceId === sentence.id
                    ? 'border-primary bg-primary/5 text-primary'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-primary/30 hover:text-slate-950'
                }`}
              >
                <span className="mb-1 block text-xs font-black">Sentence {sentence.order}</span>
                {sentence.text}
              </button>
            ))}
          </div>
        </SurfaceCard>
      </div>

      <div className="grid gap-5">
        <SurfaceCard>
          <div className="flex items-center gap-2">
            <Highlighter className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-black text-slate-950">当前句子拆解</h2>
          </div>
          {selectedSentence ? (
            <>
              <p className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-base leading-7 text-slate-800">
                {selectedSentence.text}
              </p>
              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                {focusHints.map((hint) => (
                  <div key={hint.id} className="rounded-lg border border-slate-200 p-3">
                    <p className="text-sm font-black text-slate-950">{hint.label}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-500">{hint.text}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 grid gap-4 lg:grid-cols-3">
                <FormField
                  as="textarea"
                  label="主干识别"
                  name="reading_main_structure"
                  autoComplete="off"
                  value={notes.mainStructure}
                  onChange={(event) => onNotesChange('mainStructure', event.target.value)}
                  placeholder="S + V + O/C…"
                />
                <FormField
                  as="textarea"
                  label="词组和搭配"
                  name="reading_phrase_notes"
                  autoComplete="off"
                  value={notes.phraseNotes}
                  onChange={(event) => onNotesChange('phraseNotes', event.target.value)}
                  placeholder="记录值得复用的短语…"
                />
                <FormField
                  as="textarea"
                  label="细节证据"
                  name="reading_evidence_note"
                  autoComplete="off"
                  value={notes.evidenceNote}
                  onChange={(event) => onNotesChange('evidenceNote', event.target.value)}
                  placeholder="这句话支持了哪一个细节…"
                />
              </div>
            </>
          ) : (
            <p className="mt-4 text-sm text-muted-foreground">材料中还没有可选择的句子。</p>
          )}
        </SurfaceCard>

        <SurfaceCard>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <ExternalLink className="h-5 w-5 text-success" />
              <h2 className="text-lg font-black text-slate-950">发现语法点</h2>
            </div>
            <p className="text-xs text-muted-foreground">先标记卡点，再跳转到语法微知识点。</p>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {READING_GRAMMAR_OPTIONS.map((option) => (
              <GrammarOptionCard
                key={option.id}
                option={option}
                isSelected={selectedGrammarOptionIds.includes(option.id)}
                isSuggested={suggestedGrammarOptionIds.includes(option.id)}
                onOpen={() => onOpenGrammar(option)}
                onToggle={() => onToggleGrammarOption(option.id)}
              />
            ))}
          </div>
        </SurfaceCard>

        {selectedGrammarOptions.length > 0 ? (
          <div className="grid gap-3">
            <div className="flex items-center gap-2 px-1">
              <BookOpenCheck className="h-5 w-5 text-primary" />
              <h2 className="text-lg font-black text-slate-950">做 3 道相关小练习</h2>
            </div>
            {selectedGrammarOptions.map((option) => (
              <ExerciseBlock
                key={option.id}
                learnerId={learnerId}
                target={getGrammarExerciseTargetFromReadingOption(option)}
                limit={3}
              />
            ))}
          </div>
        ) : null}
      </div>
    </section>
  )
}

function ReviewWorkspace({
  completeStatus,
  completionResult,
  extensiveNotes,
  intensiveNotes,
  keywordCandidates,
  material,
  openedGrammarTopics,
  selectedGrammarOptions,
  selectedSentences,
  sentences,
  sourceLabel,
  wordCount,
  onCompleteReading,
  onOpenGrammar,
  onOpenWorkspace,
}: {
  completeStatus: MaterialCompleteStatus
  completionResult: ReadingMaterialCompleteResponse | null
  extensiveNotes: ExtensiveNotes
  intensiveNotes: IntensiveNotes
  keywordCandidates: ReadingKeywordCandidate[]
  material: ReadingMaterial
  openedGrammarTopics: string[]
  selectedGrammarOptions: ReadingGrammarOption[]
  selectedSentences: ReadingSentence[]
  sentences: ReadingSentence[]
  sourceLabel: string | null
  wordCount: number
  onCompleteReading: () => void
  onOpenGrammar: (option: ReadingGrammarOption) => void
  onOpenWorkspace: (workspace: ReadingWorkspace) => void
}) {
  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <SurfaceCard>
        <div className="flex items-center gap-2">
          <ClipboardList className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-black text-slate-950">本次阅读沉淀</h2>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <MetricTile label="材料" value={material.title.trim() || '未命名'} />
          <MetricTile label="词数 / 句子" value={`${wordCount} / ${sentences.length}`} />
          <MetricTile label="目标" value={READING_GOAL_LABELS[material.goal]} />
        </div>

        <div className="mt-5 grid gap-4 xl:grid-cols-3">
          <KeywordFrequencyChart keywords={keywordCandidates.slice(0, 8)} />
          <SentenceDifficultyHeatmap sentences={sentences} selectedSentences={selectedSentences} />
          <GrammarTroubleChart
            openedGrammarTopics={openedGrammarTopics}
            selectedGrammarOptions={selectedGrammarOptions}
          />
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <ReadingFlowProgress
            extensiveNotes={extensiveNotes}
            intensiveNotes={intensiveNotes}
            openedGrammarTopics={openedGrammarTopics}
            selectedGrammarOptions={selectedGrammarOptions}
            selectedSentences={selectedSentences}
            sentences={sentences}
          />
          <ReadingCoveragePanel selectedSentences={selectedSentences} sentences={sentences} />
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <ReviewBlock
            title="泛读记录"
            items={[
              ['主旨', extensiveNotes.gist],
              ['态度', extensiveNotes.attitude],
              ['段落功能', extensiveNotes.paragraphFunction],
              ['中心句', extensiveNotes.centralSentence],
            ]}
          />
          <ReviewBlock
            title="精读记录"
            items={[
              ['主干', intensiveNotes.mainStructure],
              ['词组搭配', intensiveNotes.phraseNotes],
              ['细节证据', intensiveNotes.evidenceNote],
            ]}
          />
        </div>

        <div className="mt-5">
          <h3 className="text-sm font-black text-slate-950">选择过的句子</h3>
          <div className="mt-3 space-y-2">
            {selectedSentences.length > 0 ? (
              selectedSentences.map((sentence) => (
                <p key={sentence.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-600">
                  <span className="font-black text-slate-950">Sentence {sentence.order}: </span>
                  {sentence.text}
                </p>
              ))
            ) : (
              <p className="rounded-lg border border-dashed border-slate-200 p-3 text-sm text-muted-foreground">
                还没有在精读模式里选择句子。
              </p>
            )}
          </div>
        </div>
      </SurfaceCard>

      <div className="grid gap-5">
        <SurfaceCard>
          <div className="flex items-center gap-2">
            <BookOpenCheck className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-black text-slate-950">完成阅读</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            {sourceLabel ? `${sourceLabel} · ` : ''}完成后会写入阅读画像证据，学习中心的阅读值会随练习记录更新。
          </p>
          {completionResult ? (
            <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm font-bold text-emerald-700">
              已记录阅读值 +{completionResult.reading_value}
            </div>
          ) : completeStatus === 'error' ? (
            <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm font-bold text-rose-700">
              完成记录保存失败，请稍后重试。
            </div>
          ) : null}
          <Button
            className="mt-5 w-full"
            disabled={completeStatus === 'saving' || completeStatus === 'completed'}
            onClick={onCompleteReading}
          >
            <CheckCircle2 className="h-4 w-4" />
            {completeStatus === 'saving' ? '正在记录' : completeStatus === 'completed' ? '已完成阅读' : '完成阅读'}
          </Button>
        </SurfaceCard>

        <SurfaceCard>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-success" />
            <h2 className="text-lg font-black text-slate-950">语法点去向</h2>
          </div>
          <div className="mt-4 space-y-3">
            {selectedGrammarOptions.length > 0 ? (
              selectedGrammarOptions.map((option) => (
                <div key={option.id} className="rounded-lg border border-slate-200 p-3">
                  <p className="text-sm font-black text-slate-950">{option.label}</p>
                  <p className="mt-1 text-sm leading-6 text-slate-500">{option.description}</p>
                  <Button className="mt-3 w-full" variant="secondary" onClick={() => onOpenGrammar(option)}>
                    <ExternalLink className="h-4 w-4" />
                    去学这个语法点
                  </Button>
                </div>
              ))
            ) : (
              <p className="text-sm leading-6 text-muted-foreground">
                精读时标记语法卡点后，这里会显示可继续学习的微知识点。
              </p>
            )}
          </div>
        </SurfaceCard>

        <SurfaceCard>
          <h2 className="text-lg font-black text-slate-950">已跳转记录</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {openedGrammarTopics.length > 0 ? (
              openedGrammarTopics.map((topic) => (
                <span key={topic} className="rounded-md bg-primary/10 px-2.5 py-1 text-xs font-bold text-primary">
                  {topic}
                </span>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">还没有从精读句子跳转到语法微知识点。</p>
            )}
          </div>
          <div className="mt-5 flex flex-col gap-3">
            <Button variant="secondary" onClick={() => onOpenWorkspace('extensive')}>
              <Gauge className="h-4 w-4" />
              回到泛读任务
            </Button>
            <Button onClick={() => onOpenWorkspace('intensive')}>
              <Highlighter className="h-4 w-4" />
              继续精读句子
            </Button>
          </div>
        </SurfaceCard>
      </div>
    </section>
  )
}

function GrammarOptionCard({
  option,
  isSelected,
  isSuggested,
  onOpen,
  onToggle,
}: {
  option: ReadingGrammarOption
  isSelected: boolean
  isSuggested: boolean
  onOpen: () => void
  onToggle: () => void
}) {
  return (
    <div className={`rounded-lg border p-4 ${isSelected ? 'border-primary bg-primary/5' : 'border-slate-200 bg-white'}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-black text-slate-950">{option.label}</h3>
            {isSuggested && (
              <span className="rounded-md bg-success/10 px-2 py-0.5 text-xs font-bold text-success">句中可能出现</span>
            )}
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-500">{option.description}</p>
        </div>
        <button
          type="button"
          className={`rounded-lg border px-2 py-1 text-xs font-bold transition ${
            isSelected
              ? 'border-primary bg-primary text-primary-foreground'
              : 'border-slate-200 text-slate-500 hover:border-primary/30 hover:text-primary'
          } focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary`}
          onClick={onToggle}
        >
          {isSelected ? '已标记' : '标记'}
        </button>
      </div>
      <Button className="mt-3 w-full" variant="secondary" onClick={onOpen}>
        <ExternalLink className="h-4 w-4" />
        去学{option.label}
      </Button>
    </div>
  )
}

function ReadingFlowProgress({
  extensiveNotes,
  intensiveNotes,
  openedGrammarTopics,
  selectedGrammarOptions,
  selectedSentences,
  sentences,
}: {
  extensiveNotes: ExtensiveNotes
  intensiveNotes: IntensiveNotes
  openedGrammarTopics: string[]
  selectedGrammarOptions: ReadingGrammarOption[]
  selectedSentences: ReadingSentence[]
  sentences: ReadingSentence[]
}) {
  const steps = [
    { label: '主旨', done: Boolean(extensiveNotes.gist.trim()) },
    { label: '态度', done: Boolean(extensiveNotes.attitude.trim()) },
    { label: '中心句', done: Boolean(extensiveNotes.centralSentence.trim()) },
    { label: '精读句', done: selectedSentences.length > 0 },
    { label: '主干', done: Boolean(intensiveNotes.mainStructure.trim()) },
    { label: '语法卡点', done: selectedGrammarOptions.length > 0 || openedGrammarTopics.length > 0 },
  ]
  const completed = steps.filter((step) => step.done).length
  const percent = steps.length > 0 ? Math.round((completed / steps.length) * 100) : 0
  const sentenceCoverage = sentences.length > 0 ? Math.round((selectedSentences.length / sentences.length) * 100) : 0

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-black text-slate-950">阅读流程进度</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            泛读、精读和语法沉淀的完成状态会集中到这里。
          </p>
        </div>
        <span className="text-2xl font-black text-slate-950">{percent}%</span>
      </div>
      <div className="mt-4 h-3 overflow-hidden rounded-full bg-white">
        <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${percent}%` }} />
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        {steps.map((step) => (
          <div
            key={step.label}
            className={`rounded-lg border px-3 py-2 text-xs font-bold ${
              step.done
                ? 'border-success/20 bg-success/10 text-success'
                : 'border-slate-200 bg-white text-slate-500'
            }`}
          >
            {step.done ? '已完成' : '待补'} · {step.label}
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs font-semibold text-muted-foreground">
        精读覆盖 {selectedSentences.length}/{sentences.length} 句，约 {sentenceCoverage}%。
      </p>
    </div>
  )
}

function ReadingCoveragePanel({
  selectedSentences,
  sentences,
}: {
  selectedSentences: ReadingSentence[]
  sentences: ReadingSentence[]
}) {
  const selectedIds = new Set(selectedSentences.map((sentence) => sentence.id))
  const percent = sentences.length > 0 ? Math.round((selectedSentences.length / sentences.length) * 100) : 0
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-black text-slate-950">正文高亮覆盖</p>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">
        深色块表示已经进入精读的句子位置。
      </p>
      <div className="mt-4 flex h-12 overflow-hidden rounded-xl border border-slate-200 bg-white p-1">
        {sentences.length > 0 ? (
          sentences.map((sentence) => {
            const isSelected = selectedIds.has(sentence.id)
            return (
              <span
                key={sentence.id}
                className={`mx-0.5 flex min-w-3 flex-1 items-center justify-center rounded-lg text-[10px] font-black transition-colors ${
                  isSelected ? 'bg-primary text-primary-foreground' : 'bg-slate-100 text-slate-400'
                }`}
                title={`Sentence ${sentence.order}${isSelected ? '，已精读' : '，未精读'}`}
              >
                {sentence.order}
              </span>
            )
          })
        ) : (
          <span className="flex flex-1 items-center justify-center text-xs font-semibold text-slate-400">
            还没有可分析的句子
          </span>
        )}
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <MetricTile label="覆盖率" value={`${percent}%`} />
        <MetricTile label="已精读" value={`${selectedSentences.length}/${sentences.length}`} />
      </div>
    </div>
  )
}

function getGrammarExerciseTargetFromReadingOption(option: ReadingGrammarOption): ExerciseTarget {
  return {
    type: 'grammar_topic',
    id: mapReadingGrammarOptionToExerciseTargetId(option),
    label: option.grammarTopicTitle,
  }
}

function mapReadingGrammarOptionToExerciseTargetId(option: ReadingGrammarOption) {
  return READING_GRAMMAR_EXERCISE_TARGET_IDS[option.grammarTopicTitle] ?? normalizeReadingExerciseTargetId(option.id)
}

function normalizeReadingExerciseTargetId(value: string) {
  const normalized = value
    .trim()
    .toLocaleLowerCase()
    .replace(/['’]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')

  return normalized || 'unknown-reading-grammar'
}

function EmptyMaterialCard({ onOpenInput }: { onOpenInput: () => void }) {
  return (
    <SurfaceCard className="min-h-[360px]">
      <div className="flex h-full flex-col items-center justify-center text-center">
        <FileText className="h-10 w-10 text-muted-foreground" />
        <h2 className="mt-4 text-lg font-black text-slate-950">先添加一段英文材料</h2>
        <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
          粘贴材料后再进入泛读或精读，工作区会自动分句并生成本地训练提示。
        </p>
        <Button className="mt-5" onClick={onOpenInput}>
          返回材料输入
        </Button>
      </div>
    </SurfaceCard>
  )
}

function MetricTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 truncate text-base font-black text-slate-950">{value}</p>
    </div>
  )
}

function KeywordFrequencyChart({ keywords }: { keywords: ReadingKeywordCandidate[] }) {
  const maxCount = Math.max(...keywords.map((keyword) => keyword.count), 1)
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <h3 className="text-sm font-black text-slate-950">关键词频次</h3>
      <div className="mt-3 space-y-2">
        {keywords.length > 0 ? (
          keywords.map((keyword) => (
            <div key={keyword.word} className="grid grid-cols-[80px_minmax(0,1fr)_28px] items-center gap-2">
              <span className="truncate text-xs font-bold text-slate-600">{keyword.word}</span>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-500"
                  style={{ width: `${(keyword.count / maxCount) * 100}%` }}
                />
              </div>
              <span className="text-right text-xs font-black text-slate-500">{keyword.count}</span>
            </div>
          ))
        ) : (
          <p className="text-sm leading-6 text-slate-500">材料较短，暂未形成关键词频次。</p>
        )}
      </div>
    </div>
  )
}

function SentenceDifficultyHeatmap({
  selectedSentences,
  sentences,
}: {
  selectedSentences: ReadingSentence[]
  sentences: ReadingSentence[]
}) {
  const selectedIds = new Set(selectedSentences.map((sentence) => sentence.id))
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-black text-slate-950">句子难度热力图</h3>
        <span className="text-xs font-bold text-slate-500">按词数估算</span>
      </div>
      <div className="mt-3 grid grid-cols-8 gap-2 sm:grid-cols-10">
        {sentences.length > 0 ? (
          sentences.map((sentence) => {
            const wordCount = countEnglishWords(sentence.text)
            const intensity = Math.min(1, 0.18 + wordCount / 28)
            const isSelected = selectedIds.has(sentence.id)
            return (
              <span
                key={sentence.id}
                className={`flex aspect-square items-center justify-center rounded-[4px] text-[10px] font-black ring-1 ring-inset ${
                  isSelected ? 'text-indigo-950 ring-indigo-500' : 'text-slate-600 ring-slate-200'
                }`}
                style={{ backgroundColor: `rgb(99 102 241 / ${intensity.toFixed(2)})` }}
                title={`Sentence ${sentence.order}: ${wordCount} words${isSelected ? '，已精读' : ''}`}
              >
                {sentence.order}
              </span>
            )
          })
        ) : (
          <span className="col-span-full text-sm leading-6 text-slate-500">添加材料后会显示句子难度。</span>
        )}
      </div>
      <p className="mt-3 text-xs font-semibold text-slate-500">深色代表句子更长；描边代表你在精读中选中过。</p>
    </div>
  )
}

function GrammarTroubleChart({
  openedGrammarTopics,
  selectedGrammarOptions,
}: {
  openedGrammarTopics: string[]
  selectedGrammarOptions: ReadingGrammarOption[]
}) {
  const rows = getGrammarTroubleRows(selectedGrammarOptions, openedGrammarTopics)
  const maxValue = Math.max(...rows.map((row) => row.value), 1)

  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-black text-slate-950">语法卡点分布</h3>
        <span className="text-xs font-bold text-slate-500">标记 + 跳转</span>
      </div>
      <div className="mt-3 space-y-2">
        {rows.length > 0 ? (
          rows.map((row) => (
            <div key={row.label}>
              <div className="flex justify-between gap-3 text-xs font-bold text-slate-500">
                <span className="truncate">{row.label}</span>
                <span>{row.value}</span>
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-success transition-[width] duration-500"
                  style={{ width: `${(row.value / maxValue) * 100}%` }}
                />
              </div>
              <p className="mt-1 text-xs font-semibold text-slate-500">{row.meta}</p>
            </div>
          ))
        ) : (
          <p className="text-sm leading-6 text-slate-500">精读时标记语法卡点后，这里会显示分布。</p>
        )}
      </div>
    </div>
  )
}

function getGrammarTroubleRows(
  selectedGrammarOptions: ReadingGrammarOption[],
  openedGrammarTopics: string[]
) {
  const selectedByTopic = new Map<string, number>()
  selectedGrammarOptions.forEach((option) => {
    selectedByTopic.set(option.grammarTopicTitle, (selectedByTopic.get(option.grammarTopicTitle) ?? 0) + 1)
  })
  const openedByTopic = new Map<string, number>()
  openedGrammarTopics.forEach((topic) => {
    openedByTopic.set(topic, (openedByTopic.get(topic) ?? 0) + 1)
  })
  return uniqueList([...selectedByTopic.keys(), ...openedByTopic.keys()]).map((topic) => {
    const selected = selectedByTopic.get(topic) ?? 0
    const opened = openedByTopic.get(topic) ?? 0
    return {
      label: topic,
      value: selected + opened,
      meta: `标记 ${selected} · 跳转 ${opened}`,
    }
  })
}

function HistoryItem({ item, onRestore }: { item: ReadingMaterialHistoryItem; onRestore: () => void }) {
  const title = item.title?.trim() || '未命名阅读材料'
  const preview = item.text.length > 118 ? `${item.text.slice(0, 118)}…` : item.text

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-black text-slate-950">{title}</p>
          <p className="mt-1 text-xs text-slate-500">{formatHistoryTime(item.updated_at)}</p>
        </div>
        <Button className="shrink-0 px-3 py-2 text-xs" variant="secondary" onClick={onRestore}>
          恢复
        </Button>
      </div>
      <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-500">{preview}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-bold text-slate-600">
          {item.word_count} 词
        </span>
        <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-bold text-slate-600">
          {item.sentence_count} 句
        </span>
        <span className="rounded-md bg-primary/10 px-2 py-1 text-xs font-bold text-primary">
          {READING_LEVEL_LABELS[item.level]}
        </span>
        <span className="rounded-md bg-success/10 px-2 py-1 text-xs font-bold text-success">
          {READING_GOAL_LABELS[item.goal]}
        </span>
      </div>
    </div>
  )
}

function ModeStep({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <p className="text-sm font-black text-slate-950">{title}</p>
      <p className="mt-1 text-sm leading-6 text-slate-500">{text}</p>
    </div>
  )
}

function formatHistoryTime(value: string) {
  const time = new Date(value)
  if (Number.isNaN(time.getTime())) return '时间未知'
  return time.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function ReviewBlock({ title, items }: { title: string; items: Array<[string, string]> }) {
  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <h3 className="text-sm font-black text-slate-950">{title}</h3>
      <div className="mt-3 space-y-3">
        {items.map(([label, value]) => (
          <div key={label}>
            <p className="text-xs font-bold text-slate-500">{label}</p>
            <p className="mt-1 min-h-6 text-sm leading-6 text-slate-700">{value.trim() || '未填写'}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
