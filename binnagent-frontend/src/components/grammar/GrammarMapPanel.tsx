import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, CheckCircle2, Circle, Clock3, Loader2, RotateCcw, Search } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { SurfaceCard } from '@/components/ui/SurfaceCard'

type GrammarStatus = 'stable' | 'forming' | 'review' | 'repeated_failure' | 'no_evidence'

interface GrammarDimension {
  mode: 'recognition' | 'recall' | 'production'
  score: number
  confidence: number
  evidence_count: number
}

interface GrammarPoint {
  id: string
  external_id: number | null
  slug: string
  category: string
  subcategory: string
  cefr_level: string
  construct_type: string
  guideword: string | null
  can_do_statement: string
  status: GrammarStatus
  mastery_score: number
  predicted_success: number
  confidence: number
  next_review_at: string | null
  dimensions: GrammarDimension[]
}

interface GrammarMatrixCell {
  category: string
  cefr_level: string
  stable: number
  forming: number
  review: number
  repeated_failure: number
  no_evidence: number
  total: number
}

interface GrammarMapPayload {
  catalog_version: string
  total_count: number
  example_count: number
  source_url: string | null
  source_attribution: string | null
  points: GrammarPoint[]
  matrix: GrammarMatrixCell[]
}

interface GrammarEvidence {
  id: string
  occurred_at: string
  mode: string
  outcome_score: number
  independent: boolean
  semantic_confidence: number
  decision_reason: string
  mastery_before: number | null
  mastery_after: number | null
  item_difficulty: number
}

interface GrammarDetail extends GrammarPoint {
  success_criteria: string[]
  failure_criteria: string[]
  positive_examples: string[]
  negative_examples: string[]
  prerequisites: string[]
  fsrs: null | {
    difficulty: number
    stability_days: number
    retrievability: number
    next_review_at: string
  }
  recent_evidence: GrammarEvidence[]
}

const STATUS_META: Record<GrammarStatus, { label: string; className: string }> = {
  stable: { label: '稳定掌握', className: 'bg-success/15 text-success' },
  forming: { label: '正在形成', className: 'bg-primary/15 text-primary' },
  review: { label: '需要复习', className: 'bg-warning/15 text-warning-foreground' },
  repeated_failure: { label: '反复失败', className: 'bg-destructive/15 text-destructive' },
  no_evidence: { label: '尚无证据', className: 'bg-muted text-muted-foreground' },
}

const DIMENSION_LABELS = { recognition: '辨认', recall: '回忆', production: '产出' }

