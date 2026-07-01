import { useEffect, useState } from 'react'
import { ArrowRight, CheckCircle2, RotateCcw, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { recordExerciseAttempt, saveExerciseAttempt } from '@/services/exerciseRepository'
import type { ExerciseAttempt, ExerciseItem } from '@/types/exercises'

export interface ExerciseRendererProgress {
  completedCount: number
  totalCount: number
  correctCount: number
}

interface ExerciseRendererProps {
  exercises: ExerciseItem[]
  learnerId?: string
  className?: string
  onProgressChange?: (progress: ExerciseRendererProgress) => void
  onComplete?: () => void
}

interface ExerciseFeedback {
  result: ExerciseAttempt['result']
  correctAnswer: string
}

export function ExerciseRenderer({
  exercises,
  learnerId,
  className = '',
  onProgressChange,
  onComplete,
}: ExerciseRendererProps) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answersByExerciseId, setAnswersByExerciseId] = useState<Record<string, string>>({})
  const [feedbackByExerciseId, setFeedbackByExerciseId] = useState<Record<string, ExerciseFeedback>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  const currentExercise = exercises[currentIndex]
  const currentAnswer = currentExercise ? answersByExerciseId[currentExercise.id] ?? '' : ''
  const currentFeedback = currentExercise ? feedbackByExerciseId[currentExercise.id] : undefined
  const completedCount = exercises.filter((exercise) => feedbackByExerciseId[exercise.id]).length
  const correctCount = exercises.filter((exercise) => feedbackByExerciseId[exercise.id]?.result === 'correct').length

  useEffect(() => {
    onProgressChange?.({
      completedCount,
      totalCount: exercises.length,
      correctCount,
    })
  }, [completedCount, correctCount, exercises.length, onProgressChange])

  const updateAnswer = (exerciseId: string, answer: string) => {
    setAnswersByExerciseId((current) => ({ ...current, [exerciseId]: answer }))
  }

  const submitAnswer = async () => {
    if (!currentExercise || currentFeedback || !currentAnswer.trim() || isSubmitting) return

    const isCorrect = isExerciseAnswerCorrect(currentExercise, currentAnswer)
    const attempt: ExerciseAttempt = {
      id: `attempt-${Date.now()}-${currentExercise.id}`,
      exerciseId: currentExercise.id,
      target: currentExercise.target,
      answer: currentAnswer.trim(),
      result: isCorrect ? 'correct' : 'incorrect',
      createdAt: new Date().toISOString(),
      should_update_mastery: true,
      should_create_error_pattern: !isCorrect,
      should_create_memory_evidence: true,
      metadata: {
        exercise_source: currentExercise.source,
        exercise_metadata: currentExercise.metadata ?? {},
      },
      sourceContext: {
        source: currentExercise.source.type,
        name: currentExercise.source.name,
        refId: currentExercise.source.refId,
        path: currentExercise.source.path,
      },
    }

    setIsSubmitting(true)
    try {
      if (learnerId) {
        await saveExerciseAttempt(learnerId, attempt)
      } else {
        recordExerciseAttempt(attempt)
      }
      setFeedbackByExerciseId((current) => ({
        ...current,
        [currentExercise.id]: {
          result: attempt.result,
          correctAnswer: currentExercise.correctAnswer,
        },
      }))
    } finally {
      setIsSubmitting(false)
    }
  }

  const resetCurrentAnswer = () => {
    if (!currentExercise) return
    setAnswersByExerciseId((current) => ({ ...current, [currentExercise.id]: '' }))
    setFeedbackByExerciseId((current) => {
      const next = { ...current }
      delete next[currentExercise.id]
      return next
    })
  }

  const goToNext = () => {
    setCurrentIndex((current) => Math.min(current + 1, exercises.length - 1))
  }

  const restartGroup = () => {
    setCurrentIndex(0)
  }

  if (!currentExercise) return null

  const scenario = scenarioFromExercise(currentExercise)

  return (
    <div className={className}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md bg-primary/10 px-2 py-1 text-xs font-bold text-primary">
            {exerciseTypeLabel(currentExercise.type)}
          </span>
          <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-bold text-slate-600">
            {currentIndex + 1} / {exercises.length}
          </span>
        </div>
        <p className="text-xs font-semibold text-slate-500">
          {exerciseSkillLabel(currentExercise.skill)}
        </p>
      </div>

      {scenario ? (
        <div className="mt-4 rounded-lg border border-sky-100 bg-sky-50 px-4 py-3">
          <p className="text-sm font-black text-sky-900">{scenario.name ?? scenario.zh}</p>
          <p className="mt-1 text-xs font-semibold text-sky-700">{scenario.setting ?? scenario.zh}</p>
        </div>
      ) : null}

      <p className="mt-4 whitespace-pre-wrap text-lg font-black leading-8 text-slate-950">
        {currentExercise.prompt}
      </p>

      <div className="mt-4">
        {currentExercise.type === 'single_choice' ? (
          <div className="grid gap-2">
            {(currentExercise.options ?? []).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => updateAnswer(currentExercise.id, option)}
                disabled={Boolean(currentFeedback)}
                className={optionClassName(option, currentAnswer, currentExercise, currentFeedback)}
              >
                {option}
              </button>
            ))}
          </div>
        ) : (
          <label className="block text-sm font-bold text-slate-700">
            我的答案
            <textarea
              value={currentAnswer}
              onChange={(event) => updateAnswer(currentExercise.id, event.target.value)}
              disabled={Boolean(currentFeedback)}
              rows={3}
              className="mt-2 w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm leading-6 outline-none transition focus:border-primary disabled:bg-slate-50"
              placeholder="输入答案"
            />
          </label>
        )}
      </div>

      {currentFeedback ? (
        <div className={feedbackBoxClassName(currentFeedback.result)}>
          <div className="flex items-center gap-2">
            {currentFeedback.result === 'correct' ? (
              <CheckCircle2 className="size-5 text-emerald-600" />
            ) : (
              <XCircle className="size-5 text-rose-600" />
            )}
            <p className="text-sm font-black">
              {currentFeedback.result === 'correct' ? '回答正确' : '回答错误'}
            </p>
          </div>
          {currentFeedback.result === 'incorrect' ? (
            <p className="mt-2 text-sm font-semibold">参考答案：{currentFeedback.correctAnswer}</p>
          ) : null}
          <p className="mt-2 text-sm leading-6">{currentExercise.explanation}</p>
        </div>
      ) : null}

      <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button
            onClick={() => void submitAnswer()}
            disabled={!currentAnswer.trim() || Boolean(currentFeedback) || isSubmitting}
          >
            {isSubmitting ? '提交中' : '提交答案'}
          </Button>
          {currentFeedback ? (
            <Button variant="secondary" onClick={resetCurrentAnswer}>
              <RotateCcw className="size-4" />
              再答一次
            </Button>
          ) : null}
        </div>
        {currentIndex < exercises.length - 1 ? (
          <Button variant="secondary" onClick={goToNext} disabled={!currentFeedback}>
            下一题
            <ArrowRight className="size-4" />
          </Button>
        ) : (
          <Button variant="secondary" onClick={onComplete ?? restartGroup} disabled={Boolean(onComplete) && !currentFeedback}>
            {onComplete ? '完成练习' : '回到第一题'}
          </Button>
        )}
      </div>
    </div>
  )
}

