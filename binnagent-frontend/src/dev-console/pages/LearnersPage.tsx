import { useCallback, useEffect, useState } from 'react'
import { Eye, RefreshCw, Search, UserCheck, Users } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import { debugFetch } from '@/shared/api/debugClient'
import type { Learner } from '@/types'
import { selectDebugLearner } from './actions'
import type { LearnerDebugSummary } from './types'

interface LearnersPageProps {
  onLearnerChange: (learner: Learner | null) => void
  navigate: (path: string) => void
}

export function LearnersPage({ onLearnerChange, navigate }: LearnersPageProps) {
  const [query, setQuery] = useState('')
  const [learners, setLearners] = useState<LearnerDebugSummary[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadLearners = useCallback(async (nextQuery: string) => {
    setIsLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({ limit: '20' })
      if (nextQuery.trim()) params.set('q', nextQuery.trim())
      const response = await debugFetch(`/api/debug/learners?${params.toString()}`)
      if (!response.ok) throw new Error('Learners unavailable')
      const data = await response.json() as { learners?: LearnerDebugSummary[]; total?: number }
      setLearners(data.learners ?? [])
      setTotal(data.total ?? 0)
    } catch (err) {
      console.error('Learners load error:', err)
      setError('Learners 暂时无法加载，请确认 debug token 和后端配置。')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadLearners(''), 0)
    return () => window.clearTimeout(timer)
  }, [loadLearners])

  const viewEpisodes = (learner: LearnerDebugSummary) => {
    selectDebugLearner(learner, onLearnerChange)
    navigate(`/dev/episodes?learner_id=${encodeURIComponent(learner.id)}`)
  }

  if (isLoading && learners.length === 0) {
    return <LoadingState title="正在读取 Learners" description="正在请求 /api/debug/learners..." />
  }
  if (error) {
    return (
      <ErrorState
        title="Learners 不可用"
        description={error}
        action={<Button variant="secondary" onClick={() => void loadLearners(query)}><RefreshCw className="size-4" />重试</Button>}
      />
    )
  }

  return (
    <section className="space-y-4">
      <SurfaceCard>
        <form
          className="flex flex-col gap-3 lg:flex-row lg:items-end"
          onSubmit={(event) => {
            event.preventDefault()
            void loadLearners(query)
          }}
        >
          <div className="min-w-0 flex-1">
            <label className="text-xs font-bold uppercase text-slate-500" htmlFor="debug-learner-search">
              search learners
            </label>
            <input
              id="debug-learner-search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="nickname or email"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 outline-none focus:border-cyan-400"
            />
          </div>
          <Button type="submit">
            <Search className="size-4" />
            Search
          </Button>
          <Button type="button" variant="secondary" onClick={() => void loadLearners(query)}>
            <RefreshCw className="size-4" />
            Refresh
          </Button>
        </form>
        <p className="mt-3 text-xs font-bold text-slate-500">{total} learners</p>
      </SurfaceCard>

      {learners.length ? (
        <LearnersList
          learners={learners}
          onSelect={(learner) => selectDebugLearner(learner, onLearnerChange)}
          onViewEpisodes={viewEpisodes}
        />
      ) : (
        <EmptyState
          icon={<Users className="size-5" />}
          title="No learners"
          description="当前数据库里还没有 learner，或搜索条件没有匹配结果。"
        />
      )}
    </section>
  )
}

export function LearnersList({
  learners,
  onSelect,
  onViewEpisodes,
}: {
  learners: LearnerDebugSummary[]
  onSelect: (learner: LearnerDebugSummary) => void
  onViewEpisodes: (learner: LearnerDebugSummary) => void
}) {
  return (
    <SurfaceCard className="overflow-hidden p-0">
      <div className="overflow-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3 font-black">Learner</th>
              <th className="px-4 py-3 font-black">Profile</th>
              <th className="px-4 py-3 font-black">Counts</th>
              <th className="px-4 py-3 font-black">Created</th>
              <th className="px-4 py-3 font-black">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {learners.map((learner) => (
              <tr key={learner.id}>
                <td className="px-4 py-3">
                  <p className="font-bold text-slate-950">{learner.nickname}</p>
                  <p className="mt-1 text-xs text-slate-500">{learner.email ?? '-'}</p>
                  <p className="mt-1 break-all font-mono text-xs text-slate-400">{learner.id}</p>
                </td>
                <td className="px-4 py-3 text-slate-700">
                  <p>{learner.profile?.target_exam ?? '-'}</p>
                  <p className="mt-1 text-xs text-slate-500">{learner.profile?.current_level ?? '-'}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {learner.profile?.daily_time_budget_minutes
                      ? `${learner.profile.daily_time_budget_minutes} min/day`
                      : '-'}
                  </p>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-slate-600">
                  <p>episodes {learner.counts.episode_count}</p>
                  <p>memory {learner.counts.memory_event_count}</p>
                  <p>exercises {learner.counts.exercise_attempt_count}</p>
                  <p>vocabulary {learner.counts.vocabulary_count}</p>
                </td>
                <td className="px-4 py-3 text-xs text-slate-500">{formatDateTime(learner.created_at)}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" onClick={() => onSelect(learner)}>
                      <UserCheck className="size-4" />
                      设为当前 learner
                    </Button>
                    <Button variant="secondary" onClick={() => onViewEpisodes(learner)}>
                      <Eye className="size-4" />
                      查看 Episodes
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SurfaceCard>
  )
}

function formatDateTime(value?: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}
