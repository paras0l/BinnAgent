import { describe, expect, it } from 'vitest'
import { answerFromAttempt, resultFromAttempt } from './attemptState'

describe('Expression Lab persisted practice state', () => {
  it('restores the submitted answer and feedback after reopening a session', () => {
    const attempt = {
      id: 'attempt-1',
      block_id: 'practice-1',
      question_id: 'question-1',
      answer_json: { value: 'I agree with you.' },
      score: 100,
      is_correct: true,
      feedback_json: { message: '回答正确' },
      next_recommendations: [{ message: '换一个场景继续练习' }],
    }

    expect(answerFromAttempt(attempt)).toBe('I agree with you.')
    expect(resultFromAttempt(attempt)).toMatchObject({
      attempt_id: 'attempt-1',
      score: 100,
      is_correct: true,
      feedback: { message: '回答正确' },
    })
  })
})
