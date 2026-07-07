import { debugFetch } from '@/shared/api/debugClient'
import type {
  ParserEvidenceResponse,
  ParserReviewBatchDecisionResponse,
  ParserReviewDecisionResponse,
  ParserReviewItemsResponse,
  ParserRunDetailResponse,
  ParserRunsResponse,
  ReviewDecisionBody,
  TextbookParsingReport,
  TextbookSourcesResponse,
} from '@/types/textbookParsing'

interface TextbookSourceFilters {
  status?: string
  quality_status?: string
}

interface ReviewItemFilters {
  decision?: string
  severity?: string
  issue_type?: string
  target_type?: string
  parser_run_id?: string
}

export interface EvidenceQuery {
  target_type?: string
  target_id?: string
  parser_run_id?: string
  issue_type?: string
}

export async function fetchDebugTextbookSources(filters: TextbookSourceFilters = {}) {
  const params = compactParams(filters)
  return requestJson<TextbookSourcesResponse>(`/api/debug/textbook-sources${params}`)
}

export async function fetchDebugTextbookParsingReport(sourceId: string) {
  return requestJson<TextbookParsingReport>(
    `/api/debug/textbook-sources/${encodeURIComponent(sourceId)}/parsing-report`,
  )
}

export async function fetchDebugParserRuns(sourceId: string) {
  return requestJson<ParserRunsResponse>(
    `/api/debug/textbook-sources/${encodeURIComponent(sourceId)}/parser-runs`,
  )
}

export async function fetchDebugParserRunDetail(sourceId: string, parserRunId: string) {
  return requestJson<ParserRunDetailResponse>(
    `/api/debug/textbook-sources/${encodeURIComponent(sourceId)}/parser-runs/${encodeURIComponent(parserRunId)}`,
  )
}

export async function fetchDebugParserReviewItems(
  sourceId: string,
  filters: ReviewItemFilters = {},
) {
  const params = compactParams(filters)
  return requestJson<ParserReviewItemsResponse>(
    `/api/debug/textbook-sources/${encodeURIComponent(sourceId)}/review-items${params}`,
  )
}

export async function decideDebugParserReviewItem(
  sourceId: string,
  reviewItemId: string,
  action: 'confirm' | 'update' | 'ignore',
  body: ReviewDecisionBody,
) {
  return requestJson<ParserReviewDecisionResponse>(
    `/api/debug/textbook-sources/${encodeURIComponent(sourceId)}/review-items/${encodeURIComponent(reviewItemId)}/${action}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  )
}

export async function batchDecideDebugParserReviewItems(
  sourceId: string,
  body: {
    action: 'confirm' | 'ignore'
    review_item_ids: string[]
    review_note?: string
    allow_blocker_ignore?: boolean
  },
) {
  return requestJson<ParserReviewBatchDecisionResponse>(
    `/api/debug/textbook-sources/${encodeURIComponent(sourceId)}/review-items/batch`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  )
}

export async function fetchDebugParserEvidence(sourceId: string, query: EvidenceQuery) {
  const params = compactParams(query)
  return requestJson<ParserEvidenceResponse>(
    `/api/debug/textbook-sources/${encodeURIComponent(sourceId)}/evidence${params}`,
  )
}

async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit) {
  const response = await debugFetch(input, init)
  if (!response.ok) {
    const detail = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(detail?.detail ?? `Debug request failed: ${response.status}`)
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
