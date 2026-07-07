import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  ArrowLeft,
  BookOpenCheck,
  CheckCircle2,
  Clock3,
  Database,
  Eye,
  FileWarning,
  History,
  ListFilter,
  Pencil,
  RefreshCw,
  Search,
  ShieldAlert,
  XCircle,
} from 'lucide-react'
import {
  batchDecideDebugParserReviewItems,
  decideDebugParserReviewItem,
  fetchDebugParserEvidence,
  fetchDebugParserReviewItems,
  fetchDebugParserRunDetail,
  fetchDebugParserRuns,
  fetchDebugTextbookParsingReport,
  fetchDebugTextbookSources,
  type EvidenceQuery,
} from '@/api/debug'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { StatusBanner } from '@/components/ui/StatusBanner'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import type {
  ParserEvidenceResponse,
  ParserQualityMetricGroupName,
  ParserReviewItem,
  ParserReviewItemsResponse,
  ParserRunDetailResponse,
  ParserRunsResponse,
  TextbookParsingReport,
  TextbookSourceDebugSummary,
} from '@/types/textbookParsing'

interface TextbookParsingPageProps {
  navigate: (path: string) => void
}

interface TextbookRouteState {
  sourceId: string | null
  parserRunId: string | null
}

const METRIC_TABS: Array<{ id: ParserQualityMetricGroupName; label: string }> = [
  { id: 'intake', label: 'Intake' },
  { id: 'structure', label: 'Structure' },
  { id: 'vocabulary', label: 'Vocabulary' },
  { id: 'knowledge', label: 'Knowledge' },
  { id: 'rag', label: 'RAG' },
]

const TARGET_TYPES = ['knowledge_point', 'curriculum_node', 'exercise_question', 'knowledge_chunk']

export function TextbookParsingPage({ navigate }: TextbookParsingPageProps) {
  const [route, setRoute] = useState<TextbookRouteState>(() => readTextbookRoute())
  const [sources, setSources] = useState<TextbookSourceDebugSummary[]>([])
  const [statusFilter, setStatusFilter] = useState('')
  const [qualityFilter, setQualityFilter] = useState('')
  const [isSourcesLoading, setIsSourcesLoading] = useState(true)
  const [sourcesError, setSourcesError] = useState<string | null>(null)

  const go = useCallback((path: string) => {
    navigate(path)
    setRoute(readTextbookRoute())
  }, [navigate])

  const loadSources = useCallback(async () => {
    setIsSourcesLoading(true)
    setSourcesError(null)
    try {
      const data = await fetchDebugTextbookSources({
        status: statusFilter,
        quality_status: qualityFilter,
      })
      setSources(data.sources)
    } catch (error) {
      setSourcesError(error instanceof Error ? error.message : 'Textbook sources unavailable')
    } finally {
      setIsSourcesLoading(false)
    }
  }, [qualityFilter, statusFilter])

  useEffect(() => {
    const handlePopState = () => setRoute(readTextbookRoute())
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadSources(), 0)
    return () => window.clearTimeout(timer)
  }, [loadSources])

  if (!route.sourceId) {
    return (
      <TextbookSourcesView
        sources={sources}
        statusFilter={statusFilter}
        qualityFilter={qualityFilter}
        isLoading={isSourcesLoading}
        error={sourcesError}
        onStatusFilterChange={setStatusFilter}
        onQualityFilterChange={setQualityFilter}
        onRefresh={() => void loadSources()}
        onOpenSource={(sourceId) => go(`/dev/textbooks/${encodeURIComponent(sourceId)}`)}
      />
    )
  }

  return (
    <TextbookParsingDetailView
      sourceId={route.sourceId}
      parserRunId={route.parserRunId}
      go={go}
    />
  )
}

