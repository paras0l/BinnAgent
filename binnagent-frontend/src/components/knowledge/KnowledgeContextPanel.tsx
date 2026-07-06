import { BookOpen, CheckCircle2, Info, Layers3, Target, TrendingUp, UploadCloud } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type { KnowledgeBaseOverview } from '@/types'

interface KnowledgeContextPanelProps {
  overview: KnowledgeBaseOverview
  className?: string
  onUpload: () => void
}

export function KnowledgeContextPanel({ overview, className = '', onUpload }: KnowledgeContextPanelProps) {
  const { source } = overview
  const sourceStatus = sourceStatusLabel(source.status)
  return (
    <aside className={`knowledge-context space-y-5 border-l border-slate-200 bg-slate-50/40 px-5 py-7 ${className}`}>
      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-extrabold text-slate-950">教材信息</h2>
        <div className="mt-5 flex gap-4">
          {source.grade === 'grade-7' && source.volume === 'upper' ? (
            <img
              src="/grade7-english-upper-cover.png"
              alt="人教版英语七年级上册封面"
              width={96}
              height={144}
              className="h-36 w-24 shrink-0 rounded-md border border-slate-100 object-cover object-[78%_center] shadow-sm"
            />
          ) : (
            <div className="flex h-36 w-24 shrink-0 items-center justify-center rounded-md border border-indigo-100 bg-indigo-50 text-indigo-600 shadow-sm">
              <BookOpen className="size-8" />
            </div>
          )}
          <div className="min-w-0 py-1">
            <p className="text-xs text-slate-500">{source.publisher}</p>
            <h3 className="mt-1 text-sm font-extrabold leading-6 text-slate-900">{source.title}</h3>
            <span className={`mt-3 inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-bold ${sourceStatus.className}`}>
              <CheckCircle2 className="size-3.5" />
              {sourceStatus.label}
            </span>
          </div>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-3 border-t border-slate-100 pt-4 text-sm text-slate-600">
          <span className="flex items-center gap-2"><BookOpen className="size-4" />{source.unit_count} 个单元</span>
          <span className="flex items-center gap-2"><Layers3 className="size-4" />{source.knowledge_count} 个知识点</span>
          <span className="flex items-center gap-2">页数 {source.page_count ?? '—'}</span>
          <span className="flex items-center gap-2 text-emerald-700"><CheckCircle2 className="size-4" />可练习</span>
        </div>
        <Button
          variant="secondary"
          onClick={onUpload}
          className="mt-5 w-full border-indigo-300 text-indigo-600 hover:bg-indigo-50"
        >
          <UploadCloud className="size-4" />
          上传英语教材
        </Button>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-extrabold text-slate-950">掌握度快照</h2>
          <Target className="size-5 text-indigo-600" />
        </div>
        <div className="mt-5 grid grid-cols-[92px_minmax(0,1fr)] items-center gap-4">
          <div className="flex aspect-square items-center justify-center rounded-full border-[10px] border-emerald-500 bg-emerald-50 text-center">
            <div>
              <p className="text-2xl font-black text-slate-950">{masteryPercent(overview)}%</p>
              <p className="text-xs font-bold text-slate-500">掌握度</p>
            </div>
          </div>
          <div className="space-y-3">
            {masteryRows(overview).map((row) => (
              <div key={row.label} className="grid grid-cols-[44px_minmax(0,1fr)_38px] items-center gap-2 text-xs font-bold text-slate-500">
                <span>{row.label}</span>
                <span className="h-2 overflow-hidden rounded-full bg-slate-100">
                  <span className={`block h-full rounded-full ${row.className}`} style={{ width: `${row.value}%` }} />
                </span>
                <span className="text-right text-slate-700">{row.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="flex items-center gap-2">
          <TrendingUp className="size-5 text-amber-500" />
          <h2 className="text-base font-extrabold text-slate-950">推荐原因</h2>
        </div>
        <div className="mt-4 rounded-xl bg-slate-50 px-3 py-3 text-sm leading-6 text-slate-600">
          {overview.recommendation_reason}
        </div>
        <div className="mt-4 border-t border-slate-100 pt-4">
          <p className="text-xs font-black uppercase text-slate-500">完成后会改善</p>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs font-bold text-slate-600">
            <span className="rounded-lg bg-emerald-50 px-2 py-2 text-emerald-700">词汇记忆</span>
            <span className="rounded-lg bg-indigo-50 px-2 py-2 text-indigo-700">语法准确</span>
            <span className="rounded-lg bg-amber-50 px-2 py-2 text-amber-700">听力理解</span>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-extrabold text-slate-950">学习路径</h2>
        <ol className="relative mt-5 space-y-6">
          <span className="absolute bottom-5 left-3 top-3 w-px bg-slate-200" />
          {overview.path.map((item) => (
            <li key={item.id} className="relative grid grid-cols-[28px_minmax(0,1fr)] gap-3">
              <span className={`relative z-10 flex size-6 items-center justify-center rounded-full border text-xs font-extrabold ${
                item.status === 'current'
                  ? 'border-indigo-600 bg-indigo-600 text-white'
                  : item.status === 'completed'
                    ? 'border-emerald-500 bg-emerald-500 text-white'
                    : 'border-slate-300 bg-white text-slate-500'
              }`}>
                {item.ordinal}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-extrabold text-slate-800">{item.title}</p>
                <p className="mt-0.5 truncate text-xs text-slate-500">{item.subtitle}</p>
                <p className={`mt-1 text-xs font-semibold ${item.status === 'current' ? 'text-indigo-600' : 'text-slate-400'}`}>
                  {item.status === 'current'
                    ? '当前正在学习'
                    : item.status === 'completed'
                      ? '已完成'
                      : `预计 ${item.estimated_minutes ?? 20} 分钟`}
                </p>
              </div>
            </li>
          ))}
        </ol>
        <div className="mt-6 flex gap-2 rounded-xl border border-indigo-100 bg-indigo-50/70 p-3 text-xs leading-5 text-slate-600">
          <Info className="mt-0.5 size-4 shrink-0 text-indigo-600" />
          <p><span className="font-extrabold text-slate-800">推荐理由：</span>{overview.recommendation_reason}</p>
        </div>
      </section>
    </aside>
  )
}

function masteryPercent(overview: KnowledgeBaseOverview) {
  const average = overview.unit_workspace?.mastery_summary.average
  if (typeof average === 'number') return Math.round(average * 100)
  const points = overview.knowledge_points
  if (!points.length) return 0
  return Math.round((points.reduce((sum, item) => sum + (item.mastery ?? 0), 0) / points.length) * 100)
}

function masteryRows(overview: KnowledgeBaseOverview) {
  const points = overview.knowledge_points
  const byType = (type: string) => {
    const items = points.filter((item) => item.type === type)
    if (!items.length) return 0
    return Math.round((items.reduce((sum, item) => sum + (item.mastery ?? 0), 0) / items.length) * 100)
  }
  return [
    { label: '词汇', value: byType('vocabulary'), className: 'bg-emerald-500' },
    { label: '语法', value: byType('grammar'), className: 'bg-indigo-500' },
    { label: '句式', value: byType('sentence_pattern'), className: 'bg-sky-500' },
    { label: '听力', value: byType('pronunciation'), className: 'bg-amber-500' },
  ]
}

function sourceStatusLabel(status: string) {
  if (status === 'published' || status === 'review_required' || status === 'partial_indexed') {
    return { label: '可学习', className: 'bg-emerald-50 text-emerald-700' }
  }
  if (status === 'failed' || status === 'index_failed') {
    return { label: '解析失败', className: 'bg-rose-50 text-rose-700' }
  }
  return { label: '解析中', className: 'bg-indigo-50 text-indigo-700' }
}
