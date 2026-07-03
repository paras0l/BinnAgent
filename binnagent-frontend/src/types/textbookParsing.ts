export interface TextbookQualityScore {
  overall_score?: number | null
  structure_score?: number | null
  vocabulary_score?: number | null
  rag_score?: number | null
  provenance_score?: number | null
  status?: string | null
  blocking_reasons?: string[]
  warnings?: string[]
}

export interface TextbookSourceDebugSummary {
  source_id: string
  id?: string
  title: string
  name?: string
  filename?: string | null
  status: string
  quality_status?: string | null
  overall_score?: number | null
  parser_status?: string | null
  latest_parser_run_id?: string | null
  latest_parser_version?: string | null
  pending_review_count: number
  pending_blocker_count: number
  review_warning_count: number
  blocking_reasons: string[]
  created_at?: string | null
  updated_at?: string | null
}

export type ParserQualityMetricGroupName =
  | 'intake'
  | 'structure'
  | 'vocabulary'
  | 'knowledge'
  | 'rag'

export type ParserQualityMetricGroups = Record<ParserQualityMetricGroupName, Record<string, unknown>>

export interface ParserRunSummary {
  parser_run_id: string
  parser_id: string
  parser_version: string
  status: string
  started_at?: string | null
  completed_at?: string | null
  duration_ms?: number | null
  quality_status?: string | null
  overall_score?: number | null
  pending_review_count: number
  error_message?: string | null
}

export interface ParserRunDetail extends ParserRunSummary {
  source_id: string
  parser_profile_id?: string | null
  book_manifest_id?: string | null
  pdf_sha256?: string | null
  input_hash?: string | null
  quality_report?: Record<string, unknown> | null
  quality_score?: TextbookQualityScore | null
  artifact_refs?: Record<string, unknown>
  created_at?: string | null
  updated_at?: string | null
}

export interface ParserReviewItem {
  id: string
  source_id?: string
  parser_run_id?: string | null
  issue_type: string
  severity: string
  decision: string
  target_type: string
  target_id?: string | null
  evidence_snapshot: Record<string, unknown>
  suggested_fix: Record<string, unknown>
  review_note?: string | null
  reviewed_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface ParserEvidenceItem {
  target_type: string
  target_id?: string | null
  parser_run_id?: string | null
  origin?: string | null
  source_page?: string | null
  pdf_page?: string | number | null
  raw_line?: string | null
  raw_text_excerpt?: string | null
  raw_text_span?: unknown
  confidence?: number | null
  warnings: string[]
  schema_version?: string | null
  review_item_ids: string[]
  issue_types: string[]
}

export interface TextbookParsingReport {
  source: TextbookSourceDebugSummary
  latest_parser_run?: ParserRunSummary | null
  quality_score?: TextbookQualityScore | null
  quality_report?: Record<string, unknown> | null
  quality_metrics_by_group: ParserQualityMetricGroups
  blocking_reasons: string[]
  warnings: string[]
  pending_review_count: number
  pending_blocker_count: number
  review_warning_count: number
  review_summary_by_issue_type: Record<string, number>
  review_summary_by_severity: Record<string, number>
  parser_artifacts: Record<string, unknown>
  evidence_coverage: Record<string, unknown>
}

export interface TextbookSourcesResponse {
  sources: TextbookSourceDebugSummary[]
  total: number
  limit: number
  offset: number
}

export interface ParserRunsResponse {
  source: TextbookSourceDebugSummary
  parser_runs: ParserRunSummary[]
  limit: number
  offset: number
}

export interface ParserRunDetailResponse {
  source: TextbookSourceDebugSummary
  parser_run: ParserRunDetail
  quality_report?: Record<string, unknown> | null
  quality_score?: TextbookQualityScore | null
  artifact_refs?: Record<string, unknown>
  error_message?: string | null
  review_items: ParserReviewItem[]
  review_summary_by_issue_type: Record<string, number>
  review_summary_by_severity: Record<string, number>
}

export interface ParserReviewItemsResponse {
  source: TextbookSourceDebugSummary
  source_quality_summary: TextbookSourceDebugSummary
  summary: {
    pending_review_count: number
    pending_blocker_count: number
    review_warning_count: number
  }
  items: ParserReviewItem[]
}

export interface ParserReviewDecisionResponse {
  source: TextbookSourceDebugSummary
  source_quality_summary: TextbookSourceDebugSummary
  summary: ParserReviewItemsResponse['summary']
  item: ParserReviewItem
}

export interface ParserEvidenceResponse {
  source_id: string
  query: {
    target_type?: string | null
    target_id?: string | null
    parser_run_id?: string | null
    issue_type?: string | null
  }
  evidence: ParserEvidenceItem[]
  warnings: string[]
  limit: number
  excerpt_limit: number
}

export interface ReviewDecisionBody {
  patch?: Record<string, unknown>
  review_note?: string
  allow_blocker_ignore?: boolean
}