export function GrammarMapPanel({ learnerId }: { learnerId: string }) {
  const [payload, setPayload] = useState<GrammarMapPayload | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<GrammarDetail | null>(null)
  const [category, setCategory] = useState('all')
  const [cefrLevel, setCefrLevel] = useState('all')
  const [query, setQuery] = useState('')
  const [visibleLimit, setVisibleLimit] = useState(100)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    async function loadMap() {
      setLoading(true)
      setError(null)
      try {
        const response = await fetch(`/api/learners/${learnerId}/grammar/map`, { signal: controller.signal })
        if (!response.ok) throw new Error('语法地图加载失败')
        const next = (await response.json()) as GrammarMapPayload
        setPayload(next)
        setSelectedId((current) => current ?? next.points[0]?.id ?? null)
      } catch (reason) {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '语法地图加载失败')
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void loadMap()
    return () => controller.abort()
  }, [learnerId])

  useEffect(() => {
    if (!selectedId) return
    const controller = new AbortController()
    async function loadDetail() {
      setDetailLoading(true)
      try {
        const response = await fetch(`/api/learners/${learnerId}/grammar/can-do/${selectedId}`, { signal: controller.signal })
        if (!response.ok) throw new Error('知识点详情加载失败')
        setDetail((await response.json()) as GrammarDetail)
      } catch (reason) {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '知识点详情加载失败')
      } finally {
        if (!controller.signal.aborted) setDetailLoading(false)
      }
    }
    void loadDetail()
    return () => controller.abort()
  }, [learnerId, selectedId])

  const categories = useMemo(() => Array.from(new Set(payload?.points.map((point) => point.category) ?? [])), [payload])
  const filteredPoints = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase()
    return payload?.points.filter((point) => {
      if (category !== 'all' && point.category !== category) return false
      if (cefrLevel !== 'all' && point.cefr_level !== cefrLevel) return false
      if (!normalizedQuery) return true
      return [point.can_do_statement, point.guideword ?? '', point.subcategory, String(point.external_id ?? '')]
        .some((value) => value.toLocaleLowerCase().includes(normalizedQuery))
    }) ?? []
  }, [category, cefrLevel, payload, query])
  const visiblePoints = filteredPoints.slice(0, visibleLimit)

  if (loading) {
    return <SurfaceCard className="flex min-h-72 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-primary" /><span className="ml-2 text-sm text-muted-foreground">正在汇总语法证据…</span></SurfaceCard>
  }

  if (error && !payload) {
    return <SurfaceCard className="min-h-52"><div className="flex items-center gap-2 text-destructive"><AlertCircle className="h-5 w-5" /><p>{error}</p></div><Button className="mt-4" variant="secondary" onClick={() => window.location.reload()}><RotateCcw className="h-4 w-4" />重新加载</Button></SurfaceCard>
  }

  return (
    <div className="space-y-5">
      <SurfaceCard>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-foreground">语法能力矩阵</h2>
            <p className="text-sm text-muted-foreground">颜色表示当前证据状态，不等同于课程完成度。目录版本 {payload?.catalog_version}</p>
          </div>
          <p className="text-sm text-muted-foreground">{payload?.total_count ?? 0} 个 can-do · {payload?.example_count ?? 0} 个 learner examples</p>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[640px] border-separate border-spacing-1 text-sm">
            <thead><tr><th className="p-2 text-left font-medium text-muted-foreground">类别</th>{['A1', 'A2', 'B1', 'B2'].map((level) => <th key={level} className="p-2 text-center font-medium text-muted-foreground">{level}</th>)}</tr></thead>
            <tbody>{categories.map((item) => <tr key={item}><th className="p-2 text-left font-medium text-foreground">{item}</th>{['A1', 'A2', 'B1', 'B2'].map((level) => {
              const cell = payload?.matrix.find((candidate) => candidate.category === item && candidate.cefr_level === level)
              if (!cell) return <td key={level} className="rounded-lg bg-muted/40 p-3 text-center text-muted-foreground">—</td>
              const active = cell.stable + cell.forming
              const tone = cell.repeated_failure > 0 ? 'bg-destructive/15 text-destructive' : cell.review > 0 ? 'bg-warning/15 text-warning-foreground' : active > 0 ? 'bg-success/15 text-success' : 'bg-muted text-muted-foreground'
              return <td key={level} className={`rounded-lg p-3 text-center font-medium ${tone}`}>{active}/{cell.total}</td>
            })}</tr>)}</tbody>
          </table>
        </div>
      </SurfaceCard>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <SurfaceCard>
          <div className="relative mb-3">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input value={query} onChange={(event) => { setQuery(event.target.value); setVisibleLimit(100) }} className="w-full rounded-lg border bg-background py-2 pl-9 pr-3 text-sm outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/20" placeholder="搜索 can-do、guideword 或 EGP 编号…" />
          </div>
          <div className="mb-3 flex gap-2 overflow-x-auto pb-2">
            <FilterButton active={cefrLevel === 'all'} label="全部等级" onClick={() => { setCefrLevel('all'); setVisibleLimit(100) }} />
            {['A1', 'A2', 'B1', 'B2', 'C1', 'C2'].map((level) => <FilterButton key={level} active={cefrLevel === level} label={level} onClick={() => { setCefrLevel(level); setVisibleLimit(100) }} />)}
          </div>
          <div className="flex gap-2 overflow-x-auto pb-2">
            <FilterButton active={category === 'all'} label="全部" onClick={() => { setCategory('all'); setVisibleLimit(100) }} />
            {categories.map((item) => <FilterButton key={item} active={category === item} label={item} onClick={() => { setCategory(item); setVisibleLimit(100) }} />)}
          </div>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {visiblePoints.map((point) => {
              const meta = STATUS_META[point.status]
              return <button key={point.id} type="button" onClick={() => setSelectedId(point.id)} style={{ contentVisibility: 'auto', containIntrinsicSize: '150px' }} className={`rounded-lg border p-4 text-left transition-colors hover:border-primary/50 ${selectedId === point.id ? 'border-primary bg-primary/5' : 'bg-background'}`}>
                <div className="flex items-start justify-between gap-3"><p className="font-medium text-foreground">{point.can_do_statement}</p><span className={`shrink-0 rounded-md px-2 py-1 text-xs ${meta.className}`}>{meta.label}</span></div>
                <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground"><span>EGP {point.external_id} · {point.cefr_level} · {point.construct_type}</span><span>预测成功率 {Math.round(point.predicted_success * 100)}%</span></div>
              </button>
            })}
          </div>
          {visiblePoints.length < filteredPoints.length ? <Button variant="secondary" className="mt-4 w-full" onClick={() => setVisibleLimit((current) => current + 100)}>继续显示（剩余 {filteredPoints.length - visiblePoints.length}）</Button> : null}
        </SurfaceCard>

        <SurfaceCard className="self-start xl:sticky xl:top-5">
          {detailLoading && !detail ? <div className="flex min-h-48 items-center justify-center"><Loader2 className="h-5 w-5 animate-spin text-primary" /></div> : detail ? <GrammarDetailView detail={detail} /> : <p className="text-sm text-muted-foreground">选择一个知识点查看证据。</p>}
        </SurfaceCard>
      </div>
      {payload?.source_attribution ? <SurfaceCard><p className="text-xs leading-relaxed text-muted-foreground">{payload.source_attribution}</p>{payload.source_url ? <a className="mt-2 inline-block text-xs text-primary hover:underline" href={payload.source_url} target="_blank" rel="noreferrer">English Grammar Profile</a> : null}</SurfaceCard> : null}
    </div>
  )
}

