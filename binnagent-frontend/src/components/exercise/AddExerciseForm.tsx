import { useState } from 'react'
import { Plus, Save, Sparkles, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { FormField } from '@/components/ui/FormField'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import {
  generateExercisesForTarget,
  saveExerciseItems,
  type GenerateExercisesRequest,
} from '@/services/exerciseRepository'
import type { ExerciseItem, ExerciseTarget } from '@/types/exercises'

interface AddExerciseFormProps {
  target: ExerciseTarget
  learnerId?: string
  className?: string
  context?: GenerateExercisesRequest['context']
}

type ExerciseDraft = ExerciseItem & {
  optionsText: string
  acceptedAnswersText: string
}

export function AddExerciseForm({ target, learnerId, className = '', context }: AddExerciseFormProps) {
  const [drafts, setDrafts] = useState<ExerciseDraft[]>([])
  const [isGenerating, setIsGenerating] = useState(false)
  const [status, setStatus] = useState<string | null>(null)

  const addManualDraft = () => {
    setStatus(null)
    setDrafts((current) => [
      ...current,
      toDraft(createBlankExercise(target)),
    ])
  }

  const generateExercises = async () => {
    if (!learnerId) {
      setStatus('需要登录学习者后才能使用 AI 生成。')
      return
    }
    setIsGenerating(true)
    setStatus(null)
    try {
      const generated = await generateExercisesForTarget(learnerId, {
        target,
        count: 3,
        exerciseTypes: ['single_choice', 'fill_blank'],
        context,
      })
      setDrafts(generated.map(toDraft))
      setStatus(generated.length ? 'AI 已填入练习表单，保存前可以继续编辑。' : 'AI 没有返回可用题目。')
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'AI 生成练习暂时不可用。')
    } finally {
      setIsGenerating(false)
    }
  }

  const updateDraft = (index: number, patch: Partial<ExerciseDraft>) => {
    setDrafts((current) => current.map((draft, draftIndex) => (
      draftIndex === index ? { ...draft, ...patch } : draft
    )))
  }

  const removeDraft = (index: number) => {
    setDrafts((current) => current.filter((_, draftIndex) => draftIndex !== index))
  }

  const saveDrafts = () => {
    const exercises = drafts.map((draft) => fromDraft(draft, target))
    const invalid = exercises.find((exercise) => (
      !exercise.prompt.trim() ||
      !exercise.correctAnswer.trim() ||
      !exercise.explanation.trim()
    ))
    if (invalid) {
      setStatus('请补全题干、答案和解释后再保存。')
      return
    }
    saveExerciseItems(exercises)
    setDrafts([])
    setStatus(`已保存 ${exercises.length} 道练习。`)
  }

  return (
    <SurfaceCard className={className}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="size-5 text-primary" />
            <h2 className="text-lg font-black text-slate-950">添加练习</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            验收对象：<span className="font-black text-slate-700">{target.label}</span>
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button variant="secondary" onClick={addManualDraft}>
            <Plus className="size-4" />
            手动添加
          </Button>
          <Button onClick={() => void generateExercises()} disabled={isGenerating}>
            <Sparkles className="size-4" />
            {isGenerating ? '生成中' : 'AI 生成练习'}
          </Button>
        </div>
      </div>

      {status ? (
        <p className="mt-4 rounded-lg bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
          {status}
        </p>
      ) : null}

      {drafts.length > 0 ? (
        <div className="mt-5 grid gap-4">
          {drafts.map((draft, index) => (
            <div key={draft.id} className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-black text-slate-950">练习 {index + 1}</p>
                <Button variant="ghost" onClick={() => removeDraft(index)} aria-label="删除练习">
                  <Trash2 className="size-4" />
                </Button>
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <label className="block">
                  <span className="text-sm font-medium text-slate-950">题型</span>
                  <select
                    value={draft.type}
                    onChange={(event) => updateDraft(index, { type: event.target.value as ExerciseItem['type'] })}
                    className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-primary"
                  >
                    <option value="single_choice">单选题</option>
                    <option value="fill_blank">填空题</option>
                  </select>
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-slate-950">能力</span>
                  <select
                    value={draft.skill}
                    onChange={(event) => updateDraft(index, { skill: event.target.value as ExerciseItem['skill'] })}
                    className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-primary"
                  >
                    <option value="grammar">语法</option>
                    <option value="vocabulary">词汇</option>
                    <option value="reading">阅读</option>
                  </select>
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-slate-950">难度</span>
                  <select
                    value={draft.difficulty ?? 'easy'}
                    onChange={(event) => updateDraft(index, { difficulty: event.target.value as ExerciseItem['difficulty'] })}
                    className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-primary"
                  >
                    <option value="easy">easy</option>
                    <option value="medium">medium</option>
                    <option value="hard">hard</option>
                  </select>
                </label>
              </div>

              <div className="mt-3 grid gap-3">
                <FormField
                  as="textarea"
                  label="题干"
                  value={draft.prompt}
                  onChange={(event) => updateDraft(index, { prompt: event.target.value })}
                />
                <FormField
                  as="textarea"
                  label="选项"
                  description="单选题每行一个选项；填空题可以留空。"
                  value={draft.optionsText}
                  onChange={(event) => updateDraft(index, { optionsText: event.target.value })}
                />
                <FormField
                  label="正确答案"
                  value={draft.correctAnswer}
                  onChange={(event) => updateDraft(index, { correctAnswer: event.target.value })}
                />
                <FormField
                  as="textarea"
                  label="可接受答案"
                  description="每行一个，可留空。"
                  value={draft.acceptedAnswersText}
                  onChange={(event) => updateDraft(index, { acceptedAnswersText: event.target.value })}
                />
                <FormField
                  as="textarea"
                  label="解释"
                  value={draft.explanation}
                  onChange={(event) => updateDraft(index, { explanation: event.target.value })}
                />
              </div>
            </div>
          ))}
          <div className="flex justify-end">
            <Button onClick={saveDrafts}>
              <Save className="size-4" />
              保存为正式练习
            </Button>
          </div>
        </div>
      ) : null}
    </SurfaceCard>
  )
}

