export type GroupLearningSourceStatus = 'active' | 'paused' | 'revoked'
export type GroupLearningSourcePlatform = 'feishu' | 'wechat'
export type GroupLearningImportMode = 'silent' | 'triggered_reply'
export type GroupLearningParticipantRole = 'learner' | 'partner' | 'unknown'
export type GroupLearningSignalStatus = 'candidate' | 'accepted' | 'dismissed' | 'deleted'

export interface GroupLearningSource {
  id: string
  learner_id: string
  platform: GroupLearningSourcePlatform
  source_type: string
  display_name: string
  external_group_key: string
  status: GroupLearningSourceStatus
  last_cursor?: string | null
  last_seen_at?: string | null
  last_sync_at?: string | null
  last_import_summary: Record<string, unknown>
  sync_interval_seconds: number
  import_mode: GroupLearningImportMode
  allowed_senders: string[]
  raw_retention_days: number
  auto_generate_recommendations: boolean
  auto_write_candidates: boolean
  auto_apply_high_confidence_tagged_signals: boolean
  confidence_threshold: number
  pending_signal_count: number
  pending_llm_message_count: number
  participant_count: number
  created_at: string
  updated_at: string
}

export interface GroupLearningSourcePayload {
  platform?: GroupLearningSourcePlatform
  display_name: string
  external_group_key: string
  status: GroupLearningSourceStatus
  sync_interval_seconds?: number
  import_mode?: GroupLearningImportMode
  allowed_senders?: string[]
  raw_retention_days: number
  auto_generate_recommendations?: boolean
  auto_write_candidates?: boolean
  auto_apply_high_confidence_tagged_signals?: boolean
  confidence_threshold?: number
}

export interface GroupLearningParticipant {
  id: string
  source_id: string
  external_member_key: string
  display_name: string
  learner_id?: string | null
  role: GroupLearningParticipantRole
  analysis_enabled: boolean
  last_message_at?: string | null
  created_at: string
  updated_at: string
}

export interface GroupLearningParticipantPayload {
  external_member_key: string
  display_name: string
  learner_id?: string | null
  role: GroupLearningParticipantRole
  analysis_enabled: boolean
}

export interface GroupLearningSignal {
  id: string
  message_id: string
  learner_id: string
  signal_type: string
  category: string
  target_type: string
  target_label: string
  confidence: number
  evidence_text: string
  normalized_note?: string | null
  recommendation_reason: string
  status: GroupLearningSignalStatus
  applied_target_type?: string | null
  applied_target_id?: string | null
  metadata: Record<string, unknown>
  source_display_name?: string | null
  source_time?: string | null
  created_at: string
  updated_at: string
}

export interface ImportGroupLearningMessage {
  external_message_id: string
  external_member_key: string
  display_name?: string | null
  content_text: string
  occurred_at: string
  message_type?: string
}

export interface ImportGroupLearningSummary {
  source_id: string
  learner_id: string
  imported_count: number
  duplicate_count: number
  generated_signal_count: number
  ignored_count: number
  participant_count: number
  expression_reuse_count: number
}

export interface GroupLearningSyncNowSummary extends ImportGroupLearningSummary {
  fetched_count: number
  next_cursor?: string | null
  last_sync_at: string
  placeholder: boolean
  help_reply_count?: number
}

export interface GroupLearningSyncMembersSummary {
  source_id: string
  learner_id: string
  fetched_count: number
  upserted_count: number
  participant_count: number
  last_sync_at: string
  placeholder: boolean
}

export interface GroupLearningAnalyzePendingSummary {
  source_id: string
  learner_id: string
  analyzed_message_count: number
  generated_signal_count: number
  skipped_signal_count: number
  remaining_pending_count: number
}