function GrammarDetailView({ detail }: { detail: GrammarDetail }) {
  const meta = STATUS_META[detail.status]
  return <div>
    <div className="flex items-start justify-between gap-3"><div><p className="text-xs text-muted-foreground">EGP {detail.external_id} · {detail.category} · {detail.subcategory} · {detail.cefr_level}</p>{detail.guideword ? <p className="mt-2 text-xs font-medium text-primary">{detail.guideword}</p> : null}<h3 className="mt-1 text-lg font-semibold text-foreground">{detail.can_do_statement}</h3></div><span className={`shrink-0 rounded-md px-2 py-1 text-xs ${meta.className}`}>{meta.label}</span></div>
    <div className="mt-5 rounded-lg border bg-background p-4"><p className="text-sm font-medium text-foreground">预计独立成功率</p><p className="mt-1 text-3xl font-semibold text-primary">{Math.round(detail.predicted_success * 100)}%</p><p className="mt-1 text-xs text-muted-foreground">证据置信度 {Math.round(detail.confidence * 100)}%</p></div>
    <div className="mt-5 space-y-3">{detail.dimensions.map((dimension) => <div key={dimension.mode}><div className="flex justify-between text-sm"><span className="text-foreground">{DIMENSION_LABELS[dimension.mode]}</span><span className="text-muted-foreground">{Math.round(dimension.score * 100)}% · {dimension.evidence_count} 条</span></div><div className="mt-1 h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${Math.round(dimension.score * 100)}%` }} /></div></div>)}</div>
    {detail.next_review_at ? <div className="mt-5 flex items-center gap-2 rounded-lg bg-warning/10 p-3 text-sm text-foreground"><Clock3 className="h-4 w-4 text-warning-foreground" />下次复习：{new Date(detail.next_review_at).toLocaleString()}</div> : null}
    <div className="mt-5"><h4 className="text-sm font-semibold text-foreground">判断标准</h4><ul className="mt-2 space-y-2">{detail.success_criteria.map((criterion) => <li key={criterion} className="flex gap-2 text-sm text-muted-foreground"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />{criterion}</li>)}</ul></div>
    {detail.positive_examples.length > 0 ? <div className="mt-5 rounded-lg bg-muted/60 p-3"><p className="text-xs font-medium text-muted-foreground">Learner examples（{detail.positive_examples.length}）</p><div className="mt-2 space-y-2">{detail.positive_examples.map((example) => <p key={example} className="text-sm text-foreground">{example}</p>)}</div></div> : null}
    <div className="mt-5"><h4 className="text-sm font-semibold text-foreground">最近证据</h4>{detail.recent_evidence.length === 0 ? <p className="mt-2 text-sm text-muted-foreground">尚无作答证据。完成关联练习后会显示掌握轨迹。</p> : <ol className="mt-2 space-y-2">{detail.recent_evidence.slice(0, 5).map((item) => <li key={item.id} className="flex gap-2 text-sm"><Circle className={`mt-1 h-3 w-3 shrink-0 ${item.outcome_score >= 0.6 ? 'fill-success text-success' : 'fill-destructive text-destructive'}`} /><div><p className="text-foreground">{DIMENSION_LABELS[item.mode as keyof typeof DIMENSION_LABELS] ?? item.mode} · {Math.round(item.outcome_score * 100)}%</p><p className="text-xs text-muted-foreground">{new Date(item.occurred_at).toLocaleString()} · 语义置信度 {Math.round(item.semantic_confidence * 100)}%</p></div></li>)}</ol>}</div>
  </div>
}

function FilterButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return <button type="button" onClick={onClick} className={`shrink-0 rounded-lg px-3 py-2 text-sm transition-colors ${active ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:text-foreground'}`}>{label}</button>
}
