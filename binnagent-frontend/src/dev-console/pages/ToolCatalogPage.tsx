import { useCallback, useEffect, useState } from 'react'
import { PauseCircle, PlayCircle, RefreshCw, Search, Wrench } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { StatusBanner } from '@/components/ui/StatusBanner'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import { debugFetch } from '@/shared/api/debugClient'

interface ToolSpec {
  name: string
  version: string
  description: string
  source: 'internal' | 'mcp'
  provider_ref: string
  enabled: boolean
  health_status: 'healthy' | 'degraded' | 'unavailable' | 'disabled'
  spec_hash?: string | null
  risk_level: string
  timeout_ms: number
  idempotency: string
  input_schema: unknown
  output_schema: unknown
  last_health_check_at?: string | null
}

interface ToolCatalog {
  revision: string
  generation: number
  created_at: string
  refreshed_at: string
  tool_count: number
  enabled_count: number
  healthy_count: number
  degraded_count: number
  unavailable_count: number
  disabled_count: number
  refresh_count: number
  failed_refresh_count: number
  last_refresh_error?: string | null
  tools: ToolSpec[]
}

interface ResolutionItem {
  name: string
  version: string
  allowed: boolean
  reason: string
}

export function ToolCatalogPage() {
  const [catalog, setCatalog] = useState<ToolCatalog | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isMutating, setIsMutating] = useState(false)
  const [autoMonitor, setAutoMonitor] = useState(true)
  const [allowlistDraft, setAllowlistDraft] = useState('exercise.grade, memory.write')
  const [resolution, setResolution] = useState<ResolutionItem[] | null>(null)

  const loadCatalog = useCallback(async (quiet = false) => {
    if (!quiet) setIsLoading(true)
    setError(null)
    try {
      const response = await debugFetch('/api/tools/catalog')
      if (!response.ok) throw new Error('Tool Catalog unavailable')
      setCatalog(await response.json() as ToolCatalog)
    } catch (loadError) {
      console.error('Tool Catalog load error:', loadError)
      setError('Tool Catalog 暂时无法加载。')
    } finally {
      if (!quiet) setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadCatalog(), 0)
    return () => window.clearTimeout(timer)
  }, [loadCatalog])

  useEffect(() => {
    if (!autoMonitor) return undefined
    const timer = window.setInterval(() => void loadCatalog(true), 15_000)
    return () => window.clearInterval(timer)
  }, [autoMonitor, loadCatalog])

  const mutate = useCallback(async (path: string) => {
    setIsMutating(true)
    setError(null)
    try {
      const response = await debugFetch(path, { method: 'POST' })
      if (!response.ok) throw new Error(`Tool operation failed: ${response.status}`)
      await loadCatalog(true)
    } catch (mutationError) {
      console.error('Tool Catalog mutation error:', mutationError)
      setError('Tool 生命周期操作失败，请检查后端日志。')
    } finally {
      setIsMutating(false)
    }
  }, [loadCatalog])

  const resolveAllowlist = useCallback(async () => {
    const allowedTools = allowlistDraft.split(',').map((item) => item.trim()).filter(Boolean)
    setIsMutating(true)
    try {
      const response = await debugFetch('/api/tools/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ allowed_tools: allowedTools }),
      })
      if (!response.ok) throw new Error('Tool resolution failed')
      const data = await response.json() as { items: ResolutionItem[] }
      setResolution(data.items)
    } catch (resolutionError) {
      console.error('Tool resolution error:', resolutionError)
      setError('Tool 权限解析失败。')
    } finally {
      setIsMutating(false)
    }
  }, [allowlistDraft])

  if (isLoading && !catalog) {
    return <LoadingState title="正在读取 Tool Catalog" description="正在加载版本、健康与生命周期状态…" />
  }
  if (error && !catalog) {
    return <ErrorState title="Tool Catalog 不可用" description={error} action={<Button variant="secondary" onClick={() => void loadCatalog()}>重试</Button>} />
  }
  if (!catalog) return <EmptyState title="Catalog 尚未初始化" description="刷新后将发现内部工具。" />

  const hasLifecycleRisk = catalog.unavailable_count > 0 || catalog.failed_refresh_count > 0

  return (
    <div className="space-y-4">
      <StatusBanner
        tone={hasLifecycleRisk ? 'warning' : 'success'}
        title={hasLifecycleRisk ? 'Tool 生命周期需要关注' : 'Tool Catalog 运行正常'}
        action={(
          <div className="flex gap-2">
            <Button variant="secondary" disabled={isMutating} onClick={() => setAutoMonitor((value) => !value)}>
              {autoMonitor ? <PauseCircle className="size-4" /> : <PlayCircle className="size-4" />}
              {autoMonitor ? '暂停监控' : '恢复监控'}
            </Button>
            <Button disabled={isMutating} onClick={() => void mutate('/api/tools/refresh')}>
              <RefreshCw className="size-4" />重新发现
            </Button>
          </div>
        )}
      >
        revision <span className="font-mono">{catalog.revision}</span> · generation {catalog.generation} · {autoMonitor ? '每 15 秒刷新状态' : '自动监控已暂停'}
      </StatusBanner>

      {error ? <StatusBanner tone="warning">{error}</StatusBanner> : null}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label="已发现" value={catalog.tool_count} />
        <Metric label="已启用" value={catalog.enabled_count} />
        <Metric label="健康" value={catalog.healthy_count} tone="text-emerald-600" />
        <Metric label="不可用" value={catalog.unavailable_count} tone="text-rose-600" />
        <Metric label="刷新失败" value={catalog.failed_refresh_count} tone="text-amber-600" />
      </section>

      <SurfaceCard>
        <div className="flex items-center gap-2">
          <Search className="size-5 text-cyan-600" />
          <div>
            <h2 className="font-black text-slate-950">Task allowlist 解析诊断</h2>
            <p className="text-sm text-slate-600">输入逗号分隔工具名，验证 Catalog、启停和健康状态形成的最终决策。</p>
          </div>
        </div>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <input
            value={allowlistDraft}
            onChange={(event) => setAllowlistDraft(event.target.value)}
            className="min-w-0 flex-1 rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm text-slate-900"
          />
          <Button disabled={isMutating} onClick={() => void resolveAllowlist()}>解析权限</Button>
        </div>
        {resolution ? (
          <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            {resolution.map((item) => (
              <div key={item.name} className={`rounded-lg border p-3 text-sm ${item.allowed ? 'border-emerald-200 bg-emerald-50' : 'border-slate-200 bg-slate-50'}`}>
                <p className="font-mono font-bold text-slate-950">{item.name}</p>
                <p className={item.allowed ? 'text-emerald-700' : 'text-slate-500'}>{item.allowed ? 'allowed' : item.reason}</p>
              </div>
            ))}
          </div>
        ) : null}
      </SurfaceCard>

      <section className="grid gap-4 xl:grid-cols-2">
        {catalog.tools.map((tool) => (
          <SurfaceCard key={`${tool.name}:${tool.version}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-3">
                <Wrench className="mt-1 size-5 shrink-0 text-cyan-600" />
                <div className="min-w-0">
                  <h2 className="break-words font-mono text-sm font-black text-slate-950">{tool.name}@{tool.version}</h2>
                  <p className="mt-1 text-sm leading-6 text-slate-600">{tool.description}</p>
                </div>
              </div>
              <span className={`rounded-full px-2 py-1 text-xs font-bold ${healthClass(tool)}`}>{tool.enabled ? tool.health_status : 'disabled'}</span>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
              <Field label="来源" value={`${tool.source} · ${tool.provider_ref}`} />
              <Field label="风险 / 幂等" value={`${tool.risk_level} · ${tool.idempotency}`} />
              <Field label="超时" value={`${tool.timeout_ms} ms`} />
              <Field label="Spec hash" value={tool.spec_hash?.slice(0, 12) ?? '—'} mono />
            </dl>
            <details className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
              <summary className="cursor-pointer font-bold">Schema</summary>
              <pre className="mt-2 max-h-48 overflow-auto">{JSON.stringify({ input_schema: tool.input_schema, output_schema: tool.output_schema }, null, 2)}</pre>
            </details>
            <div className="mt-3 flex justify-end">
              <Button
                variant={tool.enabled ? 'danger' : 'secondary'}
                disabled={isMutating}
                onClick={() => void mutate(`/api/tools/${encodeURIComponent(tool.name)}/${tool.enabled ? 'disable' : 'enable'}`)}
              >
                {tool.enabled ? <PauseCircle className="size-4" /> : <PlayCircle className="size-4" />}
                {tool.enabled ? '停用' : '启用'}
              </Button>
            </div>
          </SurfaceCard>
        ))}
      </section>
    </div>
  )
}

function Metric({ label, value, tone = 'text-slate-950' }: { label: string; value: number; tone?: string }) {
  return <SurfaceCard><p className="text-xs font-bold uppercase text-slate-500">{label}</p><p className={`mt-1 text-2xl font-black ${tone}`}>{value}</p></SurfaceCard>
}

function Field({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div><dt className="font-bold text-slate-400">{label}</dt><dd className={`mt-0.5 break-all ${mono ? 'font-mono' : ''}`}>{value}</dd></div>
}

function healthClass(tool: ToolSpec): string {
  if (!tool.enabled) return 'bg-slate-100 text-slate-600'
  if (tool.health_status === 'healthy') return 'bg-emerald-100 text-emerald-700'
  if (tool.health_status === 'degraded') return 'bg-amber-100 text-amber-700'
  return 'bg-rose-100 text-rose-700'
}