function TextbookSourcesView({
  sources,
  statusFilter,
  qualityFilter,
  isLoading,
  error,
  onStatusFilterChange,
  onQualityFilterChange,
  onRefresh,
  onOpenSource,
}: {
  sources: TextbookSourceDebugSummary[]
  statusFilter: string
  qualityFilter: string
  isLoading: boolean
  error: string | null
  onStatusFilterChange: (value: string) => void
  onQualityFilterChange: (value: string) => void
  onRefresh: () => void
  onOpenSource: (sourceId: string) => void
}) {
  if (isLoading && sources.length === 0) {
    return <LoadingState title="正在读取 Textbook Sources" description="正在请求教材解析治理摘要..." />
  }
  if (error) {
    return (
      <ErrorState
        title="Textbook Sources 不可用"
        description={error}
        action={<Button variant="secondary" onClick={onRefresh}><RefreshCw className="size-4" />重试</Button>}
      />
    )
  }

  return (
    <section className="space-y-4">
      <SurfaceCard>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-start gap-3">
            <BookOpenCheck className="mt-1 size-5 text-cyan-500" />
            <div>
              <h2 className="text-lg font-black text-slate-950">Textbook Sources</h2>
              <p className="mt-1 text-sm text-slate-500">{sources.length} sources</p>
            </div>
          </div>
          <div className="grid gap-2 sm:grid-cols-[160px_180px_auto]">
            <FilterSelect
              icon={<ListFilter className="size-4" />}
              value={statusFilter}
              onChange={onStatusFilterChange}
              options={['published', 'review_required', 'partial_indexed', 'blocked', 'failed']}
              placeholder="status"
            />
            <FilterSelect
              icon={<ShieldAlert className="size-4" />}
              value={qualityFilter}
              onChange={onQualityFilterChange}
              options={['published', 'review_required', 'partial_indexed', 'blocked', 'failed']}
              placeholder="quality"
            />
            <Button variant="secondary" onClick={onRefresh}>
              <RefreshCw className="size-4" />
              Refresh
            </Button>
          </div>
        </div>
      </SurfaceCard>

      {sources.length ? (
        <SurfaceCard className="overflow-hidden p-0">
          <div className="overflow-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-black">Source</th>
                  <th className="px-4 py-3 font-black">Status</th>
                  <th className="px-4 py-3 font-black">Quality</th>
                  <th className="px-4 py-3 font-black">Score</th>
                  <th className="px-4 py-3 font-black">Latest Run</th>
                  <th className="px-4 py-3 font-black">Review</th>
                  <th className="px-4 py-3 font-black">Updated</th>
                  <th className="px-4 py-3 font-black">Open</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {sources.map((source) => (
                  <tr key={source.source_id} className="align-top">
                    <td className="max-w-sm px-4 py-3">
                      <p className="font-bold text-slate-950">{source.title}</p>
                      <p className="mt-1 break-all font-mono text-xs text-slate-500">{source.source_id}</p>
                    </td>
                    <td className="px-4 py-3"><StatusPill value={source.status} /></td>
                    <td className="px-4 py-3"><QualityPill value={source.quality_status ?? source.status} /></td>
                    <td className="px-4 py-3 font-mono text-xs font-black text-slate-950">
                      {formatScore(source.overall_score)}
                    </td>
                    <td className="max-w-xs px-4 py-3">
                      <p className="font-mono text-xs text-slate-700">{source.latest_parser_version ?? '-'}</p>
                      <p className="mt-1 break-all font-mono text-xs text-slate-400">{source.latest_parser_run_id ?? '-'}</p>
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      <ReviewCounts source={source} />
                    </td>
                    <td className="px-4 py-3 text-slate-600">{formatDate(source.updated_at)}</td>
                    <td className="px-4 py-3">
                      <Button variant="secondary" onClick={() => onOpenSource(source.source_id)}>
                        <Eye className="size-4" />
                        Open
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SurfaceCard>
      ) : (
        <EmptyState
          icon={<BookOpenCheck className="size-5" />}
          title="No textbook sources"
          description="当前过滤条件下没有教材 source。"
        />
      )}
    </section>
  )
}

function TextbookParsingDetailView({
  sourceId,
  parserRunId,
  go,
}: {
  sourceId: string
  parserRunId: string | null
  go: (path: string) => void
}) {
  const [report, setReport] = useState<TextbookParsingReport | null>(null)
  const [runs, setRuns] = useState<ParserRunsResponse | null>(null)
  const [runDetail, setRunDetail] = useState<ParserRunDetailResponse | null>(null)
  const [review, setReview] = useState<ParserReviewItemsResponse | null>(null)
  const [metricTab, setMetricTab] = useState<ParserQualityMetricGroupName>('intake')
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null)
  const [selectedBatchReviewIds, setSelectedBatchReviewIds] = useState<string[]>([])
  const [reviewPatch, setReviewPatch] = useState('{}')
  const [reviewNote, setReviewNote] = useState('')
  const [allowBlockerIgnore, setAllowBlockerIgnore] = useState(false)
  const [isReviewSaving, setIsReviewSaving] = useState(false)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [evidenceQuery, setEvidenceQuery] = useState<EvidenceQuery>({
    target_type: 'knowledge_point',
    target_id: '',
    parser_run_id: '',
    issue_type: '',
  })
  const [evidence, setEvidence] = useState<ParserEvidenceResponse | null>(null)
  const [isEvidenceLoading, setIsEvidenceLoading] = useState(false)
  const [evidenceError, setEvidenceError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadDetail = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [nextReport, nextRuns, nextReview] = await Promise.all([
        fetchDebugTextbookParsingReport(sourceId),
        fetchDebugParserRuns(sourceId),
        fetchDebugParserReviewItems(sourceId, { decision: 'pending' }),
      ])
      setReport(nextReport)
      setRuns(nextRuns)
      setReview(nextReview)
      setSelectedBatchReviewIds((current) => current.filter((itemId) => nextReview.items.some((item) => item.id === itemId)))
      setSelectedReviewId((current) => {
        if (current && nextReview.items.some((item) => item.id === current)) return current
        return nextReview.items[0]?.id ?? null
      })
      if (parserRunId) {
        setRunDetail(await fetchDebugParserRunDetail(sourceId, parserRunId))
      } else {
        setRunDetail(null)
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Textbook parsing report unavailable')
    } finally {
      setIsLoading(false)
    }
  }, [parserRunId, sourceId])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadDetail(), 0)
    return () => window.clearTimeout(timer)
  }, [loadDetail])

  const selectedReviewItem = useMemo(() => {
    const items = review?.items ?? []
    return items.find((item) => item.id === selectedReviewId) ?? items[0] ?? null
  }, [review?.items, selectedReviewId])

  const loadEvidence = useCallback(async (query: EvidenceQuery = evidenceQuery) => {
    setIsEvidenceLoading(true)
    setEvidenceError(null)
    try {
      setEvidence(await fetchDebugParserEvidence(sourceId, query))
    } catch (loadError) {
      setEvidenceError(loadError instanceof Error ? loadError.message : 'Parser evidence unavailable')
    } finally {
      setIsEvidenceLoading(false)
    }
  }, [evidenceQuery, sourceId])

  const handleSelectReviewItem = (itemId: string) => {
    const nextItem = review?.items.find((item) => item.id === itemId) ?? null
    setSelectedReviewId(itemId)
    setReviewPatch('{}')
    setReviewNote(nextItem?.review_note ?? '')
    setAllowBlockerIgnore(false)
    setReviewError(null)
  }

  const handleReviewAction = async (action: 'confirm' | 'update' | 'ignore') => {
    if (!selectedReviewItem) return
    setIsReviewSaving(true)
    setReviewError(null)
    try {
      const body = {
        review_note: reviewNote.trim() || undefined,
        allow_blocker_ignore: allowBlockerIgnore,
        patch: action === 'update' ? parsePatch(reviewPatch) : undefined,
      }
      await decideDebugParserReviewItem(sourceId, selectedReviewItem.id, action, body)
      await loadDetail()
    } catch (saveError) {
      setReviewError(saveError instanceof Error ? saveError.message : 'Review action failed')
    } finally {
      setIsReviewSaving(false)
    }
  }

  const handleBatchReviewAction = async (action: 'confirm' | 'ignore') => {
    if (!selectedBatchReviewIds.length) return
    setIsReviewSaving(true)
    setReviewError(null)
    try {
      await batchDecideDebugParserReviewItems(sourceId, {
        action,
        review_item_ids: selectedBatchReviewIds,
        review_note: reviewNote.trim() || undefined,
        allow_blocker_ignore: allowBlockerIgnore,
      })
      setSelectedBatchReviewIds([])
      await loadDetail()
    } catch (saveError) {
      setReviewError(saveError instanceof Error ? saveError.message : 'Batch review action failed')
    } finally {
      setIsReviewSaving(false)
    }
  }

  const jumpToEvidence = async (item: ParserReviewItem) => {
    const nextQuery = item.target_id
      ? { target_type: item.target_type, target_id: item.target_id, parser_run_id: '', issue_type: '' }
      : { target_type: '', target_id: '', parser_run_id: '', issue_type: item.issue_type }
    setEvidenceQuery(nextQuery)
    await loadEvidence(nextQuery)
  }

  if (isLoading && !report) {
    return <LoadingState title="正在读取 Parsing Report" description="正在聚合 ParserRun、QualityReport 和 Review Queue..." />
  }
  if (error || !report) {
    return (
      <ErrorState
        title="Parsing Report 不可用"
        description={error ?? 'Textbook parsing report missing'}
        action={<Button variant="secondary" onClick={() => void loadDetail()}><RefreshCw className="size-4" />重试</Button>}
      />
    )
  }

  return (
    <section className="space-y-4">
      <SurfaceCard>
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-start gap-3">
            <BookOpenCheck className="mt-1 size-5 text-cyan-500" />
            <div>
              <p className="text-xs font-black uppercase text-slate-500">Parsing Report</p>
              <h2 className="mt-1 text-xl font-black text-slate-950">{report.source.title}</h2>
              <p className="mt-1 break-all font-mono text-xs text-slate-500">{sourceId}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => go('/dev/textbooks')}>
              <ArrowLeft className="size-4" />
              Sources
            </Button>
            <Button variant="secondary" onClick={() => void loadDetail()}>
              <RefreshCw className="size-4" />
              Refresh
            </Button>
          </div>
        </div>
      </SurfaceCard>

      <section className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <SourceSummaryCard source={report.source} />
        <QualityScoreCard report={report} />
      </section>

      <SurfaceCard>
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="size-5 text-cyan-500" />
            <h3 className="text-base font-black text-slate-950">Quality Metrics</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {METRIC_TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setMetricTab(tab.id)}
                className={`rounded-lg px-3 py-2 text-sm font-black transition ${
                  metricTab === tab.id
                    ? 'bg-slate-950 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
        <MetricGrid metrics={report.quality_metrics_by_group[metricTab] ?? {}} />
      </SurfaceCard>

      <section className="grid gap-4 2xl:grid-cols-[minmax(0,1.15fr)_minmax(380px,0.85fr)]">
        <ReviewQueuePanel
          review={review}
          selectedReviewItem={selectedReviewItem}
          selectedReviewId={selectedReviewId}
          selectedBatchReviewIds={selectedBatchReviewIds}
          reviewPatch={reviewPatch}
          reviewNote={reviewNote}
          allowBlockerIgnore={allowBlockerIgnore}
          isSaving={isReviewSaving}
          error={reviewError}
          onSelect={handleSelectReviewItem}
          onBatchSelectionChange={setSelectedBatchReviewIds}
          onPatchChange={setReviewPatch}
          onNoteChange={setReviewNote}
          onAllowBlockerIgnoreChange={setAllowBlockerIgnore}
          onAction={(action) => void handleReviewAction(action)}
          onBatchAction={(action) => void handleBatchReviewAction(action)}
          onEvidence={(item) => void jumpToEvidence(item)}
        />
        <ParserRunsPanel
          sourceId={sourceId}
          runs={runs}
          activeParserRunId={parserRunId}
          go={go}
          onEvidence={(runId) => {
            const nextQuery = { target_type: '', target_id: '', parser_run_id: runId, issue_type: '' }
            setEvidenceQuery(nextQuery)
            void loadEvidence(nextQuery)
          }}
        />
      </section>

      {runDetail ? <ParserRunDetailPanel detail={runDetail} /> : null}

      <EvidenceBrowser
        query={evidenceQuery}
        evidence={evidence}
        isLoading={isEvidenceLoading}
        error={evidenceError}
        onQueryChange={setEvidenceQuery}
        onSearch={() => void loadEvidence()}
      />

      <TextbookArtifactSummaryPanel report={report} />

      <section className="grid gap-4 xl:grid-cols-2">
        <RawJsonPanel title="Quality Report JSON" data={report.quality_report} />
        <RawJsonPanel title="Parser Artifacts JSON" data={report.parser_artifacts} />
      </section>
    </section>
  )
}

function TextbookArtifactSummaryPanel({ report }: { report: TextbookParsingReport }) {
  const artifacts = report.parser_artifacts ?? {}
  const rows = Object.entries(artifacts).map(([key, value]) => ({
    key,
    summary: summarizeArtifact(value),
  }))
  return (
    <SurfaceCard>
      <div className="flex items-center gap-2">
        <Database className="size-5 text-cyan-500" />
        <h3 className="text-base font-black text-slate-950">Textbook Structure / Debug Views</h3>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-500">
        Learner pages hide parsing review, quality, textbook structure internals, and raw debug tables. Use this panel with Review Queue, Evidence Browser, and raw artifacts to inspect parsing output.
      </p>
      {rows.length ? (
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {rows.map((row) => (
            <MetricBlock key={row.key} label={row.key} value={row.summary} />
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<Database className="size-5" />}
          title="No parser artifacts"
          description="当前 report 没有返回 parser_artifacts。"
        />
      )}
    </SurfaceCard>
  )
}

function summarizeArtifact(value: unknown) {
  if (Array.isArray(value)) return `${value.length} items`
  if (value && typeof value === 'object') return `${Object.keys(value).length} keys`
  if (value === null || value === undefined) return '-'
  return String(value)
}

function SourceSummaryCard({ source }: { source: TextbookSourceDebugSummary }) {
  return (
    <SurfaceCard>
      <div className="flex items-center gap-2">
        <BookOpenCheck className="size-5 text-cyan-500" />
        <h3 className="text-base font-black text-slate-950">Source Summary</h3>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <MetricBlock label="status" value={<StatusPill value={source.status} />} />
        <MetricBlock label="quality_status" value={<QualityPill value={source.quality_status ?? source.status} />} />
        <MetricBlock label="overall_score" value={formatScore(source.overall_score)} />
        <MetricBlock label="parser_status" value={source.parser_status ?? '-'} />
        <MetricBlock label="latest_parser_run_id" value={source.latest_parser_run_id ?? '-'} />
        <MetricBlock label="updated_at" value={formatDate(source.updated_at)} />
      </div>
      <div className="mt-4">
        <ReviewCounts source={source} />
      </div>
    </SurfaceCard>
  )
}

function QualityScoreCard({ report }: { report: TextbookParsingReport }) {
  const score = report.quality_score
  return (
    <SurfaceCard>
      <div className="flex items-center gap-2">
        <ShieldAlert className="size-5 text-cyan-500" />
        <h3 className="text-base font-black text-slate-950">Quality Score</h3>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <MetricBlock label="overall" value={formatScore(score?.overall_score)} />
        <MetricBlock label="structure" value={formatScore(score?.structure_score)} />
        <MetricBlock label="vocabulary" value={formatScore(score?.vocabulary_score)} />
        <MetricBlock label="rag" value={formatScore(score?.rag_score)} />
        <MetricBlock label="provenance" value={formatScore(score?.provenance_score)} />
        <MetricBlock label="status" value={<QualityPill value={score?.status ?? report.source.quality_status ?? '-'} />} />
      </div>
      {report.blocking_reasons.length ? (
        <StatusBanner tone="warning" title="Blocking Reasons">
          {report.blocking_reasons.join(' / ')}
        </StatusBanner>
      ) : null}
      {report.warnings.length ? (
        <div className="mt-3">
          <StatusBanner tone="info" title="Warnings">
            {report.warnings.join(' / ')}
          </StatusBanner>
        </div>
      ) : null}
    </SurfaceCard>
  )
}

function ReviewQueuePanel({
  review,
  selectedReviewItem,
  selectedReviewId,
  selectedBatchReviewIds,
  reviewPatch,
  reviewNote,
  allowBlockerIgnore,
  isSaving,
  error,
  onSelect,
  onBatchSelectionChange,
  onPatchChange,
  onNoteChange,
  onAllowBlockerIgnoreChange,
  onAction,
  onBatchAction,
  onEvidence,
}: {
  review: ParserReviewItemsResponse | null
  selectedReviewItem: ParserReviewItem | null
  selectedReviewId: string | null
  selectedBatchReviewIds: string[]
  reviewPatch: string
  reviewNote: string
  allowBlockerIgnore: boolean
  isSaving: boolean
  error: string | null
  onSelect: (itemId: string) => void
  onBatchSelectionChange: (itemIds: string[]) => void
  onPatchChange: (value: string) => void
  onNoteChange: (value: string) => void
  onAllowBlockerIgnoreChange: (value: boolean) => void
  onAction: (action: 'confirm' | 'update' | 'ignore') => void
  onBatchAction: (action: 'confirm' | 'ignore') => void
  onEvidence: (item: ParserReviewItem) => void
}) {
  const items = review?.items ?? []
  const pendingItems = items.filter((item) => item.decision === 'pending')
  const selectedBatchSet = new Set(selectedBatchReviewIds)
  const allPendingSelected = pendingItems.length > 0 && pendingItems.every((item) => selectedBatchSet.has(item.id))
  const toggleBatchItem = (itemId: string) => {
    onBatchSelectionChange(
      selectedBatchSet.has(itemId)
        ? selectedBatchReviewIds.filter((current) => current !== itemId)
        : [...selectedBatchReviewIds, itemId],
    )
  }
  const toggleAllPending = () => {
    onBatchSelectionChange(allPendingSelected ? [] : pendingItems.map((item) => item.id))
  }
  return (
    <SurfaceCard>
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex items-center gap-2">
          <FileWarning className="size-5 text-cyan-500" />
          <h3 className="text-base font-black text-slate-950">Review Queue</h3>
        </div>
        {review ? (
          <div className="flex flex-wrap gap-2 text-xs font-bold text-slate-600">
            <span>{review.summary.pending_review_count} pending</span>
            <span>{review.summary.pending_blocker_count} blockers</span>
            <span>{review.summary.review_warning_count} warnings</span>
          </div>
        ) : null}
      </div>

      {items.length ? (
        <div className="mt-4 space-y-3">
          <div className="flex flex-col gap-3 rounded-lg border border-slate-100 bg-slate-50 p-3 xl:flex-row xl:items-center xl:justify-between">
            <div className="text-sm font-bold text-slate-700">
              {selectedBatchReviewIds.length} selected for batch review
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" disabled={isSaving || selectedBatchReviewIds.length === 0} onClick={() => onBatchAction('confirm')}>
                <CheckCircle2 className="size-4" />
                Batch Confirm
              </Button>
              <Button variant="danger" disabled={isSaving || selectedBatchReviewIds.length === 0} onClick={() => onBatchAction('ignore')}>
                <XCircle className="size-4" />
                Batch Ignore
              </Button>
            </div>
          </div>
          <div className="overflow-auto rounded-lg border border-slate-100">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2 font-black">
                  <input
                    type="checkbox"
                    checked={allPendingSelected}
                    onChange={toggleAllPending}
                    aria-label="Select all pending review items"
                  />
                </th>
                <th className="px-3 py-2 font-black">Issue</th>
                <th className="px-3 py-2 font-black">Target</th>
                <th className="px-3 py-2 font-black">Evidence</th>
                <th className="px-3 py-2 font-black">Decision</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((item) => (
                <tr
                  key={item.id}
                  className={`cursor-pointer align-top ${selectedReviewId === item.id ? 'bg-cyan-50' : 'bg-white hover:bg-slate-50'}`}
                  onClick={() => onSelect(item.id)}
                >
                  <td className="px-3 py-3">
                    <input
                      type="checkbox"
                      checked={selectedBatchSet.has(item.id)}
                      disabled={item.decision !== 'pending'}
                      onChange={(event) => {
                        event.stopPropagation()
                        toggleBatchItem(item.id)
                      }}
                      onClick={(event) => event.stopPropagation()}
                      aria-label={`Select review item ${item.id}`}
                    />
                  </td>
                  <td className="px-3 py-3">
                    <p className="font-bold text-slate-950">{item.issue_type}</p>
                    <p className="mt-1"><SeverityPill value={item.severity} /></p>
                  </td>
                  <td className="max-w-xs px-3 py-3">
                    <p className="font-mono text-xs font-bold text-slate-700">{item.target_type}</p>
                    <p className="mt-1 break-all font-mono text-xs text-slate-400">{item.target_id ?? '-'}</p>
                  </td>
                  <td className="px-3 py-3">
                    <Button variant="ghost" onClick={(event) => {
                      event.stopPropagation()
                      onEvidence(item)
                    }}>
                      <Search className="size-4" />
                      Evidence
                    </Button>
                  </td>
                  <td className="px-3 py-3 text-slate-700">{item.decision}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      ) : (
        <EmptyState
          icon={<CheckCircle2 className="size-5" />}
          title="No pending review items"
          description="当前教材没有 pending review item。"
        />
      )}

      {selectedReviewItem ? (
        <div className="mt-4 rounded-lg border border-slate-100 bg-slate-50 p-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <p className="font-mono text-xs font-black text-slate-950">{selectedReviewItem.id}</p>
              <p className="mt-1 text-sm text-slate-600">
                {selectedReviewItem.issue_type} / {selectedReviewItem.severity} / {selectedReviewItem.target_type}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                disabled={isSaving}
                onClick={() => onAction('confirm')}
              >
                <CheckCircle2 className="size-4" />
                Confirm
              </Button>
              <Button
                variant="secondary"
                disabled={isSaving}
                onClick={() => onAction('update')}
              >
                <Pencil className="size-4" />
                Update
              </Button>
              <Button
                variant="danger"
                disabled={isSaving}
                onClick={() => onAction('ignore')}
              >
                <XCircle className="size-4" />
                Ignore
              </Button>
            </div>
          </div>
          <div className="mt-3 grid gap-3 xl:grid-cols-2">
            <textarea
              value={reviewPatch}
              onChange={(event) => onPatchChange(event.target.value)}
              rows={7}
              className="w-full rounded-lg border border-slate-200 bg-white p-3 font-mono text-xs text-slate-900 outline-none focus:border-cyan-400"
            />
            <div className="space-y-3">
              <textarea
                value={reviewNote}
                onChange={(event) => onNoteChange(event.target.value)}
                rows={3}
                placeholder="review_note"
                className="w-full rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-900 outline-none focus:border-cyan-400"
              />
              <label className="flex items-center gap-2 text-sm font-bold text-slate-700">
                <input
                  type="checkbox"
                  checked={allowBlockerIgnore}
                  onChange={(event) => onAllowBlockerIgnoreChange(event.target.checked)}
                />
                allow_blocker_ignore
              </label>
              <RawJsonPanel title="Selected Review JSON" data={selectedReviewItem} />
            </div>
          </div>
          {error ? (
            <div className="mt-3">
              <StatusBanner tone="warning" title="Review action failed">{error}</StatusBanner>
            </div>
          ) : null}
        </div>
      ) : null}
    </SurfaceCard>
  )
}

function ParserRunsPanel({
  sourceId,
  runs,
  activeParserRunId,
  go,
  onEvidence,
}: {
  sourceId: string
  runs: ParserRunsResponse | null
  activeParserRunId: string | null
  go: (path: string) => void
  onEvidence: (parserRunId: string) => void
}) {
  const parserRuns = runs?.parser_runs ?? []
  return (
    <SurfaceCard>
      <div className="flex items-center gap-2">
        <History className="size-5 text-cyan-500" />
        <h3 className="text-base font-black text-slate-950">ParserRun History</h3>
      </div>
      {parserRuns.length ? (
        <div className="mt-4 space-y-3">
          {parserRuns.map((run) => (
            <div
              key={run.parser_run_id}
              className={`rounded-lg border p-3 ${activeParserRunId === run.parser_run_id ? 'border-cyan-300 bg-cyan-50' : 'border-slate-100 bg-slate-50'}`}
            >
              <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                <div>
                  <p className="font-mono text-xs font-black text-slate-950">{run.parser_id}@{run.parser_version}</p>
                  <p className="mt-1 break-all font-mono text-xs text-slate-500">{run.parser_run_id}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <StatusPill value={run.status} />
                  <QualityPill value={run.quality_status ?? '-'} />
                </div>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                <MetricBlock label="started_at" value={formatDate(run.started_at)} compact />
                <MetricBlock label="overall_score" value={formatScore(run.overall_score)} compact />
                <MetricBlock label="pending_review" value={String(run.pending_review_count)} compact />
              </div>
              {run.error_message ? <p className="mt-2 text-sm text-rose-600">{run.error_message}</p> : null}
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  onClick={() => go(`/dev/textbooks/${encodeURIComponent(sourceId)}/parser-runs/${encodeURIComponent(run.parser_run_id)}`)}
                >
                  <Clock3 className="size-4" />
                  Detail
                </Button>
                <Button variant="ghost" onClick={() => onEvidence(run.parser_run_id)}>
                  <Database className="size-4" />
                  Evidence
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={<History className="size-5" />}
          title="No parser runs"
          description="当前教材还没有 ParserRun 历史。"
        />
      )}
    </SurfaceCard>
  )
}

function ParserRunDetailPanel({ detail }: { detail: ParserRunDetailResponse }) {
  return (
    <SurfaceCard>
      <div className="flex items-center gap-2">
        <Clock3 className="size-5 text-cyan-500" />
        <h3 className="text-base font-black text-slate-950">ParserRun Detail</h3>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricBlock label="parser_id" value={detail.parser_run.parser_id} />
        <MetricBlock label="parser_version" value={detail.parser_run.parser_version} />
        <MetricBlock label="status" value={<StatusPill value={detail.parser_run.status} />} />
        <MetricBlock label="duration_ms" value={String(detail.parser_run.duration_ms ?? '-')} />
        <MetricBlock label="parser_profile_id" value={detail.parser_run.parser_profile_id ?? '-'} />
        <MetricBlock label="book_manifest_id" value={detail.parser_run.book_manifest_id ?? '-'} />
        <MetricBlock label="input_hash" value={detail.parser_run.input_hash ?? '-'} />
        <MetricBlock label="review_items" value={String(detail.review_items.length)} />
      </div>
      {detail.error_message ? (
        <div className="mt-3">
          <StatusBanner tone="warning" title="Parser error">{detail.error_message}</StatusBanner>
        </div>
      ) : null}
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <RawJsonPanel title="ParserRun JSON" data={detail.parser_run} />
        <RawJsonPanel title="Related Review Items JSON" data={detail.review_items} />
      </div>
    </SurfaceCard>
  )
}

function EvidenceBrowser({
  query,
  evidence,
  isLoading,
  error,
  onQueryChange,
  onSearch,
}: {
  query: EvidenceQuery
  evidence: ParserEvidenceResponse | null
  isLoading: boolean
  error: string | null
  onQueryChange: (query: EvidenceQuery) => void
  onSearch: () => void
}) {
  return (
    <SurfaceCard>
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex items-center gap-2">
          <Database className="size-5 text-cyan-500" />
          <h3 className="text-base font-black text-slate-950">Evidence Browser</h3>
        </div>
        <Button onClick={onSearch} disabled={isLoading}>
          <Search className="size-4" />
          {isLoading ? 'Searching...' : 'Search'}
        </Button>
      </div>
      <div className="mt-4 grid gap-3 xl:grid-cols-4">
        <select
          value={query.target_type ?? ''}
          onChange={(event) => onQueryChange({ ...query, target_type: event.target.value })}
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 outline-none focus:border-cyan-400"
        >
          <option value="">target_type</option>
          {TARGET_TYPES.map((targetType) => (
            <option key={targetType} value={targetType}>{targetType}</option>
          ))}
        </select>
        <input
          value={query.target_id ?? ''}
          onChange={(event) => onQueryChange({ ...query, target_id: event.target.value })}
          placeholder="target_id"
          className="rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm text-slate-900 outline-none focus:border-cyan-400"
        />
        <input
          value={query.parser_run_id ?? ''}
          onChange={(event) => onQueryChange({ ...query, parser_run_id: event.target.value })}
          placeholder="parser_run_id"
          className="rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm text-slate-900 outline-none focus:border-cyan-400"
        />
        <input
          value={query.issue_type ?? ''}
          onChange={(event) => onQueryChange({ ...query, issue_type: event.target.value })}
          placeholder="issue_type"
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 outline-none focus:border-cyan-400"
        />
      </div>
      {error ? <StatusBanner tone="warning" title="Evidence request failed">{error}</StatusBanner> : null}
      {evidence?.warnings.length ? (
        <div className="mt-3">
          <StatusBanner tone="warning" title="Evidence warnings">{evidence.warnings.join(' / ')}</StatusBanner>
        </div>
      ) : null}
      {evidence ? (
        evidence.evidence.length ? (
          <div className="mt-4 grid gap-3 xl:grid-cols-2">
            {evidence.evidence.map((item, index) => (
              <div key={`${item.target_type}:${item.target_id ?? index}:${index}`} className="rounded-lg border border-slate-100 bg-slate-50 p-4">
                <div className="flex flex-wrap gap-2">
                  <StatusPill value={item.target_type} />
                  {item.issue_types.map((issue) => <SeverityPill key={issue} value={issue} />)}
                </div>
                <div className="mt-3 space-y-1 font-mono text-xs text-slate-500">
                  <p className="break-all">target_id: {item.target_id ?? '-'}</p>
                  <p className="break-all">parser_run_id: {item.parser_run_id ?? '-'}</p>
                  <p>source_page: {item.source_page ?? '-'} / pdf_page: {String(item.pdf_page ?? '-')}</p>
                  <p>confidence: {formatScore(item.confidence)}</p>
                </div>
                {item.raw_text_excerpt ? (
                  <p className="mt-3 max-h-52 overflow-auto rounded-lg bg-white p-3 text-sm leading-6 text-slate-700">
                    {item.raw_text_excerpt}
                  </p>
                ) : null}
                {item.warnings.length ? (
                  <p className="mt-2 text-sm text-amber-700">{item.warnings.join(' / ')}</p>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<Database className="size-5" />}
            title="No evidence"
            description="当前查询没有返回 parser evidence。"
          />
        )
      ) : null}
    </SurfaceCard>
  )
}

function MetricGrid({ metrics }: { metrics: Record<string, unknown> }) {
  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {Object.entries(metrics).map(([key, value]) => (
        <MetricBlock key={key} label={key} value={formatValue(value)} />
      ))}
    </div>
  )
}

function MetricBlock({
  label,
  value,
  compact = false,
}: {
  label: string
  value: ReactNode
  compact?: boolean
}) {
  return (
    <div className={`rounded-lg border border-slate-100 bg-slate-50 ${compact ? 'p-2' : 'p-3'}`}>
      <p className="text-xs font-bold uppercase text-slate-500">{label}</p>
      <div className="mt-1 break-words font-mono text-sm font-black text-slate-950">{value}</div>
    </div>
  )
}

function ReviewCounts({ source }: { source: TextbookSourceDebugSummary }) {
  return (
    <div className="flex flex-wrap gap-2 text-xs font-bold text-slate-600">
      <span className="rounded-lg bg-slate-100 px-2 py-1">{source.pending_review_count} pending</span>
      <span className="rounded-lg bg-rose-50 px-2 py-1 text-rose-700">{source.pending_blocker_count} blockers</span>
      <span className="rounded-lg bg-amber-50 px-2 py-1 text-amber-700">{source.review_warning_count} warnings</span>
    </div>
  )
}

function FilterSelect({
  icon,
  value,
  onChange,
  options,
  placeholder,
}: {
  icon: ReactNode
  value: string
  onChange: (value: string) => void
  options: string[]
  placeholder: string
}) {
  return (
    <label className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
      {icon}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-w-0 flex-1 bg-transparent text-sm font-bold text-slate-900 outline-none"
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option} value={option}>{option}</option>
        ))}
      </select>
    </label>
  )
}

function StatusPill({ value }: { value: string }) {
  return <span className={`inline-flex rounded-lg px-2 py-1 text-xs font-black ${pillClass(value)}`}>{value}</span>
}

function QualityPill({ value }: { value: string }) {
  return <span className={`inline-flex rounded-lg px-2 py-1 text-xs font-black ${pillClass(value)}`}>{value}</span>
}

function SeverityPill({ value }: { value: string }) {
  return <span className={`inline-flex rounded-lg px-2 py-1 text-xs font-black ${pillClass(value)}`}>{value}</span>
}

function RawJsonPanel({ title, data }: { title: string; data: unknown }) {
  return (
    <details className="rounded-lg border border-slate-200 bg-white p-4">
      <summary className="cursor-pointer text-sm font-black text-slate-950">{title}</summary>
      <pre className="mt-4 max-h-[420px] overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-100">
        {JSON.stringify(data, null, 2)}
      </pre>
    </details>
  )
}

function parsePatch(value: string) {
  const trimmed = value.trim()
  if (!trimmed) return {}
  const parsed = JSON.parse(trimmed) as unknown
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('Patch JSON must be an object')
  }
  return parsed as Record<string, unknown>
}

function formatDate(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function formatScore(value?: number | null) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-'
  return value.toFixed(3)
}

function formatValue(value: unknown): ReactNode {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(4)
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'string') return value
  return JSON.stringify(value)
}

function pillClass(value: string) {
  if (value.includes('blocker') || value === 'blocked' || value === 'failed') {
    return 'bg-rose-50 text-rose-700'
  }
  if (value.includes('warning') || value === 'review_required' || value === 'partial_indexed') {
    return 'bg-amber-50 text-amber-700'
  }
  if (value === 'published' || value === 'completed' || value === 'confirmed') {
    return 'bg-emerald-50 text-emerald-700'
  }
  return 'bg-slate-100 text-slate-700'
}

function readTextbookRoute(): TextbookRouteState {
  const match = window.location.pathname.match(/^\/dev\/textbooks\/([^/]+)(?:\/parser-runs\/([^/]+))?/)
  return {
    sourceId: match?.[1] ? decodeURIComponent(match[1]) : null,
    parserRunId: match?.[2] ? decodeURIComponent(match[2]) : null,
  }
}
