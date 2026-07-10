import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  createExpressionLabSession,
  deleteExpressionLabSession,
  executeExpressionLabAction,
  listExpressionLabSessionPage,
  recordExpressionLabSessionEvent,
  submitExpressionLabAttempt,
} from './expressionLabApi'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('expressionLabApi', () => {
  it('creates a session with the complete learner input contract', async () => {
    const fetchMock = jsonFetch({ session_id: 'session-1', status: 'generating' })
    vi.stubGlobal('fetch', fetchMock)

    const result = await createExpressionLabSession('learner / 1', {
      input_type: 'good_sentence',
      text: 'What matters most is consistency.',
      context: 'exam_writing',
      style: 'formal',
      current_level: 'B1',
      needs_practice: true,
      source_signal_id: 'signal-1',
    })

    expect(result).toEqual({ session_id: 'session-1', status: 'generating' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/learners/learner%20%2F%201/expression-lab/sessions')
    expect(init?.method).toBe('POST')
    expect((init?.headers as Headers).get('Content-Type')).toBe('application/json')
    expect(JSON.parse(String(init?.body))).toEqual({
      input_type: 'good_sentence',
      text: 'What matters most is consistency.',
      context: 'exam_writing',
      style: 'formal',
      current_level: 'B1',
      needs_practice: true,
      source_signal_id: 'signal-1',
    })
  })

  it('normalizes the backend item alias and pending count for recent sessions', async () => {
    const fetchMock = jsonFetch({
      items: [
        {
          session_id: 'session-1',
          status: 'ready',
          input_type: 'zh_intent',
          input_text: '怎么委婉反对？',
          created_at: '2026-07-10T12:00:00Z',
        },
      ],
      pending_count: 2,
    })
    vi.stubGlobal('fetch', fetchMock)

    const page = await listExpressionLabSessionPage('learner-1', 999)

    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/learners/learner-1/expression-lab/sessions?limit=50',
    )
    expect(page.sessions).toHaveLength(1)
    expect(page.pending_count).toBe(2)
  })

  it('submits practice answers to the session-scoped endpoint', async () => {
    const fetchMock = jsonFetch({
      attempt_id: 'attempt-1',
      score: 100,
      is_correct: true,
      feedback: { message: '正确' },
    })
    vi.stubGlobal('fetch', fetchMock)

    await submitExpressionLabAttempt('learner-1', 'session/1', {
      block_id: 'practice-1',
      question_id: 'question-1',
      answer: 'I agree with you.',
    })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(
      '/api/learners/learner-1/expression-lab/sessions/session%2F1/attempts',
    )
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual({
      block_id: 'practice-1',
      question_id: 'question-1',
      answer: 'I agree with you.',
    })
  })

  it('sends only explicit confirmation and client edits when executing an action', async () => {
    const fetchMock = jsonFetch({
      action_id: 'action-1',
      status: 'applied',
      applied_target_type: 'writing_phrase',
      applied_target_id: 'phrase-1',
    })
    vi.stubGlobal('fetch', fetchMock)

    await executeExpressionLabAction('learner-1', 'session-1', 'save / 1', {
      confirmed: true,
      edits: { chinese_meaning: '这个说法可能过于绝对。' },
    })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(
      '/api/learners/learner-1/expression-lab/sessions/session-1/actions/save%20%2F%201',
    )
    expect(JSON.parse(String(init?.body))).toEqual({
      confirmed: true,
      edits: { chinese_meaning: '这个说法可能过于绝对。' },
    })
  })

  it('deletes only the selected temporary session endpoint', async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await deleteExpressionLabSession('learner-1', 'session-1')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/learners/learner-1/expression-lab/sessions/session-1',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('records a client event through the 204-safe request path', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      void input
      void init
      return new Response(null, { status: 204 })
    })
    vi.stubGlobal('fetch', fetchMock)

    await recordExpressionLabSessionEvent(
      'learner-1',
      'session-1',
      'block_viewed',
      { block_id: 'tone-1' },
    )

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(
      '/api/learners/learner-1/expression-lab/sessions/session-1/events',
    )
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual({
      event_type: 'block_viewed',
      payload: { block_id: 'tone-1' },
    })
  })

  it('maps nested FastAPI error codes to stable learner-facing messages', async () => {
    const fetchMock = jsonFetch({
      detail: {
        code: 'confirmation_required',
        message: 'internal confirmation text',
      },
    }, 409)
    vi.stubGlobal('fetch', fetchMock)

    await expect(executeExpressionLabAction(
      'learner-1',
      'session-1',
      'action-1',
      { confirmed: false, edits: {} },
    )).rejects.toMatchObject({
      status: 409,
      message: '这项操作需要你明确确认后才能执行。',
    })
  })
})

function jsonFetch(value: unknown, status = 200) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    void input
    void init
    return new Response(
      JSON.stringify(value),
      { status, headers: { 'Content-Type': 'application/json' } },
    )
  })
}
