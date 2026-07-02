import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import {
  Activity,
  BrainCircuit,
  Database,
  FileJson,
  FlaskConical,
  KeyRound,
  LockKeyhole,
  RefreshCw,
  Route,
  Search,
  ShieldCheck,
  TerminalSquare,
  Users,
  Wrench,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { StatusBanner } from '@/components/ui/StatusBanner'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import { clearDebugToken, debugFetch, readDebugToken, saveDebugToken } from '@/shared/api/debugClient'
import type { Learner } from '@/types'
import { LearnersPage } from './pages/LearnersPage'
import { RecentEpisodesPage } from './pages/RecentEpisodesPage'
import { devConsoleRoutes, findDevConsoleRoute, type DevConsoleRouteId } from './routes'

const MemoryCenterPage = lazy(() =>
  import('@/pages/MemoryCenterPage').then((module) => ({ default: module.MemoryCenterPage }))
)

const EpisodeDebugPage = lazy(() =>
  import('@/pages/EpisodeDebugPage').then((module) => ({ default: module.EpisodeDebugPage }))
)

const DEV_LEARNER_ID_KEY = 'BINNAGENT_DEV_LEARNER_ID'
const DEV_LEARNER_NAME_KEY = 'BINNAGENT_DEV_LEARNER_NAME'

interface ToolSpec {
  name: string
  description?: string
  input_schema?: unknown
  output_schema?: unknown
}

interface ToolCallRecord {
  id?: string
  tool_name?: string
  name?: string
  status?: string
  latency_ms?: number
  duration_ms?: number
  input_hash?: string
  output_hash?: string
  error?: string | null
  [key: string]: unknown
}

interface EpisodeTrace {
  episode?: {
    id?: string
    status?: string
  }
  tool_calls?: ToolCallRecord[]
}

interface RagDebugResult {
  chunk_id: string
  source_id: string
  curriculum_node_id?: string | null
  page_number?: number
  score?: number
  retrieval_mode?: string
  content_preview?: string
  metadata?: Record<string, unknown>
}

interface RagDebugResponse {
  query: string
  retrieval_mode: string
  embedding_model?: string | null
  chunk_version?: string | null
  result_count: number
  results: RagDebugResult[]
}

interface SimulationScenario {
  id: string
  name: string
  persona_id: string
  step_count: number
}

interface SimulationLatestReport {
  path: string
  report: Record<string, unknown>
  summary: {
    status?: string
    episode_count?: number
    completed_episode_count?: number
    failed_episode_count?: number
    verification_pass_count?: number
    verification_fail_count?: number
    avg_tool_latency_ms?: number
    failed_assertions?: string[]
    failed_assertion_count?: number
    step_count?: number
    passed_step_count?: number
    failed_step_count?: number
  }
}

function DevConsoleApp() {
  const [token, setToken] = useState(() => readDebugToken())

  if (!token) {
    return <TokenSetup onSaved={() => setToken(readDebugToken())} />
  }

  return (
    <DevConsoleShell
      onClearToken={() => {
        clearDebugToken()
        setToken(null)
      }}
    />
  )
}

export default DevConsoleApp

function DevConsoleShell({ onClearToken }: { onClearToken: () => void }) {
  const [routeId, setRouteId] = useState<DevConsoleRouteId>(() => routeIdFromLocation())
  const [learner, setLearner] = useState<Learner | null>(() => readLearnerContext())
  const [episodeId, setEpisodeId] = useState<string | null>(() => readEpisodeIdFromLocation())

  useEffect(() => {
    const handleLocationChange = () => {
      setRouteId(routeIdFromLocation())
      setEpisodeId(readEpisodeIdFromLocation())
    }
    window.addEventListener('popstate', handleLocationChange)
    return () => window.removeEventListener('popstate', handleLocationChange)
  }, [])

  const activeRoute = devConsoleRoutes.find((route) => route.id === routeId) ?? devConsoleRoutes[0]
  const debugLearner = learner ?? { id: 'dev-console', nickname: 'Dev Console', email: null }

  const navigate = (path: string) => {
    window.history.pushState({}, '', path)
    setRouteId(routeIdFromLocation())
    setEpisodeId(readEpisodeIdFromLocation())
  }

  const updateLearner = (nextLearner: Learner | null) => {
    if (nextLearner) {
      localStorage.setItem(DEV_LEARNER_ID_KEY, nextLearner.id)
      localStorage.setItem(DEV_LEARNER_NAME_KEY, nextLearner.nickname)
    } else {
      localStorage.removeItem(DEV_LEARNER_ID_KEY)
      localStorage.removeItem(DEV_LEARNER_NAME_KEY)
    }
    setLearner(nextLearner)
  }

  const updateEpisodeId = (nextEpisodeId: string | null) => {
    setEpisodeId(nextEpisodeId)
    if (routeId === 'episodes' && nextEpisodeId) {
      window.history.pushState({}, '', `/runtime/episodes/${encodeURIComponent(nextEpisodeId)}`)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-slate-800 bg-slate-950/95 px-4 py-5 lg:block">
        <div className="flex items-center gap-3 px-2">
          <TerminalSquare className="size-6 text-cyan-300" />
          <div>
            <p className="text-sm font-black uppercase tracking-wide text-white">BinnAgent</p>
            <p className="text-xs text-slate-400">Dev Console</p>
          </div>
        </div>
        <nav className="mt-8 space-y-1">
          {devConsoleRoutes.map((route) => (
            <button
              key={route.id}
              type="button"
              onClick={() => navigate(route.path)}
              className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-bold transition ${
                activeRoute.id === route.id
                  ? 'bg-cyan-400 text-slate-950'
                  : 'text-slate-300 hover:bg-slate-900 hover:text-white'
              }`}
            >
              {routeIcon(route.id)}
              {route.label}
            </button>
          ))}
        </nav>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-40 border-b border-slate-800 bg-slate-950/90 px-4 py-4 backdrop-blur lg:px-8">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-wide text-cyan-300">{activeRoute.label}</p>
              <h1 className="mt-1 text-2xl font-black text-white">Agent Runtime Harness</h1>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" onClick={onClearToken}>
                <LockKeyhole className="size-4" />
                清除 Token
              </Button>
            </div>
          </div>
          <div className="mt-4 lg:hidden">
            <select
              value={activeRoute.id}
              onChange={(event) => {
                const route = devConsoleRoutes.find((item) => item.id === event.target.value)
                if (route) navigate(route.path)
              }}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm font-bold text-white"
            >
              {devConsoleRoutes.map((route) => (
                <option key={route.id} value={route.id}>{route.label}</option>
              ))}
            </select>
          </div>
          <ContextBar
            key={`${learner?.id ?? 'no-learner'}:${episodeId ?? 'no-episode'}`}
            learner={learner}
            episodeId={episodeId}
            onLearnerChange={updateLearner}
            onEpisodeIdChange={updateEpisodeId}
          />
        </header>

        <main className="px-4 py-6 lg:px-8">
          <Suspense fallback={<LoadingState title="正在打开 Dev Console" description="正在加载调试面板..." />}>
            {routeId === 'learners' ? (
              <LearnersPage onLearnerChange={updateLearner} navigate={navigate} />
            ) : routeId === 'memory' ? (
              learner ? (
                <MemoryCenterPage learner={learner} />
              ) : (
                <ContextRequired title="Memory Debug 需要 learner_id" />
              )
            ) : routeId === 'episodes' ? (
              episodeId ? (
                <EpisodeDebugPage learner={debugLearner} episodeId={episodeId} />
              ) : (
                <RecentEpisodesPage
                  key={`${learner?.id ?? 'all'}:${window.location.search}`}
                  learner={learner}
                  onEpisodeIdChange={updateEpisodeId}
                  navigate={navigate}
                />
              )
            ) : routeId === 'tools' ? (
              <ToolRegistryPage />
            ) : routeId === 'tool-call-records' ? (
              episodeId ? (
                <ToolCallRecordsPage key={episodeId} episodeId={episodeId} />
              ) : (
                <ContextRequired title="Tool Call Records 需要 episode_id" />
              )
            ) : routeId === 'evidence' ? (
              <EvidenceDebugPage />
            ) : routeId === 'rag' ? (
              <RagDebugPage key={learner?.id ?? 'rag'} learner={learner} />
            ) : routeId === 'prompt' ? (
              <PromptDebugPage />
            ) : routeId === 'verification' ? (
              <VerificationReportPage
                key={episodeId ?? 'verification'}
                episodeId={episodeId}
                onEpisodeIdChange={updateEpisodeId}
              />
            ) : (
              <SimulationReportPage />
            )}
          </Suspense>
        </main>
      </div>
    </div>
  )
}

function TokenSetup({ onSaved }: { onSaved: () => void }) {
  const [token, setToken] = useState('')

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 p-4 text-slate-100">
      <form
        onSubmit={(event) => {
          event.preventDefault()
          saveDebugToken(token)
          onSaved()
        }}
        className="w-full max-w-md rounded-lg border border-slate-800 bg-slate-900 p-6 shadow-xl"
      >
        <div className="flex items-center gap-3">
          <KeyRound className="size-6 text-cyan-300" />
          <div>
            <h1 className="text-xl font-black text-white">Dev Console Token</h1>
            <p className="mt-1 text-sm text-slate-400">需要 DEBUG_CONSOLE_TOKEN 才会请求内部 API。</p>
          </div>
        </div>
        <input
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="例如 dev"
          className="mt-5 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300"
        />
        <Button className="mt-4 w-full justify-center" disabled={!token.trim()}>
          保存并进入
        </Button>
      </form>
    </div>
  )
}

function ContextBar({
  learner,
  episodeId,
  onLearnerChange,
  onEpisodeIdChange,
}: {
  learner: Learner | null
  episodeId: string | null
  onLearnerChange: (learner: Learner | null) => void
  onEpisodeIdChange: (episodeId: string | null) => void
}) {
  const [learnerIdDraft, setLearnerIdDraft] = useState(learner?.id ?? '')
  const [learnerNameDraft, setLearnerNameDraft] = useState(learner?.nickname ?? 'Dev Learner')
  const [episodeIdDraft, setEpisodeIdDraft] = useState(episodeId ?? '')

  return (
    <div className="mt-4 grid gap-3 rounded-lg border border-slate-800 bg-slate-900/70 p-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_160px_auto_auto]">
        <input
          value={learnerIdDraft}
          onChange={(event) => setLearnerIdDraft(event.target.value)}
          placeholder="learner_id for Memory Debug"
          className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300"
        />
        <input
          value={learnerNameDraft}
          onChange={(event) => setLearnerNameDraft(event.target.value)}
          placeholder="nickname"
          className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300"
        />
        <Button
          type="button"
          variant="secondary"
          onClick={() => {
            const learnerId = learnerIdDraft.trim()
            if (learnerId) onLearnerChange({ id: learnerId, nickname: learnerNameDraft.trim() || 'Dev Learner' })
          }}
        >
          保存 learner
        </Button>
        <Button type="button" variant="secondary" onClick={() => onLearnerChange(null)}>
          清除
        </Button>
      </div>
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
        <input
          value={episodeIdDraft}
          onChange={(event) => setEpisodeIdDraft(event.target.value)}
          placeholder="episode_id for Episode / Verification"
          className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300"
        />
        <Button
          type="button"
          variant="secondary"
          onClick={() => onEpisodeIdChange(episodeIdDraft.trim() || null)}
        >
          保存 episode
        </Button>
      </div>
    </div>
  )
}

function ToolRegistryPage() {
  const [tools, setTools] = useState<ToolSpec[] | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadTools = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await debugFetch('/api/tools')
      if (!response.ok) throw new Error('Tool Registry unavailable')
      setTools(await response.json() as ToolSpec[])
    } catch (err) {
      console.error('Tool Registry load error:', err)
      setError('Tool Registry 暂时无法加载。')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadTools(), 0)
    return () => window.clearTimeout(timer)
  }, [loadTools])

  if (isLoading && !tools) return <LoadingState title="正在读取 Tool Registry" description="正在请求 /api/tools..." />
  if (error) {
    return (
      <ErrorState
        title="Tool Registry 不可用"
        description={error}
        action={<Button variant="secondary" onClick={() => void loadTools()}><RefreshCw className="size-4" />重试</Button>}
      />
    )
  }

  return (
    <section className="grid gap-4 xl:grid-cols-2">
      {(tools ?? []).map((tool) => (
        <SurfaceCard key={tool.name}>
          <div className="flex items-start gap-3">
            <Wrench className="mt-1 size-5 text-cyan-300" />
            <div className="min-w-0">
              <h2 className="break-words font-mono text-sm font-black text-slate-950">{tool.name}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">{tool.description ?? 'No description'}</p>
              <pre className="mt-3 max-h-48 overflow-auto rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                {JSON.stringify({ input_schema: tool.input_schema, output_schema: tool.output_schema }, null, 2)}
              </pre>
            </div>
          </div>
        </SurfaceCard>
      ))}
    </section>
  )
}

function ToolCallRecordsPage({ episodeId }: { episodeId: string }) {
  const [trace, setTrace] = useState<EpisodeTrace | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadTrace = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await debugFetch(`/api/runtime/episodes/${encodeURIComponent(episodeId)}`)
      if (!response.ok) throw new Error('Tool call records unavailable')
      setTrace(await response.json() as EpisodeTrace)
    } catch (err) {
      console.error('Tool Call Records load error:', err)
      setError('Tool Call Records 暂时无法加载，请确认 episode_id 和 token。')
    } finally {
      setIsLoading(false)
    }
  }, [episodeId])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadTrace(), 0)
    return () => window.clearTimeout(timer)
  }, [loadTrace])

  if (isLoading && !trace) {
    return <LoadingState title="正在读取 Tool Call Records" description="正在请求 episode trace..." />
  }
  if (error) {
    return (
      <ErrorState
        title="Tool Call Records 不可用"
        description={error}
        action={<Button variant="secondary" onClick={() => void loadTrace()}><RefreshCw className="size-4" />重试</Button>}
      />
    )
  }

  const calls = trace?.tool_calls ?? []

  return (
    <section className="space-y-4">
      <SurfaceCard>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-black text-slate-950">Tool Call Records</h2>
            <p className="mt-1 break-all font-mono text-xs text-slate-500">{episodeId}</p>
          </div>
          <Button variant="secondary" onClick={() => void loadTrace()}>
            <RefreshCw className="size-4" />
            Refresh
          </Button>
        </div>
      </SurfaceCard>

      {calls.length ? (
        <SurfaceCard className="overflow-hidden p-0">
          <div className="overflow-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-black">Tool</th>
                  <th className="px-4 py-3 font-black">Status</th>
                  <th className="px-4 py-3 font-black">Latency</th>
                  <th className="px-4 py-3 font-black">Input</th>
                  <th className="px-4 py-3 font-black">Output</th>
                  <th className="px-4 py-3 font-black">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {calls.map((call, index) => {
                  const latency = typeof call.latency_ms === 'number'
                    ? call.latency_ms
                    : typeof call.duration_ms === 'number'
                      ? call.duration_ms
                      : null
                  return (
                    <tr key={call.id ?? `${index}:${call.tool_name ?? call.name ?? 'tool'}`}>
                      <td className="px-4 py-3 font-mono text-xs font-bold text-slate-950">
                        {call.tool_name ?? call.name ?? 'unknown'}
                      </td>
                      <td className="px-4 py-3 text-slate-700">{call.status ?? 'unknown'}</td>
                      <td className="px-4 py-3 text-slate-700">
                        {latency === null ? '-' : `${Math.round(latency)} ms`}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">{call.input_hash ?? '-'}</td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">{call.output_hash ?? '-'}</td>
                      <td className="max-w-xs px-4 py-3 text-rose-600">{call.error ?? '-'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </SurfaceCard>
      ) : (
        <EmptyState
          icon={<Wrench className="size-5" />}
          title="No tool calls"
          description="这个 episode trace 里还没有记录 tool_calls。"
        />
      )}

      <RawJsonPanel title="Raw episode trace" data={trace} />
    </section>
  )
}

function RagDebugPage({ learner }: { learner: Learner | null }) {
  const [learnerId, setLearnerId] = useState(learner?.id ?? '')
  const [query, setQuery] = useState('')
  const [sourceId, setSourceId] = useState('')
  const [nodeId, setNodeId] = useState('')
  const [result, setResult] = useState<RagDebugResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const search = async () => {
    const trimmedQuery = query.trim()
    if (!trimmedQuery) return
    const params = new URLSearchParams({ query: trimmedQuery })
    if (learnerId.trim()) params.set('learner_id', learnerId.trim())
    if (sourceId.trim()) params.set('source_id', sourceId.trim())
    if (nodeId.trim()) params.set('node_id', nodeId.trim())

    setIsLoading(true)
    setError(null)
    setResult(null)
    try {
      const response = await debugFetch(`/api/debug/rag/search?${params.toString()}`)
      if (!response.ok) throw new Error('RAG search failed')
      setResult(await response.json() as RagDebugResponse)
    } catch (err) {
      console.error('RAG Debug search error:', err)
      setError('RAG Debug 搜索失败，请检查 query、过滤条件和 token。')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <section className="space-y-4">
      <SurfaceCard>
        <div className="flex items-center gap-2">
          <Database className="size-5 text-cyan-500" />
          <h2 className="text-lg font-black text-slate-950">RAG Debug</h2>
        </div>
        <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <input
            value={learnerId}
            onChange={(event) => setLearnerId(event.target.value)}
            placeholder="learner_id"
            className="rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm text-slate-900 outline-none focus:border-cyan-400"
          />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="query"
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 outline-none focus:border-cyan-400"
          />
          <input
            value={sourceId}
            onChange={(event) => setSourceId(event.target.value)}
            placeholder="source_id optional"
            className="rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm text-slate-900 outline-none focus:border-cyan-400"
          />
          <input
            value={nodeId}
            onChange={(event) => setNodeId(event.target.value)}
            placeholder="node_id optional"
            className="rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm text-slate-900 outline-none focus:border-cyan-400"
          />
        </div>
        <Button className="mt-4" onClick={() => void search()} disabled={!query.trim() || isLoading}>
          <Search className="size-4" />
          {isLoading ? 'Searching...' : 'Search'}
        </Button>
        {error ? <StatusBanner tone="warning" title="Request failed">{error}</StatusBanner> : null}
      </SurfaceCard>

      {result ? (
        <>
          <SurfaceCard>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <MetricBlock label="mode" value={result.retrieval_mode} />
              <MetricBlock label="result count" value={String(result.result_count)} />
              <MetricBlock label="embedding model" value={result.embedding_model ?? '-'} />
              <MetricBlock label="chunk version" value={result.chunk_version ?? '-'} />
            </div>
          </SurfaceCard>
          <section className="grid gap-4 xl:grid-cols-2">
            {result.results.map((chunk) => (
              <SurfaceCard key={chunk.chunk_id}>
                <div className="flex flex-wrap items-center gap-2 text-xs font-bold text-slate-500">
                  <span>page {chunk.page_number ?? '-'}</span>
                  <span>score {formatScore(chunk.score)}</span>
                  <span>{chunk.retrieval_mode ?? result.retrieval_mode}</span>
                </div>
                <p className="mt-3 break-words text-sm leading-6 text-slate-700">{chunk.content_preview}</p>
                <div className="mt-3 space-y-1 font-mono text-xs text-slate-500">
                  <p className="break-all">source_id: {chunk.source_id}</p>
                  <p className="break-all">chunk_id: {chunk.chunk_id}</p>
                  {chunk.curriculum_node_id ? (
                    <p className="break-all">node_id: {chunk.curriculum_node_id}</p>
                  ) : null}
                </div>
              </SurfaceCard>
            ))}
          </section>
          <RawJsonPanel title="Raw RAG JSON" data={result} />
        </>
      ) : null}
    </section>
  )
}

function EvidenceDebugPage() {
  const [refsText, setRefsText] = useState('[\n  { "evidence_type": "knowledge_point", "evidence_id": "" }\n]')
  const [result, setResult] = useState<unknown>(null)
  const [error, setError] = useState<string | null>(null)

  const resolveEvidence = async () => {
    setError(null)
    setResult(null)
    try {
      const refs = JSON.parse(refsText)
      const response = await debugFetch('/api/evidence/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refs }),
      })
      if (!response.ok) throw new Error('Evidence resolve failed')
      setResult(await response.json())
    } catch (err) {
      console.error('Evidence debug error:', err)
      setError('Evidence Debug 请求失败，请检查 JSON 和 token。')
    }
  }

  return (
    <DebugFormShell
      icon={<Search className="size-5" />}
      title="Evidence Debug"
      actionLabel="Resolve Evidence"
      onSubmit={() => void resolveEvidence()}
      error={error}
      result={result}
    >
      <textarea
        value={refsText}
        onChange={(event) => setRefsText(event.target.value)}
        rows={8}
        className="w-full rounded-lg border border-slate-200 p-3 font-mono text-sm text-slate-900 outline-none focus:border-cyan-400"
      />
    </DebugFormShell>
  )
}

function PromptDebugPage() {
  const [promptId, setPromptId] = useState('grammar.micro_lesson.structured')
  const [variablesText, setVariablesText] = useState('{\n  "topic_title": "一般现在时",\n  "learner_level": "grade-7"\n}')
  const [result, setResult] = useState<unknown>(null)
  const [error, setError] = useState<string | null>(null)

  const renderPrompt = async () => {
    setError(null)
    setResult(null)
    try {
      const variables = JSON.parse(variablesText)
      const response = await debugFetch(`/api/prompts/${promptId}/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ variables }),
      })
      if (!response.ok) throw new Error('Prompt render failed')
      setResult(await response.json())
    } catch (err) {
      console.error('Prompt debug error:', err)
      setError('Prompt Debug 请求失败，请检查 prompt_id、变量 JSON 和 token。')
    }
  }

  return (
    <DebugFormShell
      icon={<FileJson className="size-5" />}
      title="Prompt Debug"
      actionLabel="Render Prompt"
      onSubmit={() => void renderPrompt()}
      error={error}
      result={result}
    >
      <input
        value={promptId}
        onChange={(event) => setPromptId(event.target.value)}
        className="mb-3 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm text-slate-900 outline-none focus:border-cyan-400"
      />
      <textarea
        value={variablesText}
        onChange={(event) => setVariablesText(event.target.value)}
        rows={8}
        className="w-full rounded-lg border border-slate-200 p-3 font-mono text-sm text-slate-900 outline-none focus:border-cyan-400"
      />
    </DebugFormShell>
  )
}

