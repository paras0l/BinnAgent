import { useCallback, useEffect, useState } from 'react'
import { RefreshCw, ServerCog } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { StatusBanner } from '@/components/ui/StatusBanner'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import { debugFetch } from '@/shared/api/debugClient'

type ProviderId = 'ollama' | 'deepseek' | 'longcat'

interface ProviderSummary {
  id: ProviderId
  label: string
  base_url: string
  chat_model: string
  utility_model: string
  embedding_model?: string | null
  api_key_configured: boolean
  supports_streaming: boolean
  supports_embeddings: boolean
  health?: {
    reachable?: boolean
    chat_model?: { available?: boolean }
    utility_model?: { available?: boolean }
    embedding_model?: { available?: boolean }
    api_key_configured?: boolean
  }
}

interface ProviderStatus {
  active_provider: ProviderId
  configured_provider: ProviderId
  rag_provider: 'ollama'
  providers: ProviderSummary[]
}

export function ModelProviderPage() {
  const [status, setStatus] = useState<ProviderStatus | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadStatus = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await debugFetch('/api/debug/model/provider')
      if (!response.ok) throw new Error('Model provider status unavailable')
      setStatus(await response.json() as ProviderStatus)
    } catch (err) {
      console.error('Model provider load error:', err)
      setError('Model Provider 暂时无法加载，请确认 debug token 和后端状态。')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadStatus(), 0)
    return () => window.clearTimeout(timer)
  }, [loadStatus])

  const switchProvider = async (provider: ProviderId) => {
    setIsSaving(true)
    setError(null)
    try {
      const response = await debugFetch('/api/debug/model/provider', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider }),
      })
      if (!response.ok) throw new Error('Provider switch failed')
      setStatus(await response.json() as ProviderStatus)
    } catch (err) {
      console.error('Model provider switch error:', err)
      setError('Provider 切换失败，请检查 provider 名称和后端配置。')
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading && !status) {
    return <LoadingState title="正在读取 Model Provider" description="正在请求 /api/debug/model/provider..." />
  }
  if (error && !status) {
    return (
      <ErrorState
        title="Model Provider 不可用"
        description={error}
        action={<Button variant="secondary" onClick={() => void loadStatus()}><RefreshCw className="size-4" />重试</Button>}
      />
    )
  }

  const providers = status?.providers ?? []

  return (
    <section className="space-y-4">
      <SurfaceCard>
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex items-start gap-3">
            <ServerCog className="mt-1 size-5 text-cyan-500" />
            <div>
              <h2 className="text-lg font-black text-slate-950">Model Provider</h2>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                Runtime chat/prompt provider: <span className="font-mono font-bold text-slate-900">{status?.active_provider}</span>
              </p>
            </div>
          </div>
          <Button variant="secondary" onClick={() => void loadStatus()} disabled={isLoading || isSaving}>
            <RefreshCw className="size-4" />
            Refresh
          </Button>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <Metric label="configured" value={status?.configured_provider ?? '-'} />
          <Metric label="active" value={status?.active_provider ?? '-'} />
          <Metric label="RAG isolated on" value={status?.rag_provider ?? 'ollama'} />
        </div>
        {error ? <StatusBanner tone="warning" title="Request failed">{error}</StatusBanner> : null}
      </SurfaceCard>

      <section className="grid gap-4 xl:grid-cols-3">
        {providers.map((provider) => (
          <SurfaceCard key={provider.id}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-black text-slate-950">{provider.label}</h3>
                <p className="mt-1 font-mono text-xs text-slate-500">{provider.id}</p>
              </div>
              {status?.active_provider === provider.id ? (
                <span className="rounded-full bg-cyan-100 px-2 py-1 text-xs font-black text-cyan-700">active</span>
              ) : null}
            </div>
            <dl className="mt-4 space-y-2 text-sm">
              <ProviderRow label="base" value={provider.base_url} mono />
              <ProviderRow label="chat" value={provider.chat_model} mono />
              <ProviderRow label="utility" value={provider.utility_model} mono />
              <ProviderRow label="key" value={provider.api_key_configured ? 'configured' : 'missing'} />
              <ProviderRow label="reachable" value={provider.health?.reachable ? 'yes' : 'no'} />
              <ProviderRow label="embedding" value={provider.supports_embeddings ? (provider.embedding_model ?? '-') : 'isolated'} mono />
            </dl>
            <Button
              type="button"
              className="mt-4 w-full justify-center"
              variant={status?.active_provider === provider.id ? 'secondary' : 'primary'}
              disabled={isSaving || status?.active_provider === provider.id}
              onClick={() => void switchProvider(provider.id)}
            >
              {status?.active_provider === provider.id ? '当前使用' : `切换到 ${provider.label}`}
            </Button>
          </SurfaceCard>
        ))}
      </section>
    </section>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
      <p className="text-xs font-bold uppercase text-slate-500">{label}</p>
      <p className="mt-1 font-mono text-sm font-black text-slate-950">{value}</p>
    </div>
  )
}

function ProviderRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid grid-cols-[88px_minmax(0,1fr)] gap-2">
      <dt className="font-bold text-slate-500">{label}</dt>
      <dd className={`min-w-0 break-words text-slate-800 ${mono ? 'font-mono text-xs' : 'font-bold'}`}>{value}</dd>
    </div>
  )
}
