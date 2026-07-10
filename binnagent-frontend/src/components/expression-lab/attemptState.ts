import type {
  ExpressionAttemptResult,
  ExpressionLabAttempt,
} from '@/services/expressionLabApi'
import { displayValue } from './blockData'

export function answerFromAttempt(attempt?: ExpressionLabAttempt) {
  if (!attempt) return ''
  const answer = attempt.answer_json ?? attempt.answer
  if (answer && typeof answer === 'object' && !Array.isArray(answer)) {
    const record = answer as Record<string, unknown>
    return displayValue(record.value ?? record.answer ?? record.text)
  }
  return displayValue(answer)
}

export function resultFromAttempt(
  attempt?: ExpressionLabAttempt,
): ExpressionAttemptResult | null {
  if (!attempt || attempt.score === null || attempt.score === undefined) return null
  return {
    attempt_id: attempt.id,
    score: attempt.score,
    is_correct: Boolean(attempt.is_correct),
    feedback: attempt.feedback_json ?? attempt.feedback ?? '',
    next_recommendations: attempt.next_recommendations ?? [],
  }
}
