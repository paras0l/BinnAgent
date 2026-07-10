export type ExpressionInputType = 'zh_intent' | 'en_draft' | 'good_sentence' | 'learning_target'

export type ExpressionLabStatus =
  | 'idle'
  | 'generating'
  | 'ready'
  | 'partial'
  | 'error'
  | 'completed'

export type ExpressionBlockType =
  | 'expression_variants'
  | 'tone_spectrum'
  | 'sentence_diff'
  | 'pattern_diagram'
  | 'usage_comparison'
  | 'vocabulary_focus'
  | 'grammar_focus'
  | 'micro_practice'
  | 'transfer_builder'
  | 'sandbox_widget'

export type ExpressionActionType =
  | 'save_writing_phrase'
  | 'save_vocabulary'
  | 'save_grammar_point'
  | 'create_practice'
  | 'copy_expression'
  | 'dismiss_suggestion'
  | 'mark_completed'

export type ExpressionLabEventType = 'block_viewed' | 'source_opened' | 'sandbox_interaction'

export interface ExpressionLabSource {
  type: 'manual' | 'group_learning_signal' | string
  source_id?: string | null
  label?: string | null
  text?: string | null
  occurred_at?: string | null
  confidence?: number | null
  metadata?: Record<string, unknown>
}

export interface ExpressionLabIntent {
  input_type: ExpressionInputType
  text: string
  context?: string | null
  goal?: string | null
  level?: string | null
  include_practice?: boolean
}

export interface ExpressionBlockUi {
  collapsible?: boolean
  emphasis?: 'primary' | 'default' | 'muted' | string
}

export interface ExpressionUiBlock {
  id: string
  type: ExpressionBlockType | string
  title: string
  description?: string | null
  data: Record<string, unknown>
  ui?: ExpressionBlockUi
}

export interface ExpressionSystemAction {
  id: string
  spec_action_id?: string | null
  block_id?: string | null
  type: ExpressionActionType | string
  label: string
  payload: Record<string, unknown>
  editable_fields?: string[]
  requires_confirmation?: boolean
  status?: 'candidate' | 'confirming' | 'saving' | 'saved' | 'failed' | string
  applied_target_type?: string | null
  applied_target_id?: string | null
}

export interface ExpressionUiSpec {
  version: 'expression_ui.v1' | string
  session_id: string
  source: ExpressionLabSource
  intent: ExpressionLabIntent
  layout?: string | null
  blocks: ExpressionUiBlock[]
  suggested_assets?: Array<Record<string, unknown>>
  learning_actions?: ExpressionSystemAction[]
}

export interface ExpressionLabAttempt {
  id?: string
  block_id: string
  question_id: string
  answer?: unknown
  answer_json?: unknown
  score?: number | null
  is_correct?: boolean | null
  feedback?: unknown
  feedback_json?: unknown
  next_recommendations?: Array<Record<string, unknown>>
  attempt_number?: number
  created_at?: string
}

export interface ExpressionLabSessionDetail {
  session_id: string
  status: ExpressionLabStatus
  input_type: ExpressionInputType
  input_text: string
  context?: string | null
  style_goal?: string | null
  level?: string | null
  include_practice?: boolean
  current_level?: string | null
  needs_practice?: boolean
  source: ExpressionLabSource
  ui_spec?: ExpressionUiSpec | null
  actions: ExpressionSystemAction[]
  attempts: ExpressionLabAttempt[]
  evidence: unknown[] | Record<string, unknown>
  diagnostics?: Record<string, unknown> | null
  error_message?: string | null
  created_at: string
  updated_at?: string
  completed_at?: string | null
}

export interface ExpressionLabSessionSummary {
  session_id: string
  status: ExpressionLabStatus
  input_type: ExpressionInputType
  input_text: string
  context?: string | null
  style_goal?: string | null
  source?: ExpressionLabSource | null
  created_at: string
  completed_at?: string | null
}