function VerificationReportPage({
  episodeId,
  onEpisodeIdChange,
}: {
  episodeId: string | null
  onEpisodeIdChange: (episodeId: string | null) => void
}) {
  const [draft, setDraft] = useState(episodeId ?? '')
  const [result, setResult] = useState<unknown>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchReport = async () => {
    const nextEpisodeId = draft.trim()
    if (!nextEpisodeId) return
    onEpisodeIdChange(nextEpisodeId)
    setError(null)
    setResult(null)
    try {
      const response = await debugFetch(`/api/runtime/episodes/${nextEpisodeId}/verification`)
      if (!response.ok) throw new Error('Verification report failed')
      setResult(await response.json())
    } catch (err) {
      console.error('Verification debug error:', err)
      setError('VerificationReport 请求失败，请确认 episode_id 和 token。')
    }
  }

  return (
    <DebugFormShell
      icon={<ShieldCheck className="size-5" />}
      title="VerificationReport"
      actionLabel="Fetch Report"
      onSubmit={() => void fetchReport()}
      error={error}
      result={result}
    >
      <input
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder="episode_id"
        className="w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm text-slate-900 outline-none focus:border-cyan-400"
      />
    </DebugFormShell>
  )
}

function SimulationReportPage() {
  const [scenarios, setScenarios] = useState<SimulationScenario[]>([])
  const [latestReport, setLatestReport] = useState<SimulationLatestReport | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [reportMissing, setReportMissing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSimulationState = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [scenariosResponse, reportResponse] = await Promise.all([
        debugFetch('/api/debug/simulation/scenarios'),
        debugFetch('/api/debug/simulation/reports/latest'),
      ])
      if (!scenariosResponse.ok) throw new Error('Simulation scenarios unavailable')
      const scenariosData = await scenariosResponse.json() as { scenarios?: SimulationScenario[] }
      setScenarios(scenariosData.scenarios ?? [])
      if (reportResponse.status === 404) {
        setLatestReport(null)
        setReportMissing(true)
      } else {
        if (!reportResponse.ok) throw new Error('Latest simulation report unavailable')
        setLatestReport(await reportResponse.json() as SimulationLatestReport)
        setReportMissing(false)
      }
    } catch (err) {
      console.error('Simulation Report load error:', err)
      setError('Simulation Report 暂时无法加载，请确认 debug token 和后端配置。')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadSimulationState(), 0)
    return () => window.clearTimeout(timer)
  }, [loadSimulationState])

  if (isLoading && scenarios.length === 0 && !latestReport) {
    return <LoadingState title="正在读取 Simulation Report" description="正在请求 simulation artifacts..." />
  }
  if (error) {
    return (
      <ErrorState
        title="Simulation Report 不可用"
        description={error}
        action={<Button variant="secondary" onClick={() => void loadSimulationState()}><RefreshCw className="size-4" />重试</Button>}
      />
    )
  }

  const summary = latestReport?.summary
  const failedAssertions = summary?.failed_assertions ?? []

  return (
    <section className="space-y-4">
      <SurfaceCard>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <FlaskConical className="size-5 text-cyan-500" />
            <div>
              <h2 className="text-lg font-black text-slate-950">Simulation Report</h2>
              {latestReport ? <p className="mt-1 break-all font-mono text-xs text-slate-500">{latestReport.path}</p> : null}
            </div>
          </div>
          <Button variant="secondary" onClick={() => void loadSimulationState()}>
            <RefreshCw className="size-4" />
            Refresh
          </Button>
        </div>
      </SurfaceCard>

      {latestReport && summary ? (
        <SurfaceCard>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricBlock label="latest run status" value={summary.status ?? 'unknown'} />
            <MetricBlock label="episode_count" value={String(summary.episode_count ?? 0)} />
            <MetricBlock label="completed_episode_count" value={String(summary.completed_episode_count ?? 0)} />
            <MetricBlock label="failed_episode_count" value={String(summary.failed_episode_count ?? 0)} />
            <MetricBlock label="verification_pass_count" value={String(summary.verification_pass_count ?? 0)} />
            <MetricBlock label="verification_fail_count" value={String(summary.verification_fail_count ?? 0)} />
            <MetricBlock label="avg_tool_latency_ms" value={String(Math.round(summary.avg_tool_latency_ms ?? 0))} />
            <MetricBlock label="failed assertions" value={String(summary.failed_assertion_count ?? 0)} />
          </div>
        </SurfaceCard>
      ) : reportMissing ? (
        <EmptyState
          icon={<FlaskConical className="size-5" />}
          title="No simulation report"
          description="还没有找到 var/simulation/latest_report.json。运行 ./scripts/run_learner_simulation.sh --persona grade7_low_vocab --scenario smoke_learning_journey 后刷新。"
        />
      ) : null}

      <SurfaceCard>
        <h3 className="text-base font-black text-slate-950">Scenarios</h3>
        <div className="mt-3 grid gap-3 xl:grid-cols-2">
          {scenarios.map((scenario) => (
            <div key={scenario.id} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
              <p className="font-mono text-xs font-black text-slate-950">{scenario.id}</p>
              <p className="mt-1 text-sm font-bold text-slate-700">{scenario.name}</p>
              <p className="mt-1 text-xs text-slate-500">
                {scenario.persona_id} · {scenario.step_count} steps
              </p>
            </div>
          ))}
        </div>
      </SurfaceCard>

      {failedAssertions.length ? (
        <SurfaceCard>
          <h3 className="text-base font-black text-slate-950">Failed Assertions</h3>
          <ul className="mt-3 space-y-2 text-sm text-rose-700">
            {failedAssertions.map((failure, index) => (
              <li key={`${index}:${failure}`} className="rounded-lg bg-rose-50 px-3 py-2">{failure}</li>
            ))}
          </ul>
        </SurfaceCard>
      ) : null}

      {latestReport ? <RawJsonPanel title="Raw Simulation JSON" data={latestReport.report} /> : null}
    </section>
  )
}

function MetricBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
      <p className="text-xs font-bold uppercase text-slate-500">{label}</p>
      <p className="mt-1 break-words font-mono text-sm font-black text-slate-950">{value}</p>
    </div>
  )
}

function RawJsonPanel({ title, data }: { title: string; data: unknown }) {
  return (
    <details className="rounded-lg border border-slate-200 bg-white p-4">
      <summary className="cursor-pointer text-sm font-black text-slate-950">{title}</summary>
      <pre className="mt-4 max-h-[520px] overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-100">
        {JSON.stringify(data, null, 2)}
      </pre>
    </details>
  )
}

function formatScore(score?: number) {
  if (typeof score !== 'number') return '-'
  return score.toFixed(3)
}

function DebugFormShell({
  icon,
  title,
  actionLabel,
  onSubmit,
  error,
  result,
  children,
}: {
  icon: React.ReactNode
  title: string
  actionLabel: string
  onSubmit: () => void
  error: string | null
  result: unknown
  children: React.ReactNode
}) {
  return (
    <SurfaceCard>
      <div className="flex items-center gap-2">
        {icon}
        <h2 className="text-lg font-black text-slate-950">{title}</h2>
      </div>
      <div className="mt-4">{children}</div>
      <Button className="mt-4" onClick={onSubmit}>{actionLabel}</Button>
      {error ? <StatusBanner tone="warning" title="Request failed">{error}</StatusBanner> : null}
      {result ? (
        <pre className="mt-4 max-h-[520px] overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-100">
          {JSON.stringify(result, null, 2)}
        </pre>
      ) : null}
    </SurfaceCard>
  )
}

