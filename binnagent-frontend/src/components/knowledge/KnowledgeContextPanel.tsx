import { BookOpen, CheckCircle2, Info, Layers3, UploadCloud } from 'lucide-react'
import type { KnowledgeBaseOverview } from '@/types'

interface KnowledgeContextPanelProps {
  overview: KnowledgeBaseOverview
  onUpload: () => void
}

export function KnowledgeContextPanel({ overview, onUpload }: KnowledgeContextPanelProps) {
  const { source } = overview
  return (
    <aside className="knowledge-context space-y-5 border-l border-slate-200 bg-slate-50/40 px-5 py-7">
      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-extrabold text-slate-950">教材信息</h2>
        <div className="mt-5 flex gap-4">
          <img
            src="/grade7-english-upper-cover.png"
            alt="人教版英语七年级上册封面"
            className="h-36 w-24 shrink-0 rounded-md border border-slate-100 object-cover object-[78%_center] shadow-sm"
          />
          <div className="min-w-0 py-1">
            <p className="text-xs text-slate-500">{source.publisher}</p>
            <h3 className="mt-1 text-sm font-extrabold leading-6 text-slate-900">{source.title}</h3>
            <span className="mt-3 inline-flex items-center gap-1.5 rounded-md bg-emerald-50 px-2 py-1 text-xs font-bold text-emerald-700">
              <CheckCircle2 className="size-3.5" />
              {source.status === 'published' ? '已发布' : '处理中'}
            </span>
          </div>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-3 border-t border-slate-100 pt-4 text-sm text-slate-600">
          <span className="flex items-center gap-2"><BookOpen className="size-4" />{source.unit_count} 个单元</span>
          <span className="flex items-center gap-2"><Layers3 className="size-4" />{source.knowledge_count} 个知识点</span>
        </div>
        <button
          type="button"
          onClick={onUpload}
          className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-indigo-300 px-4 py-2.5 text-sm font-extrabold text-indigo-600 transition-colors hover:bg-indigo-50"
        >
          <UploadCloud className="size-4" />
          上传七年级教材
        </button>
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
