import { useMemo, useState } from 'react'
import {
  ArrowLeft,
  BookOpenCheck,
  CheckCircle2,
  ClipboardList,
  ExternalLink,
  FileText,
  Gauge,
  Highlighter,
  Layers3,
  ListChecks,
  PencilLine,
  SearchCheck,
  Timer,
} from 'lucide-react'
import { FeatureHero } from '@/components/layout/FeatureHero'
import { PageShell } from '@/components/layout/PageShell'
import { WorkspaceTabs, type WorkspaceTab } from '@/components/layout/WorkspaceTabs'
import { Button } from '@/components/ui/Button'
import { FormField } from '@/components/ui/FormField'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
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
  type ReadingSentence,
  type ReadingSentenceHint,
  type ReadingTrainingGoal,
  type ReadingWorkspace,
} from '@/data/readingWorkshop'
import type { Learner } from '@/types'
import { GrammarPage } from '@/pages/GrammarPage'

interface ReadingWorkshopPageProps {
  learner: Learner
  onBack: () => void
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

const SAMPLE_TEXT = `Many students believe that reading faster simply means moving their eyes quickly across a page. However, effective readers do more than race through words. They first notice the title, predict the topic, and look for sentences that show the writer's main point. When a sentence becomes difficult, they slow down, find the main verb, and separate extra information from the core meaning.`

const EMPTY_MATERIAL: ReadingMaterial = {
  title: '',
  text: '',
  level: 'general',
  goal: 'mixed',
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

const SELECT_CLASS = 'w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-primary'

const WORKSPACE_TABS: WorkspaceTab<ReadingWorkspace>[] = [
  { id: 'input', label: '材料输入', description: '标题与原文', icon: <FileText className="h-4 w-4" /> },
  { id: 'extensive', label: '泛读模式', description: '主旨与结构', icon: <Gauge className="h-4 w-4" /> },
  { id: 'intensive', label: '精读模式', description: '句子与语法', icon: <Highlighter className="h-4 w-4" /> },
  { id: 'review', label: '沉淀复盘', description: '本次记录', icon: <ClipboardList className="h-4 w-4" /> },
]

export function ReadingWorkshopPage({ learner, onBack }: ReadingWorkshopPageProps) {
  const [workspace, setWorkspace] = useState<ReadingWorkspace>('input')
  const [material, setMaterial] = useState<ReadingMaterial>(EMPTY_MATERIAL)
  const [extensiveNotes, setExtensiveNotes] = useState<ExtensiveNotes>(EMPTY_EXTENSIVE_NOTES)
  const [intensiveNotes, setIntensiveNotes] = useState<IntensiveNotes>(EMPTY_INTENSIVE_NOTES)
  const [selectedSentenceId, setSelectedSentenceId] = useState<string | null>(null)
  const [visitedSentenceIds, setVisitedSentenceIds] = useState<string[]>([])
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

  const openWorkspace = (nextWorkspace: ReadingWorkspace) => {
    if (nextWorkspace === 'intensive' && sentences[0] && !selectedSentenceId) {
      setSelectedSentenceId(sentences[0].id)
      setVisitedSentenceIds((current) => uniqueList([...current, sentences[0].id]))
    }
    setWorkspace(nextWorkspace)
  }

  const loadSampleMaterial = () => {
    setMaterial({
      title: 'How Effective Readers Work',
      text: SAMPLE_TEXT,
      level: 'general',
      goal: 'mixed',
    })
    setSelectedSentenceId('reading-sentence-1')
    setVisitedSentenceIds(['reading-sentence-1'])
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
          onOpenWorkspace={openWorkspace}
          onTitleChange={(title) => setMaterial((current) => ({ ...current, title }))}
          onTextChange={(text) => setMaterial((current) => ({ ...current, text }))}
          onLevelChange={(level) => setMaterial((current) => ({ ...current, level }))}
          onGoalChange={(goal) => setMaterial((current) => ({ ...current, goal }))}
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
          material={material}
          openedGrammarTopics={openedGrammarTopics}
          selectedGrammarOptions={selectedGrammarOptions}
          selectedSentences={visitedSentences}
          sentences={sentences}
          wordCount={wordCount}
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
  onOpenWorkspace,
  onTextChange,
  onTitleChange,
}: {
  material: ReadingMaterial
  canUseMaterial: boolean
  onGoalChange: (goal: ReadingTrainingGoal) => void
  onLevelChange: (level: ReadingLevel) => void
  onLoadSample: () => void
  onOpenWorkspace: (workspace: ReadingWorkspace) => void
  onTextChange: (text: string) => void
  onTitleChange: (title: string) => void
}) {
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
            description="可选，用来在复盘里识别这次材料。"
            value={material.title}
            onChange={(event) => onTitleChange(event.target.value)}
            placeholder="例如 The Future of Libraries"
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="难度">
              <select
                className={SELECT_CLASS}
                value={material.level}
                onChange={(event) => onLevelChange(event.target.value as ReadingLevel)}
              >
                {(Object.entries(READING_LEVEL_LABELS) as Array<[ReadingLevel, string]>).map(([id, label]) => (
                  <option key={id} value={id}>{label}</option>
                ))}
              </select>
            </FormField>
            <FormField label="训练目标">
              <select
                className={SELECT_CLASS}
                value={material.goal}
                onChange={(event) => onGoalChange(event.target.value as ReadingTrainingGoal)}
              >
                {(Object.entries(READING_GOAL_LABELS) as Array<[ReadingTrainingGoal, string]>).map(([id, label]) => (
                  <option key={id} value={id}>{label}</option>
                ))}
              </select>
            </FormField>
          </div>
        </div>
        <div className="mt-4">
          <FormField
            as="textarea"
            label="英文材料"
            description="粘贴一段英文即可，第一版先在本地工作区处理，不写入后端。"
            value={material.text}
            onChange={(event) => onTextChange(event.target.value)}
            placeholder="Paste an English paragraph here..."
            className="h-64 resize-y"
          />
        </div>
        <div className="mt-5 flex flex-wrap gap-3">
          <Button disabled={!canUseMaterial} onClick={() => onOpenWorkspace(material.goal === 'intensive' ? 'intensive' : 'extensive')}>
            <BookOpenCheck className="h-4 w-4" />
            开始训练
          </Button>
          <Button variant="secondary" onClick={onLoadSample}>
            <PencilLine className="h-4 w-4" />
            填入示例
          </Button>
        </div>
      </SurfaceCard>

      <SurfaceCard className="flex flex-col justify-between">
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
      </SurfaceCard>
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
              value={notes.gist}
              onChange={(event) => onNotesChange('gist', event.target.value)}
              placeholder="这段材料主要讲什么？"
            />
            <FormField
              label="作者态度"
              value={notes.attitude}
              onChange={(event) => onNotesChange('attitude', event.target.value)}
              placeholder="支持 / 反对 / 中立，以及依据"
            />
            <FormField
              label="段落功能"
              value={notes.paragraphFunction}
              onChange={(event) => onNotesChange('paragraphFunction', event.target.value)}
              placeholder="引入问题 / 解释原因 / 举例 / 总结"
            />
            <FormField
              label="中心句"
              value={notes.centralSentence}
              onChange={(event) => onNotesChange('centralSentence', event.target.value)}
              placeholder="哪一句最能概括段落中心？"
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
  if (!canUseMaterial) {
    return <EmptyMaterialCard onOpenInput={() => onOpenWorkspace('input')} />
  }

  return (
    <section className="grid gap-5 xl:grid-cols-[340px_minmax(0,1fr)]">
      <SurfaceCard>
        <div className="flex items-center gap-2">
          <ListChecks className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-black text-slate-950">选择精读句子</h2>
        </div>
        <div className="mt-4 max-h-[620px] space-y-2 overflow-y-auto pr-1">
          {sentences.map((sentence) => (
            <button
              key={sentence.id}
              onClick={() => onSelectSentence(sentence)}
              className={`w-full rounded-lg border p-3 text-left text-sm leading-6 transition ${
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
                  value={notes.mainStructure}
                  onChange={(event) => onNotesChange('mainStructure', event.target.value)}
                  placeholder="S + V + O/C..."
                />
                <FormField
                  as="textarea"
                  label="词组和搭配"
                  value={notes.phraseNotes}
                  onChange={(event) => onNotesChange('phraseNotes', event.target.value)}
                  placeholder="记录值得复用的短语"
                />
                <FormField
                  as="textarea"
                  label="细节证据"
                  value={notes.evidenceNote}
                  onChange={(event) => onNotesChange('evidenceNote', event.target.value)}
                  placeholder="这句话支持了哪一个细节？"
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
      </div>
    </section>
  )
}

function ReviewWorkspace({
  extensiveNotes,
  intensiveNotes,
  material,
  openedGrammarTopics,
  selectedGrammarOptions,
  selectedSentences,
  sentences,
  wordCount,
  onOpenGrammar,
  onOpenWorkspace,
}: {
  extensiveNotes: ExtensiveNotes
  intensiveNotes: IntensiveNotes
  material: ReadingMaterial
  openedGrammarTopics: string[]
  selectedGrammarOptions: ReadingGrammarOption[]
  selectedSentences: ReadingSentence[]
  sentences: ReadingSentence[]
  wordCount: number
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
          className={`rounded-lg border px-2 py-1 text-xs font-bold transition ${
            isSelected
              ? 'border-primary bg-primary text-primary-foreground'
              : 'border-slate-200 text-slate-500 hover:border-primary/30 hover:text-primary'
          }`}
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

function ModeStep({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <p className="text-sm font-black text-slate-950">{title}</p>
      <p className="mt-1 text-sm leading-6 text-slate-500">{text}</p>
    </div>
  )
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