function exerciseTypeLabel(type: ExerciseItem['type']) {
  return type === 'single_choice' ? '单选题' : '填空题'
}

function exerciseSkillLabel(skill: ExerciseItem['skill']) {
  if (skill === 'grammar') return '语法规则验收'
  if (skill === 'reading') return '阅读理解验收'
  return '词义与用法验收'
}

function optionClassName(
  option: string,
  currentAnswer: string,
  exercise: ExerciseItem,
  feedback?: ExerciseFeedback,
) {
  const isSelected = option === currentAnswer
  if (feedback) {
    if (isAcceptedAnswer(exercise, option)) {
      return 'rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-3 text-left text-sm font-semibold text-emerald-800'
    }
    if (isSelected && feedback.result === 'incorrect') {
      return 'rounded-lg border border-rose-300 bg-rose-50 px-3 py-3 text-left text-sm font-semibold text-rose-700'
    }
    return 'rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-left text-sm text-slate-500'
  }
  return isSelected
    ? 'rounded-lg border border-primary bg-primary/10 px-3 py-3 text-left text-sm font-bold text-primary'
    : 'rounded-lg border border-slate-200 bg-white px-3 py-3 text-left text-sm font-semibold text-slate-700 transition hover:border-primary/40 hover:text-primary'
}

function feedbackBoxClassName(result: ExerciseAttempt['result']) {
  return result === 'correct'
    ? 'mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-800'
    : 'mt-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-rose-800'
}

function isExerciseAnswerCorrect(exercise: ExerciseItem, answer: string) {
  return isAcceptedAnswer(exercise, answer)
}

function isAcceptedAnswer(exercise: ExerciseItem, answer: string) {
  const acceptedAnswers = exercise.acceptedAnswers?.length
    ? exercise.acceptedAnswers
    : [exercise.correctAnswer]
  const normalizedAnswer = normalizeAnswer(answer)
  return acceptedAnswers.some((accepted) => normalizeAnswer(accepted) === normalizedAnswer)
}

function normalizeAnswer(value: string) {
  return value.trim().toLocaleLowerCase().replace(/\s+/g, ' ')
}

function scenarioFromExercise(exercise: ExerciseItem) {
  const scenario = exercise.metadata?.scenario
  if (!scenario || typeof scenario !== 'object') return null
  const value = scenario as Record<string, unknown>
  return {
    name: typeof value.name === 'string' ? value.name : undefined,
    setting: typeof value.setting === 'string' ? value.setting : undefined,
    zh: typeof value.zh === 'string' ? value.zh : undefined,
  }
}