function ContextRequired({ title }: { title: string }) {
  return (
    <PlaceholderPanel
      icon={<Route className="size-5" />}
      title={title}
      description="请先在顶部上下文栏保存对应 ID，然后再打开这个调试面板。"
    />
  )
}

function PlaceholderPanel({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <SurfaceCard>
      <div className="flex items-center gap-2">
        {icon}
        <h2 className="text-lg font-black text-slate-950">{title}</h2>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{description}</p>
    </SurfaceCard>
  )
}

function routeIdFromLocation() {
  return findDevConsoleRoute(window.location.pathname).id
}

function readEpisodeIdFromLocation() {
  const pathMatch = window.location.pathname.match(/\/runtime\/episodes\/([^/]+)/)
  if (pathMatch?.[1]) return decodeURIComponent(pathMatch[1])
  const query = new URLSearchParams(window.location.search)
  return query.get('episode_id')?.trim() || null
}

function readLearnerContext(): Learner | null {
  const id = localStorage.getItem(DEV_LEARNER_ID_KEY)?.trim()
  if (!id) return null
  return {
    id,
    nickname: localStorage.getItem(DEV_LEARNER_NAME_KEY)?.trim() || 'Dev Learner',
  }
}

function routeIcon(routeId: DevConsoleRouteId) {
  if (routeId === 'learners') return <Users className="size-4" />
  if (routeId === 'memory') return <BrainCircuit className="size-4" />
  if (routeId === 'episodes') return <Activity className="size-4" />
  if (routeId === 'tools') return <Wrench className="size-4" />
  if (routeId === 'tool-call-records') return <Activity className="size-4" />
  if (routeId === 'evidence') return <Search className="size-4" />
  if (routeId === 'rag') return <Database className="size-4" />
  if (routeId === 'prompt') return <FileJson className="size-4" />
  if (routeId === 'verification') return <ShieldCheck className="size-4" />
  return <FlaskConical className="size-4" />
}
