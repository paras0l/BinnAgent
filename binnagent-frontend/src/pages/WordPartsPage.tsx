import { useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  BarChart3,
  CheckCircle2,
  Eye,
  Layers3,
  LibraryBig,
  Lightbulb,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { FeatureHero } from '@/components/layout/FeatureHero'
import { PageShell } from '@/components/layout/PageShell'
import { WorkspaceTabs, type WorkspaceTab } from '@/components/layout/WorkspaceTabs'
import { ExerciseBlock } from '@/components/exercise/ExerciseBlock'
import { ExerciseAttemptSummary } from '@/components/exercise/ExerciseAttemptSummary'
import { ExerciseLearningSignal } from '@/components/exercise/ExerciseLearningSignal'
import { Button } from '@/components/ui/Button'
import { FilterChip } from '@/components/ui/FilterChip'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import {
  MORPHOLOGY_KIND_LABELS,
  WORD_PART_EXERCISES,
  WORD_PART_KIND_LABELS,
  WORD_PART_LEVEL_LABELS,
  WORD_PARTS,
  formatMorphologyForNote,
  inferWordPartAnalysis,
  searchWordParts,
  type WordPartFilterKind,
  type WordPartFilterLevel,
} from '@/data/wordParts'
import type { WordPart, WordPartProgress, WordPartProgressStatus } from '@/types'
import type { ExerciseTarget } from '@/types/exercises'

interface WordPartsPageProps {
  onBack: () => void
}

type WordPartsWorkspace = 'method' | 'library' | 'practice' | 'progress'

const STORAGE_KEY = 'binnWordPartsProgress:v1'

const WORKSPACE_TABS: WorkspaceTab<WordPartsWorkspace>[] = [
  { id: 'method', label: '方法入门', description: '先学拆词法', icon: <Layers3 className="size-4" /> },
  { id: 'library', label: '词根词缀库', description: '查找和标记', icon: <LibraryBig className="size-4" /> },
  { id: 'practice', label: '拆词练习', description: '提示和答案', icon: <Lightbulb className="size-4" /> },
  { id: 'progress', label: '我的掌握', description: '本地进度', icon: <BarChart3 className="size-4" /> },
]

const KIND_FILTERS: WordPartFilterKind[] = ['all', 'prefix', 'root', 'suffix']
const LEVEL_FILTERS: WordPartFilterLevel[] = ['all', 'common', 'junior', 'cet4', 'cet6']

const STATUS_LABELS: Record<WordPartProgressStatus, string> = {
  new: '新项目',
  learning: '需要再练',
  familiar: '已熟悉',
  mastered: '已掌握',
}

export function WordPartsPage({ onBack }: WordPartsPageProps) {
  const [workspace, setWorkspace] = useState<WordPartsWorkspace>('method')
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState<WordPartFilterKind>('all')
  const [level, setLevel] = useState<WordPartFilterLevel>('all')
  const [selectedPartId, setSelectedPartId] = useState(WORD_PARTS[0]?.id ?? '')
  const [selectedExerciseId, setSelectedExerciseId] = useState(WORD_PART_EXERCISES[0]?.id ?? '')
  const [visibleHintCount, setVisibleHintCount] = useState(1)
  const [isAnswerVisible, setIsAnswerVisible] = useState(false)
  const [progress, setProgress] = useState<Record<string, WordPartProgress>>(() => loadProgress())

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(Object.values(progress)))
  }, [progress])

  const visibleParts = useMemo(() => searchWordParts(query, kind, level), [kind, level, query])
  const selectedPart = WORD_PARTS.find((item) => item.id === selectedPartId) ?? visibleParts[0] ?? WORD_PARTS[0]
  const selectedPartExerciseTarget = useMemo<ExerciseTarget | null>(() => {
    if (!selectedPart) return null
    return {
      type: 'word_part',
      id: selectedPart.id,
      label: selectedPart.form,
    }
  }, [selectedPart])
  const selectedExercise = WORD_PART_EXERCISES.find((item) => item.id === selectedExerciseId) ?? WORD_PART_EXERCISES[0]
  const selectedAnalysis = useMemo(() => inferWordPartAnalysis(selectedExercise?.word), [selectedExercise])
  const progressValues = Object.values(progress)
  const practicedCount = progressValues.filter((item) => item.practicedCount > 0).length
  const familiarCount = WORD_PARTS.filter((item) => {
    const status = progress[item.id]?.status
    return status === 'familiar' || status === 'mastered'
  }).length

  const updatePartStatus = (wordPartId: string, status: WordPartProgressStatus, practiced = false) => {
    setProgress((current) => {
      const existing = current[wordPartId]
      return {
        ...current,
        [wordPartId]: {
          wordPartId,
          status,
          practicedCount: (existing?.practicedCount ?? 0) + (practiced ? 1 : 0),
          lastPracticedAt: new Date().toISOString(),
        },
      }
    })
  }

  const markExercise = (status: WordPartProgressStatus) => {
    for (const wordPartId of selectedExercise.relatedWordPartIds) {
      updatePartStatus(wordPartId, status, true)
    }
  }

  return (
    <PageShell>
      <FeatureHero
        eyebrow="Word Parts"
        title="词根与词缀"
        description="学会拆词，不只是背词。用常见前缀、词根和后缀先猜大意，再回到例句里验证。"
        stats={[
          { label: '内置词根词缀', value: WORD_PARTS.length, tone: 'primary' },
          { label: '练习卡', value: WORD_PART_EXERCISES.length, tone: 'success' },
          { label: '已练项目', value: practicedCount, tone: practicedCount ? 'success' : 'default' },
          { label: '熟悉以上', value: familiarCount, tone: familiarCount ? 'success' : 'warning' },
        ]}
        actions={
          <Button variant="secondary" onClick={onBack}>
            <ArrowLeft className="size-4" />返回探索
          </Button>
        }
      />

      <WorkspaceTabs tabs={WORKSPACE_TABS} activeTab={workspace} onChange={setWorkspace} />

      {workspace === 'method' && (
        <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
          <SurfaceCard>
            <div className="flex items-center gap-2">
              <Layers3 className="size-5 text-primary" />
              <h2 className="text-lg font-black text-slate-950">一个词可以这样拆</h2>
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-3">
              <MethodStep
                title="prefix"
                label="前缀"
                text="常改变方向、否定、程度或位置。"
                example="un- / re- / pre-"
              />
              <MethodStep
                title="root"
                label="词根"
                text="通常承载核心含义。"
                example="port = carry"
              />
              <MethodStep
                title="suffix"
                label="后缀"
                text="常提示词性、抽象意义或性质。"
                example="-ful / -tion"
              />
            </div>

            <div className="mt-5 grid gap-4 lg:grid-cols-2">
              <ExampleBreakdown
                word="unhelpful"
                parts={['un-', 'help', '-ful']}
                lines={['un- = 不', 'help = 帮助', '-ful = 具有……性质的', 'unhelpful = 没有帮助的']}
              />
              <ExampleBreakdown
                word="review"
                parts={['re-', 'view']}
                lines={['re- = again / back', 'view = 看', 'review = 再看一遍，复习或评论']}
              />
            </div>
          </SurfaceCard>

          <SurfaceCard className="flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2">
                <ShieldCheck className="size-5 text-emerald-600" />
                <h2 className="text-lg font-black text-slate-950">方法边界</h2>
              </div>
              <p className="mt-4 text-sm leading-7 text-slate-600">
                词根词缀不是万能公式。遇到新词时，先用词形猜一个大概方向，再用例句、词典和语境确认真实意思。
              </p>
              <div className="mt-5 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                <p className="text-sm font-black text-emerald-900">先猜大意，再用例句验证。</p>
                <p className="mt-2 text-sm leading-6 text-emerald-800/80">
                  这个顺序能帮你减少死记硬背，也能避免把拆词线索当成唯一答案。
                </p>
              </div>
            </div>
            <Button className="mt-5 justify-center" onClick={() => setWorkspace('library')}>
              <LibraryBig className="size-4" />去看词根词缀库
            </Button>
          </SurfaceCard>
        </section>
      )}

      {workspace === 'library' && (
        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <SurfaceCard>
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="relative w-full lg:max-w-sm">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm outline-none transition focus:border-primary"
                  placeholder="搜索 re-、port、prediction..."
                />
              </div>
              <div className="flex gap-2 overflow-x-auto pb-1">
                {KIND_FILTERS.map((item) => (
                  <FilterChip key={item} active={kind === item} onClick={() => setKind(item)}>
                    {WORD_PART_KIND_LABELS[item]}
                  </FilterChip>
                ))}
              </div>
            </div>
            <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
              {LEVEL_FILTERS.map((item) => (
                <FilterChip key={item} active={level === item} onClick={() => setLevel(item)}>
                  {WORD_PART_LEVEL_LABELS[item]}
                </FilterChip>
              ))}
            </div>

            <div className="mt-5 grid gap-3 md:grid-cols-2">
              {visibleParts.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setSelectedPartId(item.id)}
                  className={`rounded-xl border p-4 text-left transition ${
                    selectedPart?.id === item.id
                      ? 'border-primary bg-primary/5 shadow-sm'
                      : 'border-slate-200 bg-white hover:border-primary/30'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <PartKindPill kind={item.kind} />
                        <span className="text-xs font-bold text-slate-400">{WORD_PART_LEVEL_LABELS[item.level]}</span>
                      </div>
                      <h3 className="mt-2 text-2xl font-black text-slate-950">{item.form}</h3>
                    </div>
                    <ProgressBadge status={progress[item.id]?.status ?? 'new'} />
                  </div>
                  <p className="mt-2 text-sm font-semibold text-slate-700">{item.meaning}</p>
                  <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-500">{item.simpleExplanation}</p>
                </button>
              ))}
            </div>
          </SurfaceCard>

          <div className="grid gap-5">
            <SurfaceCard>
              {selectedPart ? (
                <PartDetail
                  part={selectedPart}
                  status={progress[selectedPart.id]?.status ?? 'new'}
                  onStatusChange={(status) => updatePartStatus(selectedPart.id, status)}
                />
              ) : (
                <div className="rounded-xl bg-slate-50 p-4 text-sm font-semibold text-slate-500">
                  暂时没有匹配项。
                </div>
              )}
            </SurfaceCard>

            {selectedPartExerciseTarget ? (
              <>
                <ExerciseLearningSignal
                  target={selectedPartExerciseTarget}
                  messages={{
                    mastered: '已具备掌握证据。',
                    needs_review: '建议继续拆词练习。',
                    unstable: '建议继续拆词练习。',
                  }}
                  titles={{
                    mastered: '掌握证据',
                    needs_review: '继续练习',
                    unstable: '继续练习',
                  }}
                />
                <ExerciseAttemptSummary target={selectedPartExerciseTarget} />
                <ExerciseBlock target={selectedPartExerciseTarget} limit={3} />
              </>
            ) : null}
          </div>
        </section>
      )}

      {workspace === 'practice' && (
        <section className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
          <SurfaceCard>
            <h2 className="text-lg font-black text-slate-950">练习卡</h2>
            <div className="mt-4 grid gap-2">
              {WORD_PART_EXERCISES.map((exercise) => (
                <button
                  key={exercise.id}
                  type="button"
                  onClick={() => {
                    setSelectedExerciseId(exercise.id)
                    setVisibleHintCount(1)
                    setIsAnswerVisible(false)
                  }}
                  className={`rounded-xl border px-4 py-3 text-left transition ${
                    selectedExercise?.id === exercise.id
                      ? 'border-primary bg-primary/5 text-primary'
                      : 'border-slate-200 bg-white text-slate-700 hover:border-primary/30'
                  }`}
                >
                  <span className="block text-sm font-black">{exercise.word}</span>
                  <span className="mt-1 block text-xs font-semibold text-slate-400">{exercise.targetMeaning}</span>
                </button>
              ))}
            </div>
          </SurfaceCard>

          {selectedExercise ? (
            <SurfaceCard>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <p className="text-xs font-black uppercase tracking-wide text-primary">目标词</p>
                  <h2 className="mt-2 text-4xl font-black text-slate-950">{selectedExercise.word}</h2>
                  <p className="mt-2 text-sm font-semibold text-slate-500">大意：{selectedExercise.targetMeaning}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => setVisibleHintCount((count) => Math.min(count + 1, selectedExercise.hints.length))}
                    disabled={visibleHintCount >= selectedExercise.hints.length}
                  >
                    <Lightbulb className="size-4" />显示提示
                  </Button>
                  <Button variant="secondary" onClick={() => setIsAnswerVisible((value) => !value)}>
                    <Eye className="size-4" />{isAnswerVisible ? '隐藏答案' : '显示答案'}
                  </Button>
                </div>
              </div>

              <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
                <div className="space-y-4">
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <p className="text-sm font-black text-slate-800">尝试拆分</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {selectedExercise.breakdown.split(' + ').map((chunk) => (
                        <span key={chunk} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-black text-slate-700">
                          {isAnswerVisible ? chunk : '？'}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-xl border border-indigo-100 bg-indigo-50/70 p-4">
                    <p className="text-sm font-black text-indigo-900">提示</p>
                    <ol className="mt-3 space-y-2">
                      {selectedExercise.hints.slice(0, visibleHintCount).map((hint, index) => (
                        <li key={hint} className="text-sm font-semibold leading-6 text-indigo-900/80">
                          {index + 1}. {hint}
                        </li>
                      ))}
                    </ol>
                  </div>

                  {isAnswerVisible ? (
                    <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                      <p className="text-sm font-black text-emerald-900">答案解释</p>
                      <p className="mt-2 text-sm leading-7 text-emerald-900/80">{selectedExercise.explanation}</p>
                      <p className="mt-3 rounded-lg bg-white/70 px-3 py-2 text-sm font-semibold text-emerald-900">
                        {selectedExercise.example}
                      </p>
                    </div>
                  ) : null}
                </div>

                <div className="space-y-4">
                  {selectedAnalysis ? (
                    <div className="rounded-xl border border-slate-200 bg-white p-4">
                      <p className="text-sm font-black text-slate-900">构词线索</p>
                      <div className="mt-3 grid gap-2">
                        {selectedAnalysis.parts.map((item) => (
                          <div key={`${item.form}-${item.kind}`} className="rounded-lg bg-slate-50 px-3 py-2">
                            <p className="text-sm font-black text-slate-800">
                              {item.form} <span className="text-xs text-slate-400">{MORPHOLOGY_KIND_LABELS[item.kind]}</span>
                            </p>
                            <p className="mt-1 text-xs font-semibold leading-5 text-slate-500">{item.meaning}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <p className="text-sm font-black text-slate-900">标记练习结果</p>
                    <div className="mt-3 grid gap-2">
                      <Button variant="secondary" onClick={() => markExercise('learning')} className="justify-center">
                        <RotateCcw className="size-4" />需要再练
                      </Button>
                      <Button variant="secondary" onClick={() => markExercise('familiar')} className="justify-center">
                        <CheckCircle2 className="size-4" />已经熟悉
                      </Button>
                      <Button onClick={() => markExercise('mastered')} className="justify-center">
                        <Sparkles className="size-4" />已掌握
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </SurfaceCard>
          ) : null}
        </section>
      )}

      {workspace === 'progress' && (
        <section className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
          <SurfaceCard>
            <h2 className="text-lg font-black text-slate-950">掌握概览</h2>
            <div className="mt-4 grid gap-3">
              {(['new', 'learning', 'familiar', 'mastered'] as WordPartProgressStatus[]).map((status) => (
                <ProgressMetric
                  key={status}
                  label={STATUS_LABELS[status]}
                  value={WORD_PARTS.filter((item) => (progress[item.id]?.status ?? 'new') === status).length}
                />
              ))}
            </div>
            <Button
              variant="secondary"
              onClick={() => setProgress({})}
              className="mt-5 w-full justify-center"
            >
              <RotateCcw className="size-4" />重置本地记录
            </Button>
          </SurfaceCard>

          <SurfaceCard>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {WORD_PARTS.map((item) => {
                const itemProgress = progress[item.id]
                return (
                  <div key={item.id} className="rounded-xl border border-slate-200 bg-white p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <PartKindPill kind={item.kind} />
                        <h3 className="mt-2 text-xl font-black text-slate-950">{item.form}</h3>
                      </div>
                      <ProgressBadge status={itemProgress?.status ?? 'new'} />
                    </div>
                    <p className="mt-2 text-sm font-semibold text-slate-600">{item.meaning}</p>
                    <p className="mt-2 text-xs font-semibold text-slate-400">
                      已练 {itemProgress?.practicedCount ?? 0} 次
                    </p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <MiniStatusButton label="再练" onClick={() => updatePartStatus(item.id, 'learning')} />
                      <MiniStatusButton label="熟悉" onClick={() => updatePartStatus(item.id, 'familiar')} />
                      <MiniStatusButton label="掌握" onClick={() => updatePartStatus(item.id, 'mastered')} />
                    </div>
                  </div>
                )
              })}
            </div>
          </SurfaceCard>
        </section>
      )}
    </PageShell>
  )
}

function MethodStep({ title, label, text, example }: { title: string; label: string; text: string; example: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-xs font-black uppercase tracking-wide text-primary">{title}</p>
      <h3 className="mt-2 text-base font-black text-slate-950">{label}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-500">{text}</p>
      <p className="mt-3 rounded-lg bg-white px-3 py-2 text-sm font-black text-slate-700">{example}</p>
    </div>
  )
}

function ExampleBreakdown({ word, parts, lines }: { word: string; parts: string[]; lines: string[] }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="text-lg font-black text-slate-950">{word}</h3>
      <div className="mt-3 flex flex-wrap gap-2">
        {parts.map((partItem) => (
          <span key={partItem} className="rounded-lg bg-primary/10 px-3 py-2 text-sm font-black text-primary">
            {partItem}
          </span>
        ))}
      </div>
      <div className="mt-3 space-y-1">
        {lines.map((line) => (
          <p key={line} className="text-sm leading-6 text-slate-600">{line}</p>
        ))}
      </div>
    </div>
  )
}

function PartDetail({
  part,
  status,
  onStatusChange,
}: {
  part: WordPart
  status: WordPartProgressStatus
  onStatusChange: (status: WordPartProgressStatus) => void
}) {
  const sampleAnalysis = inferWordPartAnalysis(part.examples[0]?.word)
  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <PartKindPill kind={part.kind} />
          <h2 className="mt-2 text-3xl font-black text-slate-950">{part.form}</h2>
          <p className="mt-2 text-sm font-black text-slate-700">{part.meaning}</p>
        </div>
        <ProgressBadge status={status} />
      </div>
      <p className="mt-4 text-sm leading-7 text-slate-600">{part.simpleExplanation}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {part.tags.map((tag) => (
          <span key={tag} className="rounded-md bg-slate-100 px-2 py-1 text-xs font-bold text-slate-500">{tag}</span>
        ))}
      </div>

      <div className="mt-5">
        <p className="text-sm font-black text-slate-900">例词</p>
        <div className="mt-3 grid gap-3">
          {part.examples.map((example) => (
            <div key={example.word} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <p className="text-sm font-black text-slate-900">{example.word}</p>
              <p className="mt-1 text-xs font-semibold text-primary">{example.breakdown}</p>
              <p className="mt-1 text-sm text-slate-500">{example.meaning}</p>
            </div>
          ))}
        </div>
      </div>

      {sampleAnalysis ? (
        <div className="mt-5 rounded-xl border border-indigo-100 bg-indigo-50 p-4">
          <p className="text-sm font-black text-indigo-900">样例拆解</p>
          <pre className="mt-2 whitespace-pre-wrap text-xs font-semibold leading-5 text-indigo-900/80">
            {formatMorphologyForNote(sampleAnalysis)}
          </pre>
        </div>
      ) : null}

      <div className="mt-5 grid gap-2 sm:grid-cols-3">
        <Button variant="secondary" onClick={() => onStatusChange('learning')} className="justify-center">需要再练</Button>
        <Button variant="secondary" onClick={() => onStatusChange('familiar')} className="justify-center">已熟悉</Button>
        <Button onClick={() => onStatusChange('mastered')} className="justify-center">已掌握</Button>
      </div>
    </div>
  )
}

function PartKindPill({ kind }: { kind: WordPart['kind'] }) {
  const className = kind === 'prefix'
    ? 'bg-indigo-50 text-indigo-700'
    : kind === 'root'
      ? 'bg-emerald-50 text-emerald-700'
      : 'bg-amber-50 text-amber-700'
  return (
    <span className={`inline-flex rounded-md px-2 py-1 text-xs font-black ${className}`}>
      {WORD_PART_KIND_LABELS[kind]}
    </span>
  )
}

function ProgressBadge({ status }: { status: WordPartProgressStatus }) {
  const className = status === 'mastered'
    ? 'bg-emerald-100 text-emerald-800'
    : status === 'familiar'
      ? 'bg-sky-100 text-sky-800'
      : status === 'learning'
        ? 'bg-amber-100 text-amber-800'
        : 'bg-slate-100 text-slate-500'
  return <span className={`rounded-md px-2 py-1 text-xs font-black ${className}`}>{STATUS_LABELS[status]}</span>
}

function ProgressMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
      <span className="text-sm font-semibold text-slate-500">{label}</span>
      <strong className="text-xl font-black text-slate-950">{value}</strong>
    </div>
  )
}

function MiniStatusButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-md border border-slate-200 px-2 py-1 text-xs font-bold text-slate-500 transition hover:border-primary/40 hover:text-primary"
    >
      {label}
    </button>
  )
}

function loadProgress(): Record<string, WordPartProgress> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as WordPartProgress[]
    if (!Array.isArray(parsed)) return {}
    return Object.fromEntries(parsed.map((item) => [item.wordPartId, item]))
  } catch {
    return {}
  }
}
