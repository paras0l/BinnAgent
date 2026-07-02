import { useCallback, useEffect, useState } from 'react'
import { Activity, ExternalLink, RefreshCw, Search } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import { debugFetch } from '@/shared/api/debugClient'
import type { Learner } from '@/types'
import { openEpisodeTrace } from './actions'
import type { EpisodeSummary } from './types'

const EPISODE_STATUSES = ['all', 'completed', 'failed', 'waiting_user', 'running'] as const

interface RecentEpisodesPageProps {
  learner: Learner | null
  onEpisodeIdChange: (episodeId: string | null) => void
  navigate: (path: string) => void
}

export function RecentEpisodesPage({
  learner,
  onEpisodeIdChange,
  navigate,
}: RecentEpisodesPageProps) {
  const [learnerId, setLearnerId] = useState(() => initialLearnerId(learner))
  const [status, setStatus] = useState<(typeof EPISODE_STATUSES)[number]>('all')
  const [source, setSource] = useState('')
  const [entrypoint, setEntrypoint] = useState('')
  const [limit, setLimit] = useState(20)
  const [episodes, setEpisodes] = useState<EpisodeSummary[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadEpisodes = useCallback(async (filters: EpisodeFilters) => {
    setIsLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ limit: String(filters.limit) })
      if (filters.learnerId.trim()) params.set('learner_id', filters.learnerId.trim())
      if (filters.status !== 'all') params.set('status', filters.status)
      if (filters.source.trim()) params.set('source', filters.source.trim())
      if (filters.entrypoint.trim()) params.set('entrypoint', filters.entrypoint.trim())
      const response = await debugFetch(`/api/runtime/episodes?${params.toString()}`)
      if (!response.ok) throw new Error('Recent Episodes unavailable')
      const data = await response.json() as { episodes?: EpisodeSummary[]; total?: number }
      setEpisodes(data.episodes ?? [])
      setTotal(data.total ?? 0)
    } catch (err) {
      console.error('Recent Episodes load error:', err)
      setError('Recent Episodes 暂时无法加载，请确认 debug token 和筛选条件。')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    const filters = { learnerId, status, source, entrypoint, limit }
    const timer = window.setTimeout(() => void loadEpisodes(filters), 0)
    return () => window.clearTimeout(timer)
  }, [entrypoint, learnerId, limit, loadEpisodes, source, status])

  const runSearch = () => {
    void loadEpisodes({ learnerId, status, source, entrypoint, limit })
  }

  if (isLoading && episodes.length === 0) {
    return <LoadingState title="正在读取 Recent Episodes" description="正在请求 /api/runtime/episodes..." />
  }
  if (error) {
    return (
      <ErrorState
        title="Recent Episodes 不可用"
        description={error}
        action={<Button variant="secondary" onClick={runSearch}><RefreshCw className="size-4" />重试</Button>}
      />
    )
  }

  return (
    <section className="space-y-4">
      <SurfaceCard>
        <form
          className="grid gap-3 xl:grid-cols-[minmax(0,1.4fr)_160px_minmax(0,1fr)_minmax(0,1fr)_120px_auto_auto]"
          onSubmit={(event) => {
            event.preventDefault()
            runSearch()
          }}
        >
          <FilterField label="learner_id">
            <input
              value={learnerId}
              onChange={(event) => setLearnerId(event.target.value)}
              placeholder="optional learner_id"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm text-slate-900 outline-none focus:border-cyan-400"
            />
          </FilterField>
          <FilterField label="status">
            <select
              value={status}
              onChange={(event) => setStatus(event.target.value as (typeof EPISODE_STATUSES)[number])}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-bold text-slate-900 outline-none focus:border-cyan-400"
            >
              {EPISODE_STATUSES.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </FilterField>
          <FilterField label="source">
            <input
              value={source}
              onChange={(event) => setSource(event.target.value)}
              placeholder="source"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 outline-none focus:border-cyan-400"
            />
          </FilterField>
          <FilterField label="entrypoint">
            <input
              value={entrypoint}
              onChange={(event) => setEntrypoint(event.target.value)}
              placeholder="entrypoint"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 outline-none focus:border-cyan-400"
            />
          </FilterField>
          <FilterField label="limit">
            <input
              value={limit}
              type="number"
              min={1}
              max={100}
              onChange={(event) => setLimit(Number(event.target.value) || 20)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 outline-none focus:border-cyan-400"
            />
          </FilterField>
          <Button type="submit">
            <Search className="size-4" />
            Search
          </Button>
          <Button type="button" variant="secondary" onClick={runSearch}>
            <RefreshCw className="size-4" />
            Refresh
          </Button>
        </form>
        <p className="mt-3 text-xs font-bold text-slate-500">{total} episodes</p>
      </SurfaceCard>

      {episodes.length ? (
        <RecentEpisodesList
          episodes={episodes}
          onOpenTrace={(episode) => openEpisodeTrace(episode, onEpisodeIdChange, navigate)}
        />
      ) : (
        <EmptyState
          icon={<Activity className="size-5" />}
          title="暂无 AgentEpisode"
          description="请先运行一次 Daily Lesson / Knowledge Exercise / Simulation。"
        />
      )}
    </section>
  )
}

export function RecentEpisodesList({
  episodes,
  onOpenTrace,
}: {
  episodes: EpisodeSummary[]
  onOpenTrace: (episode: EpisodeSummary) => void
}) {
  return (
    <SurfaceCard className="overflow-hidden p-0">
      <div className="overflow-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3 font-black">Episode</th>
              <th className="px-4 py-3 font-black">Task</th>
              <th className="px-4 py-3 font-black">Runtime</th>
              <th className="px-4 py-3 font-black">Verification</th>
              <th className="px-4 py-3 font-black">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {episodes.map((episode) => (
              <tr key={episode.id}>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-bold text-slate-950">{episode.status}</p>
                    {episode.status === 'waiting_user' || episode.checkpoint_status === 'waiting_user' ? (
                      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-black text-amber-700">waiting_user</span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{episode.source}</p>
                  <p className="mt-1 break-all font-mono text-xs text-slate-400">{episode.id}</p>
                </td>
                <td className="px-4 py-3">
                  <p className="font-mono text-xs font-bold text-slate-950">{episode.task_type ?? '-'}</p>
                  <p className="mt-1 max-w-sm text-sm leading-6 text-slate-700">{episode.task_objective ?? '-'}</p>
                  <p className="mt-1 break-all font-mono text-xs text-slate-500">
                    {episode.target_type ?? '-'}:{episode.target_id ?? '-'}
                  </p>
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">
                  <p>{episode.learner_nickname ?? episode.learner_id}</p>
                  <p className="mt-1">{episode.entrypoint}</p>
                  <p className="mt-1">checkpoint {episode.checkpoint_status ?? '-'}</p>
                  <p className="mt-1">resume {episode.resume_from ?? '-'}</p>
                  <p className="mt-1">started {formatDateTime(episode.started_at)}</p>
                  <p className="mt-1">completed {formatDateTime(episode.completed_at)}</p>
                  <p className="mt-1 font-mono">events {episode.event_count} · tools {episode.tool_call_count}</p>
                </td>
                <td className="px-4 py-3 text-sm text-slate-700">
                  <p>{episode.verification_status ?? '-'}</p>
                  <p className="mt-1 text-xs text-rose-600">{episode.failure_type ?? ''}</p>
                </td>
                <td className="px-4 py-3">
                  <Button variant="secondary" onClick={() => onOpenTrace(episode)}>
                    <ExternalLink className="size-4" />
                    打开 Trace
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SurfaceCard>
  )
}

interface EpisodeFilters {
  learnerId: string
  status: (typeof EPISODE_STATUSES)[number]
  source: string
  entrypoint: string
  limit: number
}

function FilterField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="min-w-0">
      <span className="text-xs font-bold uppercase text-slate-500">{label}</span>
      <span className="mt-1 block">{children}</span>
    </label>
  )
}

function initialLearnerId(learner: Learner | null) {
  const query = new URLSearchParams(window.location.search)
  return query.get('learner_id')?.trim() || learner?.id || ''
}

function formatDateTime(value?: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}
