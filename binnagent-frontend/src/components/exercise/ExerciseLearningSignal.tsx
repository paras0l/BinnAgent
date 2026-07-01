import { useEffect, useState } from 'react'
import { StatusBanner } from '@/components/ui/StatusBanner'
import {
  EXERCISE_ATTEMPTS_UPDATED_EVENT,
  fetchExerciseSummaryForTarget,
  getExerciseSummaryForTarget,
  type ExerciseAttemptSummary,
  type ExerciseLearningStatus,
} from '@/services/exerciseRepository'
import type { ExerciseTarget } from '@/types/exercises'

interface ExerciseLearningSignalProps {
  target: ExerciseTarget
  messages: Partial<Record<ExerciseLearningStatus, string>>
  titles?: Partial<Record<ExerciseLearningStatus, string>>
  learnerId?: string
}

export function ExerciseLearningSignal({
  target,
  messages,
  titles = {},
  learnerId,
}: ExerciseLearningSignalProps) {
  const scopeKey = `${learnerId ?? 'local'}:${target.type}:${target.id}`
  return (
    <ExerciseLearningSignalContent
      key={scopeKey}
      target={target}
      messages={messages}
      titles={titles}
      learnerId={learnerId}
    />
  )
}

function ExerciseLearningSignalContent({ target, messages, titles, learnerId }: ExerciseLearningSignalProps) {
  const [summary, setSummary] = useState<ExerciseAttemptSummary>(() => getExerciseSummaryForTarget(target))

  useEffect(() => {
    let isMounted = true
    const refreshSummary = () => {
      if (learnerId) {
        void fetchExerciseSummaryForTarget(learnerId, target).then((nextSummary) => {
          if (isMounted) setSummary(nextSummary)
        })
        return
      }
      setSummary(getExerciseSummaryForTarget(target))
    }
    refreshSummary()
    window.addEventListener(EXERCISE_ATTEMPTS_UPDATED_EVENT, refreshSummary)
    window.addEventListener('storage', refreshSummary)
    return () => {
      isMounted = false
      window.removeEventListener(EXERCISE_ATTEMPTS_UPDATED_EVENT, refreshSummary)
      window.removeEventListener('storage', refreshSummary)
    }
  }, [target, learnerId])

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
