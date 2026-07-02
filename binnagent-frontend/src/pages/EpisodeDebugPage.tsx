import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity,
  CheckCircle2,
  Clock3,
  Database,
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
  expected?: unknown
  actual?: unknown
  evidence_refs?: EvidenceRef[]
  message?: string | null
}

interface VerificationReport {
  episode_id: string
  task_id?: string | null
  status: string
  checks: VerificationCheck[]
  failed_reason?: string | null
  generated_at: string
  metadata?: Record<string, unknown>
}

interface EpisodeTrace {
  episode: RuntimeEpisode
  events: LearningEvent[]
  tool_calls: ToolCallRecord[]
}

export function EpisodeDebugPage({ learner, episodeId }: EpisodeDebugPageProps) {
  const [trace, setTrace] = useState<EpisodeTrace | null>(null)
  const [verification, setVerification] = useState<VerificationReport | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadTrace = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [traceResponse, verificationResponse] = await Promise.all([
        fetch(`/api/runtime/episodes/${episodeId}`),
        fetch(`/api/runtime/episodes/${episodeId}/verification`),
      ])
      if (!traceResponse.ok) throw new Error('Episode trace failed')
      if (!verificationResponse.ok) throw new Error('Episode verification failed')
      const traceData: EpisodeTrace = await traceResponse.json()
      const verificationData: VerificationReport = await verificationResponse.json()
      setTrace(traceData)
      setVerification(verificationData)
    } catch (err) {
      console.error('Episode debug load error:', err)
      setError('Episode trace 暂时无法加载，请确认 episode_id 是否存在。')
    } finally {
      setIsLoading(false)
    }
  }, [episodeId])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadTrace(), 0)
    return () => window.clearTimeout(timer)
  }, [loadTrace])

  const taskSpec = trace?.episode.task_spec as TaskSpecLike | undefined
  const statusTone = trace?.episode.status === 'completed' ? 'success' : trace?.episode.status === 'failed' ? 'danger' : 'neutral'
  const eventTypes = useMemo(() => trace?.events.map((event) => event.event_type).join(' / ') ?? '', [trace])

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
          { label: '验证状态', value: verification?.status ?? 'unknown', tone: verification?.status === 'passed' ? 'success' : 'warning' },
        ]}
        actions={
          <Button variant="secondary" onClick={() => void loadTrace()}>
            <RefreshCw className="size-4" />
            刷新
          </Button>
        }
      />

      <StatusBanner tone={verification?.status === 'passed' ? 'success' : 'warning'} title="VerificationReport">
        {verification?.status === 'passed'
          ? '关键步骤已通过验证。'
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
              {(verification?.checks ?? []).map((check) => (
                <div key={check.name} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-bold text-slate-900">{check.name}</p>
                    {check.passed ? <CheckCircle2 className="size-4 text-emerald-600" /> : <XCircle className="size-4 text-rose-600" />}
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{check.check_type}</p>
                  {check.message && <p className="mt-2 text-xs leading-5 text-slate-600">{check.message}</p>}
                  <p className="mt-2 text-xs text-slate-500">evidence_refs: {check.evidence_refs?.length ?? 0}</p>
                </div>
              ))}
            </div>
          </SurfaceCard>

          <SurfaceCard>
            <SectionTitle icon={<Database className="size-4" />} title="Raw JSON" />
            <details className="mt-4 rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs text-slate-600">
              <summary className="cursor-pointer font-bold text-slate-800">trace + verification</summary>
              <pre className="mt-3 max-h-[520px] overflow-auto whitespace-pre-wrap break-words">
                {JSON.stringify({ trace, verification }, null, 2)}
              </pre>
            </details>
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
  const success = status === 'success' || status === 'completed' || status === 'passed'
  return (
    <span className={`inline-flex rounded-full px-2 py-1 text-xs font-bold ${success ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
      {status}
    </span>
  )
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