export interface GroupLearningSignalPage {
  items: GroupLearningSignal[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface GroupLearningImportedMessage {
  id: string
  source_id: string
  source_display_name: string
  external_message_id: string
  content_preview?: string | null
  ingestion_status: string
  occurred_at: string
  imported_at: string
  signal_count: number
}

export interface GroupLearningImportedMessagePage {
  items: GroupLearningImportedMessage[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export async function listGroupLearningSources(learnerId: string) {
  return apiJson<GroupLearningSource[]>(`/api/learners/${learnerId}/group-learning/sources`)
}

export async function listGroupLearningImportedMessages(learnerId: string, page = 1, pageSize = 5) {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  return apiJson<GroupLearningImportedMessagePage>(
    `/api/learners/${learnerId}/group-learning/messages?${params.toString()}`,
  )
}

export async function createGroupLearningSource(
  learnerId: string,
  payload: GroupLearningSourcePayload,
) {
  return apiJson<GroupLearningSource>(`/api/learners/${learnerId}/group-learning/sources`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateGroupLearningSource(
  learnerId: string,
  sourceId: string,
  payload: Partial<GroupLearningSourcePayload>,
) {
  return apiJson<GroupLearningSource>(`/api/learners/${learnerId}/group-learning/sources/${sourceId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteGroupLearningSource(learnerId: string, sourceId: string) {
  await apiVoid(`/api/learners/${learnerId}/group-learning/sources/${sourceId}`, { method: 'DELETE' })
}

export async function listGroupLearningParticipants(
  learnerId: string,
  sourceId: string,
  query?: string,
) {
  const params = query?.trim() ? `?q=${encodeURIComponent(query.trim())}` : ''
  return apiJson<GroupLearningParticipant[]>(
    `/api/learners/${learnerId}/group-learning/sources/${sourceId}/participants${params}`,
  )
}

export async function upsertGroupLearningParticipant(
  learnerId: string,
  sourceId: string,
  payload: GroupLearningParticipantPayload,
) {
  return apiJson<GroupLearningParticipant>(
    `/api/learners/${learnerId}/group-learning/sources/${sourceId}/participants`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export async function updateGroupLearningParticipant(
  learnerId: string,
  participantId: string,
  payload: Partial<Omit<GroupLearningParticipantPayload, 'external_member_key'>>,
) {
  return apiJson<GroupLearningParticipant>(
    `/api/learners/${learnerId}/group-learning/participants/${participantId}`,
    { method: 'PATCH', body: JSON.stringify(payload) },
  )
}

export async function cleanupGroupLearningSource(
  learnerId: string,
  sourceId: string,
  mode: 'expired' | 'all_raw_messages',
) {
  return apiJson<{ deleted_raw_message_count: number }>(
    `/api/learners/${learnerId}/group-learning/sources/${sourceId}/cleanup`,
    { method: 'POST', body: JSON.stringify({ mode, keep_signal_evidence: true }) },
  )
}

export async function importGroupLearningMessages(
  sourceId: string,
  messages: ImportGroupLearningMessage[],
) {
  return apiJson<ImportGroupLearningSummary>('/api/group-learning/messages/import', {
    method: 'POST',
    body: JSON.stringify({ source_id: sourceId, messages }),
  })
}

export async function syncGroupLearningSourceNow(learnerId: string, sourceId: string) {
  return apiJson<GroupLearningSyncNowSummary>(
    `/api/learners/${learnerId}/group-learning/sources/${sourceId}/sync-now`,
    { method: 'POST' },
  )
}

export async function syncGroupLearningSourceMembers(learnerId: string, sourceId: string) {
  return apiJson<GroupLearningSyncMembersSummary>(
    `/api/learners/${learnerId}/group-learning/sources/${sourceId}/sync-members`,
    { method: 'POST' },
  )
}

export async function analyzePendingGroupLearningMessages(learnerId: string, sourceId: string, limit = 10) {
  return apiJson<GroupLearningAnalyzePendingSummary>(
    `/api/learners/${learnerId}/group-learning/sources/${sourceId}/analyze-pending?limit=${limit}`,
    { method: 'POST' },
  )
}

export async function listGroupLearningSignals(
  learnerId: string,
  status: 'all' | GroupLearningSignalStatus = 'all',
  query?: string,
  page = 1,
  pageSize = 12,
  category: 'all' | 'expression_gap' | 'grammar' | 'intent' | 'vocabulary' | 'sentence' | 'note' = 'all',
) {
  const params = new URLSearchParams({ status, page: String(page), page_size: String(pageSize), category })
  if (query?.trim()) params.set('q', query.trim())
  return apiJson<GroupLearningSignalPage>(
    `/api/learners/${learnerId}/group-learning/signals?${params.toString()}`,
  )
}

export async function updateGroupLearningSignal(
  learnerId: string,
  signalId: string,
  action: 'accept' | 'dismiss' | 'restore' | 'delete',
) {
  return apiJson<GroupLearningSignal>(
    `/api/learners/${learnerId}/group-learning/signals/${signalId}`,
    { method: 'PATCH', body: JSON.stringify({ action }) },
  )
}

export async function deleteGroupLearningSignal(learnerId: string, signalId: string) {
  await apiVoid(`/api/learners/${learnerId}/group-learning/signals/${signalId}`, {
    method: 'DELETE',
  })
}

async function apiJson<T>(input: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(input, jsonInit(init))
  if (!response.ok) throw new Error(await errorMessage(response))
  return response.json() as Promise<T>
}

async function apiVoid(input: string, init: RequestInit = {}) {
  const response = await fetch(input, jsonInit(init))
  if (!response.ok) throw new Error(await errorMessage(response))
}

function jsonInit(init: RequestInit): RequestInit {
  return {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init.headers,
    },
  }
}

async function errorMessage(response: Response) {
  try {
    const data = await response.json() as { detail?: unknown }
    if (typeof data.detail === 'string') return data.detail
  } catch {
    // Fall through to status text.
  }
  return response.statusText || '请求失败'
}