export interface CreateExpressionLabSessionRequest {
  input_type: ExpressionInputType
  text: string
  context?: string | null
  style?: string | null
  current_level?: string | null
  needs_practice?: boolean
  source_signal_id?: string | null
}

export interface CreateExpressionLabSessionResponse {
  session_id: string
  status: 'generating' | ExpressionLabStatus
}

export interface ExpressionAttemptResult {
  attempt_id?: string
  score: number
  is_correct: boolean
  feedback: unknown
  next_recommendations?: Array<Record<string, unknown>>
}

export interface ExpressionActionResult {
  action_id?: string
  status: string
  applied_target_type?: string | null
  applied_target_id?: string | null
  applied_target?: Record<string, unknown> | null
  detail?: string | null
  payload?: Record<string, unknown>
  action?: ExpressionSystemAction
}

export interface ExpressionLabSessionList {
  sessions: ExpressionLabSessionSummary[]
  pending_count: number
}

export class ExpressionLabApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ExpressionLabApiError'
    this.status = status
  }
}

export async function createExpressionLabSession(
  learnerId: string,
  payload: CreateExpressionLabSessionRequest,
  signal?: AbortSignal,
) {
  return requestJson<CreateExpressionLabSessionResponse>(sessionsUrl(learnerId), {
    method: 'POST',
    body: JSON.stringify(payload),
    signal,
  })
}

export async function listExpressionLabSessions(
  learnerId: string,
  limit = 8,
  signal?: AbortSignal,
): Promise<ExpressionLabSessionSummary[]> {
  return (await listExpressionLabSessionPage(learnerId, limit, signal)).sessions
}

export async function listExpressionLabSessionPage(
  learnerId: string,
  limit = 8,
  signal?: AbortSignal,
): Promise<ExpressionLabSessionList> {
  const response = await requestJson<ExpressionLabSessionSummary[] | { items?: ExpressionLabSessionSummary[]; sessions?: ExpressionLabSessionSummary[]; pending_count?: number }>(
    `${sessionsUrl(learnerId)}?limit=${Math.max(1, Math.min(limit, 50))}`,
    { signal },
  )
  if (Array.isArray(response)) return { sessions: response, pending_count: 0 }
  return {
    sessions: response.sessions ?? response.items ?? [],
    pending_count: response.pending_count ?? 0,
  }
}

export async function getExpressionLabSession(
  learnerId: string,
  sessionId: string,
  signal?: AbortSignal,
) {
  return requestJson<ExpressionLabSessionDetail>(sessionUrl(learnerId, sessionId), { signal })
}

export async function regenerateExpressionLabBlock(
  learnerId: string,
  sessionId: string,
  blockId: string,
  signal?: AbortSignal,
) {
  return requestJson<ExpressionLabSessionDetail>(
    `${sessionUrl(learnerId, sessionId)}/blocks/${encodeURIComponent(blockId)}/regenerate`,
    { method: 'POST', signal },
  )
}

export async function submitExpressionLabAttempt(
  learnerId: string,
  sessionId: string,
  payload: { block_id: string; question_id: string; answer: unknown },
  signal?: AbortSignal,
) {
  return requestJson<ExpressionAttemptResult>(`${sessionUrl(learnerId, sessionId)}/attempts`, {
    method: 'POST',
    body: JSON.stringify(payload),
    signal,
  })
}

export async function executeExpressionLabAction(
  learnerId: string,
  sessionId: string,
  actionId: string,
  payload: { confirmed: boolean; edits?: Record<string, unknown> },
  signal?: AbortSignal,
) {
  return requestJson<ExpressionActionResult>(
    `${sessionUrl(learnerId, sessionId)}/actions/${encodeURIComponent(actionId)}`,
    { method: 'POST', body: JSON.stringify(payload), signal },
  )
}

export async function recordExpressionLabSessionEvent(
  learnerId: string,
  sessionId: string,
  eventType: ExpressionLabEventType,
  payload: Record<string, unknown>,
  signal?: AbortSignal,
) {
  await requestVoid(`${sessionUrl(learnerId, sessionId)}/events`, {
    method: 'POST',
    body: JSON.stringify({ event_type: eventType, payload }),
    signal,
  })
}

