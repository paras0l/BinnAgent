import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  ExternalLink,
  FileJson,
  RefreshCw,
  ShieldCheck,
  Wrench,
  XCircle,
} from 'lucide-react'
import { FeatureHero } from '@/components/layout/FeatureHero'
import { PageShell } from '@/components/layout/PageShell'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { StatusBanner } from '@/components/ui/StatusBanner'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import { debugFetch } from '@/shared/api/debugClient'
import type { Learner } from '@/types'

interface EpisodeDebugPageProps {
  learner: Learner
  episodeId: string
}

interface EvidenceRef {
  evidence_type: string
  evidence_id: string
  confidence?: number
  reason?: string | null
  used_by?: string | null
  metadata?: Record<string, unknown>
}

interface RuntimeEpisode {
  id: string
  learner_id: string
  source: string
  entrypoint: string
  status: string
  task_spec: Record<string, unknown>
  context_snapshot?: Record<string, unknown> | null
  memory_context_ids?: string[] | null
  rag_chunk_ids?: string[] | null
  tool_call_ids?: string[] | null
  verification_report?: VerificationReport | Record<string, unknown> | null
  failure_type?: string | null
  error_message?: string | null
  started_at: string
  completed_at?: string | null
  created_at: string
  updated_at: string
}

interface LearningEvent {
  id: string
  episode_id: string
  learner_id: string
  event_type: string
  source_module: string
  target_type?: string | null
  target_id?: string | null
  payload: Record<string, unknown>
  occurred_at: string
}

interface ToolCallRecord {
  id: string
  episode_id: string
  tool_name: string
  input_hash: string
  output_hash?: string | null
  latency_ms?: number | null
  status: string
  error?: string | null
  metadata?: Record<string, unknown>
  created_at: string
}

interface VerificationCheck {
  name: string
  check_type: string
  passed: boolean
  severity?: string
  expected?: unknown
  actual?: unknown
  source_node?: string | null
  source_event_type?: string | null
  source_tool_name?: string | null
  evidence_refs?: EvidenceRef[]
  message?: string | null
}

interface VerificationReport {
  episode_id: string
  task_id?: string | null
  status: string
  required_checks?: string[]
  checks: VerificationCheck[]
  passed_count?: number
  failed_count?: number
  warning_count?: number
  critical_failed_count?: number
  evidence_ref_count?: number
  failed_reason?: string | null
  generated_at: string
  metadata?: Record<string, unknown>
}

interface LearningCheckpoint {
  checkpoint_id: string
  learner_id?: string
  episode_id?: string
  thread_id?: string | null
  checkpoint_key?: string
  status: string
  resume_from?: string | null
  answer_required?: boolean
  current_task_id?: string | null
  required_input_schema?: Record<string, unknown> | null
  prompt_payload?: Record<string, unknown> | null
  state_snapshot?: Record<string, unknown> | null
  created_at?: string | null
  updated_at?: string | null
  consumed_at?: string | null
}

interface PromptExecutionRecord {
  id: string
  prompt_id: string
  prompt_version: string
  source_module: string
  schema_validation_status: string
  schema_error_summary?: string | null
  repair_used: boolean
  fallback_used: boolean
  decision: string
  langfuse_trace_id?: string | null
  langfuse_observation_id?: string | null
  prompt_hash?: string
  input_hash?: string
  output_schema?: string | null
  created_at: string
}

interface EpisodeTrace {
  episode: RuntimeEpisode
  events: LearningEvent[]
  tool_calls: ToolCallRecord[]
  checkpoint?: LearningCheckpoint | null
  verification_report?: VerificationReport | Record<string, unknown> | null
  graph_run?: Record<string, unknown>
  prompt_executions?: PromptExecutionRecord[]
  evidence_refs?: EvidenceRef[]
  node_summaries?: NodeSummary[]
}

interface NodeSummary {
  node: string
  event_count: number
  tool_call_count: number
  prompt_execution_count: number
}

