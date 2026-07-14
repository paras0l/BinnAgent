import { useCallback, useEffect, useState } from 'react'
import { BookA, Braces, Languages, Network, Quote, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { StatusBanner } from '@/components/ui/StatusBanner'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import { debugFetch } from '@/shared/api/debugClient'

interface DictionaryMetadata {
  build: {
    version: string
    status: string
    started_at: string
    completed_at: string | null
    source_manifest: Record<string, unknown>
    selection_config: Record<string, unknown>
    statistics: Record<string, unknown>
  } | null
  entries: {
    total: number
    by_kind: Record<string, number>
    total_senses: number
    with_examples: number
    with_relations: number
    example_coverage: number
    relation_coverage: number
  }
  translations: {
    locale: string
    entries: number
    senses: number
    entry_coverage: number
    sense_coverage: number
  }
}

export function BaseDictionaryPage() {
  const [metadata, setMetadata] = useState<DictionaryMetadata | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await debugFetch('/api/debug/base-dictionary/metadata')
      if (!response.ok) throw new Error('Base dictionary metadata unavailable')
      setMetadata(await response.json() as DictionaryMetadata)
    } catch {
      setError('基础词库元信息暂时无法读取，请确认数据库迁移、导入状态和 Debug Token。')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  if (loading && !metadata) {
    return <LoadingState title="正在读取基础词库" description="正在汇总版本、词条和内容覆盖率…" />
  }
  if (!metadata) {
    return (
      <ErrorState
        title="基础词库不可用"
        description={error ?? '无法读取基础词库元信息。'}
        action={<Button onClick={() => void load()}>重试</Button>}
      />
    )
  }

  const cards = [
    { label: '活跃词条', value: formatNumber(metadata.entries.total), detail: kindSummary(metadata.entries.by_kind), icon: BookA },
    { label: '英文义项', value: formatNumber(metadata.entries.total_senses), detail: '每个词条保留的常用义项', icon: Braces },
    { label: '中文释义', value: formatPercent(metadata.translations.sense_coverage), detail: `${formatNumber(metadata.translations.senses)} 个义项`, icon: Languages },
    { label: '例句覆盖', value: formatPercent(metadata.entries.example_coverage), detail: `${formatNumber(metadata.entries.with_examples)} 个词条`, icon: Quote },
    { label: '语义关系', value: formatPercent(metadata.entries.relation_coverage), detail: `${formatNumber(metadata.entries.with_relations)} 个词条`, icon: Network },
  ]

  return <div className="space-y-4">
    <StatusBanner
      tone={metadata.build?.status === 'published' ? 'success' : 'warning'}
      title={metadata.build ? `基础词库 ${metadata.build.version}` : '尚无已发布构建'}
      action={<Button variant="secondary" onClick={() => void load()} disabled={loading}><RefreshCw className="size-4" />刷新</Button>}
    >
      {metadata.build?.completed_at
        ? `发布于 ${new Date(metadata.build.completed_at).toLocaleString()}，当前统计仅包含 active 词条。`
        : '请先完成基础词库 load 发布流程。'}
    </StatusBanner>
    {error ? <StatusBanner tone="warning">{error}</StatusBanner> : null}

    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {cards.map(({ label, value, detail, icon: Icon }) => (
        <SurfaceCard key={label} className="min-w-0">
          <Icon className="size-5 text-cyan-600" />
          <p className="mt-3 text-xs font-black uppercase tracking-wide text-slate-500">{label}</p>
          <p className="mt-1 text-2xl font-black text-slate-950">{value}</p>
          <p className="mt-1 truncate text-xs text-slate-500" title={detail}>{detail}</p>
        </SurfaceCard>
      ))}
    </section>

    <section className="grid gap-4 xl:grid-cols-2">
      <SurfaceCard>
        <h2 className="font-black text-slate-950">构建参数</h2>
        <MetadataTable values={metadata.build?.selection_config ?? {}} empty="当前构建没有记录筛选参数。" />
      </SurfaceCard>
      <SurfaceCard>
        <h2 className="font-black text-slate-950">来源清单</h2>
        <MetadataTable values={metadata.build?.source_manifest ?? {}} empty="当前构建没有记录来源信息。" />
      </SurfaceCard>
    </section>
  </div>
}

function MetadataTable({ values, empty }: { values: Record<string, unknown>; empty: string }) {
  const entries = Object.entries(values)
  if (!entries.length) return <p className="mt-3 text-sm text-slate-500">{empty}</p>
  return <dl className="mt-3 divide-y divide-slate-100">
    {entries.map(([key, value]) => (
      <div key={key} className="grid gap-1 py-3 sm:grid-cols-[160px_minmax(0,1fr)]">
        <dt className="font-mono text-xs font-bold text-slate-500">{key}</dt>
        <dd className="break-words text-sm text-slate-800">{formatValue(value)}</dd>
      </div>
    ))}
  </dl>
}

function formatValue(value: unknown) {
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

function formatNumber(value: number) {
  return new Intl.NumberFormat('zh-CN').format(value)
}

function formatPercent(value: number) {
  return `${Math.round(value * 1000) / 10}%`
}

function kindSummary(values: Record<string, number>) {
  return Object.entries(values)
    .map(([kind, count]) => `${kind} ${formatNumber(count)}`)
    .join(' · ') || '暂无类型统计'
}