export async function completeExpressionLabSession(
  learnerId: string,
  sessionId: string,
  signal?: AbortSignal,
) {
  return requestJson<ExpressionLabSessionDetail>(`${sessionUrl(learnerId, sessionId)}/complete`, {
    method: 'POST',
    signal,
  })
}

export async function deleteExpressionLabSession(
  learnerId: string,
  sessionId: string,
  signal?: AbortSignal,
) {
  await requestVoid(sessionUrl(learnerId, sessionId), { method: 'DELETE', signal })
}

function sessionsUrl(learnerId: string) {
  return `/api/learners/${encodeURIComponent(learnerId)}/expression-lab/sessions`
}

function sessionUrl(learnerId: string, sessionId: string) {
  return `${sessionsUrl(learnerId)}/${encodeURIComponent(sessionId)}`
}

async function requestJson<T>(input: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(input, jsonInit(init))
  if (!response.ok) throw new ExpressionLabApiError(await errorMessage(response), response.status)
  return response.json() as Promise<T>
}

async function requestVoid(input: string, init: RequestInit = {}) {
  const response = await fetch(input, jsonInit(init))
  if (!response.ok) throw new ExpressionLabApiError(await errorMessage(response), response.status)
}

function jsonInit(init: RequestInit): RequestInit {
  const headers = new Headers(init.headers)
  if (init.body !== undefined) headers.set('Content-Type', 'application/json')
  return { ...init, headers }
}

async function errorMessage(response: Response) {
  try {
    const data = await response.json() as { detail?: unknown; message?: unknown }
    if (typeof data.detail === 'string') return data.detail
    if (data.detail && typeof data.detail === 'object' && !Array.isArray(data.detail)) {
      const detail = data.detail as Record<string, unknown>
      const code = typeof detail.code === 'string' ? detail.code : ''
      if (code && EXPRESSION_LAB_ERROR_MESSAGES[code]) return EXPRESSION_LAB_ERROR_MESSAGES[code]
      if (!code && typeof detail.message === 'string') return detail.message
    }
    if (typeof data.message === 'string') return data.message
  } catch {
    // Fall through to the stable learner-facing message.
  }
  if (response.status === 404) return '没有找到这条表达学习记录，可能已被删除。'
  if (response.status === 409) return '当前学习状态暂时不能执行这项操作，请刷新后重试。'
  if (response.status === 422) return '这项操作的内容没有通过校验，请检查后重试。'
  return response.status >= 500 ? '表达实验室暂时不可用，请稍后重试。' : '表达实验室请求失败，请稍后重试。'
}

const EXPRESSION_LAB_ERROR_MESSAGES: Record<string, string> = {
  confirmation_required: '这项操作需要你明确确认后才能执行。',
  action_not_found: '没有找到这项学习操作，请刷新页面后重试。',
  action_in_progress: '这项操作正在处理中，请稍候。',
  invalid_edits: '修改内容没有通过校验，请检查后重试。',
  invalid_action_payload: '这项学习内容不完整，暂时无法保存。',
  unsupported_action: '当前版本暂不支持这项操作。',
  session_not_found: '没有找到这条表达学习记录，可能已被删除。',
  session_completed: '已完成的会话不能重新生成。',
  session_not_ready: '本次内容仍在生成中，暂时不能执行这项操作。',
  session_not_completable: '本次内容仍在处理中，暂时不能完成学习。',
  block_not_found: '没有找到这个学习模块，请刷新页面后重试。',
  block_regeneration_failed: '这个模块暂时无法重新生成，原内容已经保留。',
  question_not_found: '没有找到这道练习，请刷新页面后重试。',
  grading_key_not_found: '这道练习暂时无法评分，请换一道题。',
  practice_generation_failed: '练习暂时生成失败，请稍后重试。',
  source_signal_not_found: '没有找到这条群聊学习线索。',
  unsupported_source_signal: '这类学习线索暂时不能进入表达实验室。',
}