interface GraphRunDebug {
  episode_id: string
  learner_id: string
  thread_id?: string | null
  graph_run_id?: string | null
  session_id?: string | null
  checkpoint_status?: string | null
  resume_from?: string | null
  current_task_id?: string | null
  node_summaries?: NodeSummary[]
  events?: LearningEvent[]
  tool_calls?: ToolCallRecord[]
  prompt_executions?: PromptExecutionRecord[]
  verification_report?: VerificationReport | null
  evidence_refs?: EvidenceRef[]
  langfuse_trace_id?: string | null
  trace: EpisodeTrace
}

export function EpisodeDebugPage({ learner, episodeId }: EpisodeDebugPageProps) {
  const [trace, setTrace] = useState<EpisodeTrace | null>(null)
  const [graphRun, setGraphRun] = useState<GraphRunDebug | null>(null)
  const [verification, setVerification] = useState<VerificationReport | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadTrace = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (isUuidLike(learner.id)) params.set('learner_id', learner.id)
      const query = params.toString()
      const response = await debugFetch(`/api/debug/graph-runs/${episodeId}${query ? `?${query}` : ''}`)
      if (!response.ok) throw new Error('Graph run debug failed')
      const data: GraphRunDebug = await response.json()
      setGraphRun(data)
      setTrace(data.trace)
      setVerification(data.verification_report ?? (data.trace.verification_report as VerificationReport | null) ?? null)
    } catch (err) {
      console.error('Episode debug load error:', err)
      setError('Graph Run Debug 暂时无法加载，请确认 episode_id、learner_id 和 debug token。')
    } finally {
      setIsLoading(false)
    }
  }, [episodeId, learner.id])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadTrace(), 0)
    return () => window.clearTimeout(timer)
  }, [loadTrace])

  const taskSpec = trace?.episode.task_spec as TaskSpecLike | undefined
  const statusTone = trace?.episode.status === 'completed' || trace?.episode.status === 'completed_with_warnings'
    ? 'success'
    : trace?.episode.status === 'failed' || trace?.episode.status === 'verification_failed'
      ? 'danger'
      : 'neutral'
  const eventTypes = useMemo(() => trace?.events.map((event) => event.event_type).join(' / ') ?? '', [trace])
  const promptExecutions = trace?.prompt_executions ?? graphRun?.prompt_executions ?? []
  const evidenceRefs = trace?.evidence_refs ?? graphRun?.evidence_refs ?? []
  const nodeSummaries = trace?.node_summaries ?? graphRun?.node_summaries ?? []
  const graphLangfuseTraceId = graphRun?.langfuse_trace_id ?? stringValue(trace?.graph_run?.langfuse_trace_id)

  if (isLoading && !trace) {
    return <LoadingState title="正在读取 Episode Trace" description="正在加载 TaskSpec、事件链、工具调用和验证报告..." />
  }

  if (error || !trace) {
    return (
      <ErrorState
        title="Episode Trace 不可用"
        description={error ?? '没有找到可展示的 episode trace。'}
        action={
          <Button variant="secondary" onClick={() => void loadTrace()}>
            <RefreshCw className="size-4" />
            重新加载
          </Button>
        }
      />
    )
  }

  return (
    <PageShell variant="full">
      <FeatureHero
        eyebrow="Runtime Debug"
        title="Agent Episode Trace"
        description={`当前学习者 ${learner.nickname} 的可追踪 AgentEpisode 运行链路。`}
        stats={[
          { label: 'Episode 状态', value: trace.episode.status, tone: statusTone === 'success' ? 'success' : statusTone === 'danger' ? 'warning' : 'primary' },
          { label: '事件数', value: trace.events.length },
          { label: '工具调用', value: trace.tool_calls.length },
          { label: 'Prompt 执行', value: promptExecutions.length },
          { label: 'EvidenceRefs', value: evidenceRefs.length },
          { label: '验证状态', value: verification?.status ?? 'unknown', tone: verification?.status === 'passed' ? 'success' : 'warning' },
        ]}
        actions={
          <>
            <LangfuseTraceLink traceId={graphLangfuseTraceId} label="Open Langfuse trace" />
            <Button variant="secondary" onClick={() => void loadTrace()}>
              <RefreshCw className="size-4" />
              刷新
            </Button>
          </>
        }
      />

      <StatusBanner tone={verification?.status === 'passed' ? 'success' : 'warning'} title="VerificationReport">
        {verification?.status === 'passed'
          ? '关键步骤已通过 deterministic / schema / business_rule / evidence checks。'
          : verification?.failed_reason ?? '验证报告尚未通过。'}
      </StatusBanner>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="flex flex-col gap-4">
          <SurfaceCard>
            <SectionTitle icon={<Activity className="size-4" />} title="Episode Summary" />
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <KeyValue label="episode_id" value={trace.episode.id} />
              <KeyValue label="learner_id" value={trace.episode.learner_id} />
              <KeyValue label="status" value={trace.episode.status} />
              <KeyValue label="source" value={trace.episode.source} />
              <KeyValue label="entrypoint" value={trace.episode.entrypoint} />
              <KeyValue label="failure_type" value={trace.episode.failure_type ?? 'none'} />
              <KeyValue label="started_at" value={formatDate(trace.episode.started_at)} />
              <KeyValue label="completed_at" value={formatDate(trace.episode.completed_at)} />
              <KeyValue label="events" value={eventTypes || 'none'} />
            </div>
          </SurfaceCard>

          <SurfaceCard>
            <SectionTitle icon={<Database className="size-4" />} title="Graph / Checkpoint" />
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <KeyValue label="thread_id" value={graphRun?.thread_id ?? stringValue(trace.graph_run?.thread_id)} />
              <KeyValue label="graph_run_id" value={graphRun?.graph_run_id ?? stringValue(trace.graph_run?.graph_run_id)} />
              <KeyValue label="session_id" value={graphRun?.session_id ?? stringValue(trace.graph_run?.session_id)} />
              <KeyValue label="checkpoint_status" value={graphRun?.checkpoint_status ?? trace.checkpoint?.status ?? 'none'} />
              <KeyValue label="resume_from" value={graphRun?.resume_from ?? trace.checkpoint?.resume_from ?? 'none'} />
              <KeyValue label="current_task_id" value={graphRun?.current_task_id ?? trace.checkpoint?.current_task_id ?? 'none'} />
              <KeyValue label="answer_required" value={String(Boolean(trace.checkpoint?.answer_required ?? trace.graph_run?.answer_required))} />
              <KeyValue label="langfuse_trace_id" value={graphLangfuseTraceId} />
            </div>
            {trace.checkpoint ? (
              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                <JsonBlock title="required_input_schema" value={trace.checkpoint.required_input_schema ?? {}} />
                <JsonBlock title="prompt_payload_summary" value={trace.checkpoint.prompt_payload ?? {}} />
                <JsonBlock title="state_snapshot_summary" value={trace.checkpoint.state_snapshot ?? {}} />
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500">No graph checkpoint recorded for this episode.</p>
            )}
          </SurfaceCard>

          <SurfaceCard>
            <SectionTitle icon={<Clock3 className="size-4" />} title="Timeline" />
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-3 py-2">time</th>
                    <th className="px-3 py-2">event</th>
                    <th className="px-3 py-2">source</th>
                    <th className="px-3 py-2">target</th>
                    <th className="px-3 py-2">evidence</th>
                    <th className="px-3 py-2">payload</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {trace.events.map((event) => (
                    <tr key={event.id} className="align-top">
                      <td className="whitespace-nowrap px-3 py-3 text-xs text-slate-500">{formatDate(event.occurred_at)}</td>
                      <td className="px-3 py-3 font-bold text-slate-900">{event.event_type}</td>
                      <td className="px-3 py-3 text-slate-600">{event.source_module}</td>
                      <td className="px-3 py-3 text-xs text-slate-500">{event.target_type ?? 'none'}:{event.target_id ?? 'none'}</td>
                      <td className="px-3 py-3">{evidenceCount(event.payload)}</td>
                      <td className="max-w-[360px] px-3 py-3 text-xs text-slate-500">{payloadSummary(event.payload)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SurfaceCard>

          <SurfaceCard>
            <SectionTitle icon={<Wrench className="size-4" />} title="Tool Calls" />
            {trace.tool_calls.length ? (
              <div className="mt-4 overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">tool</th>
                      <th className="px-3 py-2">status</th>
                      <th className="px-3 py-2">latency</th>
                      <th className="px-3 py-2">input_hash</th>
                      <th className="px-3 py-2">output_hash</th>
                      <th className="px-3 py-2">error</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {trace.tool_calls.map((tool) => (
                      <tr key={tool.id}>
                        <td className="px-3 py-3 font-bold text-slate-900">{tool.tool_name}</td>
                        <td className="px-3 py-3"><StatusPill status={tool.status} /></td>
                        <td className="px-3 py-3 text-slate-600">{tool.latency_ms ?? 0}ms</td>
                        <td className="px-3 py-3 font-mono text-xs text-slate-500">{shortHash(tool.input_hash)}</td>
                        <td className="px-3 py-3 font-mono text-xs text-slate-500">{shortHash(tool.output_hash)}</td>
                        <td className="px-3 py-3 text-xs text-rose-600">{tool.error ?? 'none'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyLine text="No tool calls recorded." />
            )}
          </SurfaceCard>

          <SurfaceCard>
            <SectionTitle icon={<FileJson className="size-4" />} title="Prompt Executions" />
            {promptExecutions.length ? (
              <div className="mt-4 overflow-x-auto">
                <table className="min-w-full text-left text-sm">
                  <thead className="text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">prompt</th>
                      <th className="px-3 py-2">schema</th>
                      <th className="px-3 py-2">repair</th>
                      <th className="px-3 py-2">fallback</th>
                      <th className="px-3 py-2">decision</th>
                      <th className="px-3 py-2">langfuse</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {promptExecutions.map((item) => (
                      <tr key={item.id} className="align-top">
                        <td className="px-3 py-3">
                          <p className="font-mono text-xs font-bold text-slate-900">{item.prompt_id}@{item.prompt_version}</p>
                          <p className="mt-1 text-xs text-slate-500">{item.source_module}</p>
                        </td>
                        <td className="px-3 py-3"><StatusPill status={item.schema_validation_status} /></td>
                        <td className="px-3 py-3 text-slate-600">{String(item.repair_used)}</td>
                        <td className="px-3 py-3 text-slate-600">{String(item.fallback_used)}</td>
                        <td className="px-3 py-3 text-slate-600">{item.decision}</td>
                        <td className="px-3 py-3 font-mono text-xs text-slate-500">
                          <LangfuseTraceLink traceId={item.langfuse_trace_id} compact />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyLine text="No prompt executions recorded for this episode." />
            )}
          </SurfaceCard>
        </div>

        <aside className="flex flex-col gap-4">
          <SurfaceCard>
            <SectionTitle icon={<Database className="size-4" />} title="TaskSpec" />
            <div className="mt-4 space-y-3">
              <KeyValue label="task_type" value={taskSpec?.task_type ?? 'unknown'} />
              <KeyValue label="objective" value={taskSpec?.objective ?? 'unknown'} />
              <KeyValue label="target_type" value={taskSpec?.target?.target_type ?? 'unknown'} />
              <KeyValue label="target_id" value={taskSpec?.target?.target_id ?? 'unknown'} />
              <KeyValue label="allowed_tools" value={(taskSpec?.allowed_tools ?? []).join(', ') || 'none'} />
              <JsonBlock title="success_criteria" value={taskSpec?.success_criteria ?? {}} />
              <JsonBlock title="verification_policy" value={taskSpec?.verification_policy ?? {}} />
            </div>
          </SurfaceCard>

          <SurfaceCard>
            <SectionTitle icon={<ShieldCheck className="size-4" />} title="Verification" />
            <div className="mt-4 space-y-3">
              <div className="grid gap-2 sm:grid-cols-2">
                <KeyValue label="status" value={verification?.status ?? 'unknown'} />
                <KeyValue label="passed / failed" value={`${verification?.passed_count ?? 0} / ${verification?.failed_count ?? 0}`} />
                <KeyValue label="warnings" value={verification?.warning_count ?? 0} />
                <KeyValue label="critical_failed" value={verification?.critical_failed_count ?? 0} />
                <KeyValue label="evidence_ref_count" value={verification?.evidence_ref_count ?? 0} />
              </div>
              <JsonBlock title="required_checks" value={verification?.required_checks ?? []} />
              {(verification?.checks ?? []).map((check) => (
                <div key={check.name} className={`rounded-lg border p-3 ${checkCardClass(check)}`}>
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-bold text-slate-900">{check.name}</p>
                    {check.passed ? (
                      <CheckCircle2 className="size-4 text-emerald-600" />
                    ) : check.severity === 'warning' ? (
                      <AlertTriangle className="size-4 text-amber-600" />
                    ) : (
                      <XCircle className="size-4 text-rose-600" />
                    )}
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{check.check_type} · {check.severity ?? 'warning'}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    source {check.source_node ?? check.source_event_type ?? check.source_tool_name ?? 'none'}
                  </p>
                  {check.message && <p className="mt-2 text-xs leading-5 text-slate-600">{check.message}</p>}
                  <p className="mt-2 text-xs text-slate-500">evidence_refs: {check.evidence_refs?.length ?? 0}</p>
                  <details className="mt-2 text-xs text-slate-600">
                    <summary className="cursor-pointer font-bold text-slate-700">expected / actual</summary>
                    <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-words rounded bg-white/70 p-2">
                      {JSON.stringify({ expected: check.expected, actual: check.actual }, null, 2)}
                    </pre>
                  </details>
                </div>
              ))}
              {verification?.checks?.length ? null : <EmptyLine text="No verification checks recorded." />}
            </div>
          </SurfaceCard>

          <SurfaceCard>
            <SectionTitle icon={<Activity className="size-4" />} title="Node Summaries" />
            {nodeSummaries.length ? (
              <div className="mt-4 space-y-2">
                {nodeSummaries.map((node) => (
                  <div key={node.node} className="rounded-lg bg-slate-50 px-3 py-2">
                    <p className="break-all font-mono text-xs font-bold text-slate-900">{node.node}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      events {node.event_count} · tools {node.tool_call_count} · prompts {node.prompt_execution_count}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyLine text="No node summaries available." />
            )}
          </SurfaceCard>

          <SurfaceCard>
            <SectionTitle icon={<Database className="size-4" />} title="Evidence Refs" />
            {evidenceRefs.length ? (
              <div className="mt-4 space-y-2">
                {evidenceRefs.map((ref, index) => (
                  <div key={`${ref.evidence_type}:${ref.evidence_id}:${index}`} className="rounded-lg bg-slate-50 px-3 py-2">
                    <p className="font-mono text-xs font-bold text-slate-900">{ref.evidence_type}:{ref.evidence_id}</p>
                    <p className="mt-1 text-xs text-slate-500">{ref.reason ?? ref.used_by ?? evidenceSource(ref)}</p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyLine text="No evidence refs recorded." />
            )}
          </SurfaceCard>

          <SurfaceCard>
            <SectionTitle icon={<FileJson className="size-4" />} title="Debug Payload" />
            <JsonBlock
              title="summary"
              value={{
                graph_run: graphRun ? omitTrace(graphRun) : trace.graph_run ?? {},
                verification_status: verification?.status,
                prompt_execution_count: promptExecutions.length,
                evidence_ref_count: evidenceRefs.length,
              }}
            />
          </SurfaceCard>
        </aside>
      </section>
    </PageShell>
  )
}

interface TaskSpecLike {
  task_type?: string
  objective?: string
  target?: {
    target_type?: string
    target_id?: string
  }
  allowed_tools?: string[]
  success_criteria?: Record<string, unknown>
  verification_policy?: Record<string, unknown>
}

function SectionTitle({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2 text-sm font-black uppercase tracking-wide text-slate-700">
      {icon}
      <h2>{title}</h2>
    </div>
  )
}

function KeyValue({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="min-w-0 rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-xs font-bold uppercase text-slate-500">{label}</p>
      <p className="mt-1 break-words font-mono text-xs text-slate-900">{value ?? 'none'}</p>
    </div>
  )
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-xs font-bold uppercase text-slate-500">{title}</p>
      <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap break-words text-xs text-slate-700">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}

function StatusPill({ status }: { status: string }) {
  const success = ['success', 'completed', 'passed', 'valid'].includes(status)
  return (
    <span className={`inline-flex rounded-full px-2 py-1 text-xs font-bold ${success ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
      {status}
    </span>
  )
}

function EmptyLine({ text }: { text: string }) {
  return <p className="mt-4 rounded-lg bg-slate-50 px-3 py-3 text-sm text-slate-500">{text}</p>
}

function LangfuseTraceLink({
  traceId,
  label = 'Langfuse',
  compact = false,
}: {
  traceId?: string | null
  label?: string
  compact?: boolean
}) {
  const url = langfuseTraceUrl(traceId)
  if (!traceId || traceId === 'none') return <span>none</span>
  if (!url) return <span>{traceId}</span>
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      className={
        compact
          ? 'inline-flex items-center gap-1 text-cyan-700 underline underline-offset-2'
          : 'inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 shadow-sm transition hover:border-cyan-300 hover:text-cyan-700'
      }
      title={traceId}
    >
      <ExternalLink className="size-4" />
      {compact ? shortHash(traceId) : label}
    </a>
  )
}

function langfuseTraceUrl(traceId?: string | null) {
  const id = traceId?.trim()
  if (!id || id === 'none') return null
  const template = import.meta.env.VITE_LANGFUSE_TRACE_URL_TEMPLATE?.trim()
  if (template) return template.replace('{traceId}', encodeURIComponent(id))
  const base = import.meta.env.VITE_LANGFUSE_BASE_URL?.trim() || 'http://localhost:3100'
  return `${base.replace(/\/$/, '')}/trace/${encodeURIComponent(id)}`
}

function formatDate(value?: string | null) {
  if (!value) return 'none'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function evidenceCount(payload: Record<string, unknown>) {
  const refs = payload.evidence_refs
  return Array.isArray(refs) ? refs.length : 0
}

function payloadSummary(payload: Record<string, unknown>) {
  const entries = Object.entries(payload).filter(([key]) => key !== 'evidence_refs')
  if (!entries.length) return 'empty'
  return entries
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
    .join(' · ')
}

function shortHash(value?: string | null) {
  if (!value) return 'none'
  return value.length > 16 ? `${value.slice(0, 8)}...${value.slice(-6)}` : value
}

function isUuidLike(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
}

function stringValue(value: unknown) {
  if (value === null || value === undefined) return null
  return String(value)
}

function checkCardClass(check: VerificationCheck) {
  if (check.passed) return 'border-emerald-100 bg-emerald-50'
  if (check.severity === 'warning') return 'border-amber-200 bg-amber-50'
  return 'border-rose-200 bg-rose-50'
}

function evidenceSource(ref: EvidenceRef) {
  const source = ref.metadata?.source
  return typeof source === 'string' ? source : 'evidence'
}

function omitTrace(graphRun: GraphRunDebug) {
  const summary: Partial<GraphRunDebug> = { ...graphRun }
  delete summary.trace
  delete summary.events
  delete summary.tool_calls
  return summary
}