function createBlankExercise(target: ExerciseTarget): ExerciseItem {
  return {
    id: `manual-${target.type}-${target.id}-${Date.now()}`,
    target,
    skill: defaultSkillForTarget(target.type),
    type: 'single_choice',
    prompt: '',
    options: ['', '', '', ''],
    correctAnswer: '',
    acceptedAnswers: [],
    explanation: '',
    difficulty: 'easy',
    source: {
      type: 'manual',
      name: 'manual',
    },
    metadata: {
      targetType: target.type,
      targetId: target.id,
    },
  }
}

function toDraft(exercise: ExerciseItem): ExerciseDraft {
  return {
    ...exercise,
    optionsText: (exercise.options ?? []).join('\n'),
    acceptedAnswersText: (exercise.acceptedAnswers ?? []).join('\n'),
  }
}

function fromDraft(draft: ExerciseDraft, target: ExerciseTarget): ExerciseItem {
  const source = draft.source.type === 'generated'
    ? { type: 'generated' as const, name: 'ai_generated' }
    : draft.source
  const metadata: Record<string, unknown> = {
    ...(draft.metadata ?? {}),
    targetType: target.type,
    targetId: target.id,
  }
  if (source.type === 'generated') {
    metadata.generatedBy = 'ai'
  }
  return {
    ...draft,
    id: draft.id || `${source.type}-${target.type}-${target.id}-${Date.now()}`,
    target,
    options: lines(draft.optionsText),
    acceptedAnswers: lines(draft.acceptedAnswersText),
    source,
    metadata,
  }
}

function lines(value: string) {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

function defaultSkillForTarget(type: ExerciseTarget['type']): ExerciseItem['skill'] {
  if (type === 'grammar_topic') return 'grammar'
  if (type === 'reading_passage') return 'reading'
  return 'vocabulary'
}
