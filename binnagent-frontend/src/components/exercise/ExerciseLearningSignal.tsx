import { useEffect, useState } from 'react'
import { StatusBanner } from '@/components/ui/StatusBanner'
import {
  EXERCISE_ATTEMPTS_UPDATED_EVENT,
  getExerciseSummaryForTarget,
  type ExerciseAttemptSummary,
  type ExerciseLearningStatus,
} from '@/services/exerciseRepository'
import type { ExerciseTarget } from '@/types/exercises'

interface ExerciseLearningSignalProps {
  target: ExerciseTarget
  messages: Partial<Record<ExerciseLearningStatus, string>>
  titles?: Partial<Record<ExerciseLearningStatus, string>>
}

export function ExerciseLearningSignal({ target, messages, titles = {} }: ExerciseLearningSignalProps) {
  const scopeKey = `${target.type}:${target.id}`
  return <ExerciseLearningSignalContent key={scopeKey} target={target} messages={messages} titles={titles} />
}

function ExerciseLearningSignalContent({ target, messages, titles }: ExerciseLearningSignalProps) {
  const [summary, setSummary] = useState<ExerciseAttemptSummary>(() => getExerciseSummaryForTarget(target))

  useEffect(() => {
    const refreshSummary = () => setSummary(getExerciseSummaryForTarget(target))
    window.addEventListener(EXERCISE_ATTEMPTS_UPDATED_EVENT, refreshSummary)
    window.addEventListener('storage', refreshSummary)
    return () => {
      window.removeEventListener(EXERCISE_ATTEMPTS_UPDATED_EVENT, refreshSummary)
      window.removeEventListener('storage', refreshSummary)
    }
  }, [target])

  const message = messages[summary.learningStatus]
  if (!message) return null

  return (
    <StatusBanner title={titles?.[summary.learningStatus]} tone={signalTone(summary.learningStatus)}>
      {message}
    </StatusBanner>
  )
}

function signalTone(status: ExerciseLearningStatus) {
  if (status === 'mastered') return 'success'
  if (status === 'not_started') return 'info'
  return 'warning'
}
