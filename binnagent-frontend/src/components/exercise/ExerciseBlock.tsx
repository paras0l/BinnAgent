import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, BookOpenCheck, CheckCircle2, RotateCcw, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import {
  CORE_VOCABULARY_EXERCISE_TARGET,
  EXERCISE_ATTEMPTS_UPDATED_EVENT,
  fetchExerciseSummaryForTarget,
  getExerciseSummaryForTarget,
  getExercisesForTarget,
  recordExerciseAttempt,
  saveExerciseAttempt,
  type ExerciseAttemptSummary,
} from '@/services/exerciseRepository'
import type { ExerciseAttempt, ExerciseItem, ExerciseTarget } from '@/types/exercises'

interface ExerciseBlockProps {
  target: ExerciseTarget
  limit?: number
  className?: string
  learnerId?: string
}

interface ExerciseFeedback {
  result: ExerciseAttempt['result']
  correctAnswer: string
}

export function ExerciseBlock({ target, limit = 3, className = '', learnerId }: ExerciseBlockProps) {
  const scopeKey = `${learnerId ?? 'local'}:${target.type}:${target.id}:${limit}`
  return (
    <ExerciseBlockContent
      key={scopeKey}
      target={target}
      limit={limit}
      className={className}
      learnerId={learnerId}
    />
  )
}

function ExerciseBlockContent({ target, limit = 3, className = '', learnerId }: ExerciseBlockProps) {
  const exactExercises = useMemo(
    () => getExercisesForTarget(target, { limit }),
    [limit, target],
  )
  const fallbackExercises = useMemo(() => {
    if (exactExercises.length > 0 || target.type !== 'vocabulary_item') return []
    return getExercisesForTarget(CORE_VOCABULARY_EXERCISE_TARGET, { limit })
  }, [exactExercises.length, limit, target.type])
  const exercises = exactExercises.length > 0 ? exactExercises : fallbackExercises
  const activeTarget = exactExercises.length > 0 || fallbackExercises.length === 0
    ? target
    : CORE_VOCABULARY_EXERCISE_TARGET
  const isFallback = exactExercises.length === 0 && fallbackExercises.length > 0
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answersByExerciseId, setAnswersByExerciseId] = useState<Record<string, string>>({})
  const [feedbackByExerciseId, setFeedbackByExerciseId] = useState<Record<string, ExerciseFeedback>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [attemptSummary, setAttemptSummary] = useState<ExerciseAttemptSummary>(() =>
    getExerciseSummaryForTarget(activeTarget)
  )

  useEffect(() => {
    let isMounted = true
    const refreshSummary = () => {
      if (learnerId) {
        void fetchExerciseSummaryForTarget(learnerId, activeTarget).then((summary) => {
          if (isMounted) setAttemptSummary(summary)
        })
        return
      }
      setAttemptSummary(getExerciseSummaryForTarget(activeTarget))
    }
    refreshSummary()
    window.addEventListener(EXERCISE_ATTEMPTS_UPDATED_EVENT, refreshSummary)
    window.addEventListener('storage', refreshSummary)
    return () => {
      isMounted = false
      window.removeEventListener(EXERCISE_ATTEMPTS_UPDATED_EVENT, refreshSummary)
      window.removeEventListener('storage', refreshSummary)
    }
  }, [activeTarget, learnerId])

  const currentExercise = exercises[currentIndex]
  const currentAnswer = currentExercise ? answersByExerciseId[currentExercise.id] ?? '' : ''
  const currentFeedback = currentExercise ? feedbackByExerciseId[currentExercise.id] : undefined
  const completedCount = exercises.filter((exercise) => feedbackByExerciseId[exercise.id]).length
  const correctCount = exercises.filter((exercise) => feedbackByExerciseId[exercise.id]?.result === 'correct').length

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

  if (exercises.length === 0) {
    return (
      <SurfaceCard className={className}>
        <ExerciseHeader
          target={target}
          completedCount={0}
          totalCount={0}
          correctCount={0}
          summary={attemptSummary}
        />
        <div className="mt-5">
          <EmptyState
            icon={<BookOpenCheck className="size-5" />}
            title="这个知识点还没有配套练习"
            description={`当前没有匹配“${target.label}”的内置验收题。可以先完成讲解阅读和个人笔记；后续补题后，这里会直接变成知识点验收入口。`}
          />
        </div>
      </SurfaceCard>
    )
  }

  return (
    <SurfaceCard className={className}>
      <ExerciseHeader
        target={activeTarget}
        completedCount={completedCount}
        totalCount={exercises.length}
        correctCount={correctCount}
        summary={attemptSummary}
        fallbackLabel={isFallback ? target.label : undefined}
      />

      {currentExercise ? (
        <div className="mt-5">
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
                <input
                  value={currentAnswer}
                  onChange={(event) => updateAnswer(currentExercise.id, event.target.value)}
                  disabled={Boolean(currentFeedback)}
                  className="mt-2 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-primary disabled:bg-slate-50"
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
              <Button variant="secondary" onClick={restartGroup}>
                回到第一题
              </Button>
            )}
          </div>
        </div>
      ) : null}
    </SurfaceCard>
  )
}

function ExerciseHeader({
  target,
  completedCount,
  totalCount,
  correctCount,
  summary,
  fallbackLabel,
}: {
  target: ExerciseTarget
  completedCount: number
  totalCount: number
  correctCount: number
  summary: ExerciseAttemptSummary
  fallbackLabel?: string
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <div className="flex items-center gap-2">
          <BookOpenCheck className="size-5 text-primary" />
          <h2 className="text-lg font-black text-slate-950">配套练习</h2>
        </div>
        <p className="mt-1 text-sm leading-6 text-slate-500">
          这组题在验收：<span className="font-black text-slate-700">{target.label}</span>
          {fallbackLabel ? `。当前词条“${fallbackLabel}”暂无专属题，先用通用词汇题验收基础用法。` : '。'}
        </p>
        <p className="mt-2 text-xs font-semibold text-slate-500">
          {summary.total > 0
            ? `累计练习 ${summary.total} 次 · 正确率 ${summary.accuracy}% · 最近一次：${resultLabel(summary.lastResult)}`
            : '累计练习 0 次 · 完成一题后会生成学习证据'}
        </p>
      </div>
      {totalCount > 0 ? (
        <div className="grid min-w-36 grid-cols-2 gap-2 text-center text-xs">
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <p className="font-black text-slate-950">{completedCount}/{totalCount}</p>
            <p className="mt-0.5 text-slate-500">已答</p>
          </div>
          <div className="rounded-lg bg-emerald-50 px-3 py-2">
            <p className="font-black text-emerald-700">{correctCount}</p>
            <p className="mt-0.5 text-emerald-700/80">正确</p>
          </div>
        </div>
      ) : null}
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

function resultLabel(result: ExerciseAttemptSummary['lastResult']) {
  if (result === 'correct') return '正确'
  if (result === 'incorrect') return '错误'
  return '暂无'
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
