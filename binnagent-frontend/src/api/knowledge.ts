import type {
  ParserReviewDecisionResponse,
  ParserReviewItemsResponse,
  ReviewDecisionBody,
} from '@/types/textbookParsing'

interface ParserReviewFilters {
  decision?: string
  severity?: string
  issue_type?: string
  target_type?: string
  parser_run_id?: string
}

export async function fetchKnowledgeParserReviewItems(
  sourceId: string,
  learnerId: string,
  filters: ParserReviewFilters = {},
) {
  const params = compactParams({ learner_id: learnerId, ...filters })
  return requestJson<ParserReviewItemsResponse>(
    `/api/knowledge/sources/${encodeURIComponent(sourceId)}/review-items${params}`,
  )
}

export async function decideKnowledgeParserReviewItem(
  sourceId: string,
  reviewItemId: string,
  learnerId: string,
  action: 'confirm' | 'update' | 'ignore',
  body: ReviewDecisionBody,
) {
  const params = compactParams({ learner_id: learnerId })
  return requestJson<ParserReviewDecisionResponse>(
    `/api/knowledge/sources/${encodeURIComponent(sourceId)}/review-items/${encodeURIComponent(reviewItemId)}/${action}${params}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  )
}

export async function deleteKnowledgeSource(sourceId: string, learnerId: string) {
  const params = compactParams({ learner_id: learnerId })
  return requestJson<{ source_id: string; deleted: boolean; message: string }>(
    `/api/knowledge/sources/${encodeURIComponent(sourceId)}${params}`,
    { method: 'DELETE' },
  )
}

async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit) {
  const response = await fetch(input, init)
  if (!response.ok) {
    const detail = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(detail?.detail ?? `Knowledge request failed: ${response.status}`)
  }
  return await response.json() as T
}

function compactParams(values: object) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    const normalized = typeof value === 'string' ? value.trim() : ''
    if (normalized) params.set(key, normalized)
  }
  const query = params.toString()
  return query ? `?${query}` : ''
}
