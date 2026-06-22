import { ArrowUpRight, BookText, GripVertical } from 'lucide-react'
import type { KnowledgePointSummary, KnowledgeType } from '@/types'

export type KnowledgeFilter = 'all' | KnowledgeType

const FILTERS: Array<{ id: KnowledgeFilter; label: string }> = [
  { id: 'all', label: '全部' },
  { id: 'vocabulary', label: '词汇' },
  { id: 'grammar', label: '语法' },
  { id: 'phrase', label: '词组' },
  { id: 'sentence_pattern', label: '句式' },
  { id: 'pronunciation', label: '语音' },
  { id: 'text_note', label: '课文注释' },
]

const TYPE_LABELS: Record<KnowledgeType, string> = {
  vocabulary: '词汇',
  grammar: '语法',
  phrase: '词组',
  sentence_pattern: '句式',
  pronunciation: '语音',
  text_note: '课文注释',
}

const TYPE_STYLES: Record<KnowledgeType, string> = {
  vocabulary: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  grammar: 'border-amber-200 bg-amber-50 text-amber-700',
  phrase: 'border-cyan-200 bg-cyan-50 text-cyan-700',
  sentence_pattern: 'border-indigo-200 bg-indigo-50 text-indigo-700',
  pronunciation: 'border-violet-200 bg-violet-50 text-violet-700',
  text_note: 'border-sky-200 bg-sky-50 text-sky-700',
}

interface KnowledgeListProps {
  items: KnowledgePointSummary[]
  filter: KnowledgeFilter
  onFilterChange: (filter: KnowledgeFilter) => void
  onStartGrammar: (topic: string) => void
}

export function KnowledgeList({ items, filter, onFilterChange, onStartGrammar }: KnowledgeListProps) {
  return (
    <section className="mt-7">
      <div className="flex items-center gap-2">
        <BookText className="size-5 text-indigo-600" />
        <h2 className="text-xl font-extrabold tracking-tight text-slate-950">本单元知识</h2>
      </div>

      <div className="mt-4 flex gap-6 border-b border-slate-200" role="tablist" aria-label="知识类型">
        {FILTERS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={filter === item.id}
            onClick={() => onFilterChange(item.id)}
            className={`relative pb-3 text-sm font-bold transition-colors ${
              filter === item.id ? 'text-indigo-600' : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            {item.label}
            {filter === item.id ? <span className="absolute inset-x-0 bottom-0 h-0.5 bg-indigo-600" /> : null}
          </button>
        ))}
      </div>

      <div className="mt-1 overflow-x-auto">
        <div className="min-w-[720px]">
          <div className="grid grid-cols-[32px_minmax(150px,1fr)_90px_90px_120px_minmax(210px,1.4fr)] border-b border-slate-200 px-1 py-3 text-xs font-bold text-slate-500">
            <span />
            <span>知识点</span>
            <span>类型</span>
            <span>来源页码</span>
            <span>掌握度</span>
            <span>知识点说明</span>
          </div>
          {items.length > 0 ? items.map((item) => (
            <article
              key={item.id}
              className="grid grid-cols-[32px_minmax(150px,1fr)_90px_90px_120px_minmax(210px,1.4fr)] items-center border-b border-slate-100 px-1 py-3.5 text-sm transition-colors hover:bg-slate-50/70"
            >
              {item.unit_order ? (
                <span className="text-xs font-bold text-slate-400">{item.unit_order}</span>
              ) : (
                <GripVertical className="size-4 text-slate-300" />
              )}
              <div className="min-w-0">
                <h3 className="font-extrabold text-slate-800">{item.title}</h3>
                {item.type === 'grammar' ? (
                  <button
                    type="button"
                    onClick={() => onStartGrammar(item.title)}
                    className="mt-1 inline-flex items-center gap-1 text-xs font-bold text-indigo-600 transition hover:text-indigo-800"
                    aria-label={`开始学习语法知识点：${item.title}`}
                  >
                    开始学习 <ArrowUpRight className="size-3" />
                  </button>
                ) : null}
              </div>
              <span>
                <span className={`inline-flex rounded-md border px-2 py-0.5 text-xs font-bold ${TYPE_STYLES[item.type]}`}>
                  {TYPE_LABELS[item.type]}
                </span>
              </span>
              <span className="text-slate-600">{item.source_page}</span>
              <span className="flex items-center gap-1" aria-label={`掌握度 ${Math.round(item.mastery * 100)}%`}>
                {[0.2, 0.4, 0.6, 0.8, 1].map((threshold) => (
                  <span
                    key={threshold}
                    className={`h-2.5 w-3 rounded-sm ${item.mastery >= threshold ? 'bg-emerald-500' : 'bg-slate-200'}`}
                  />
                ))}
              </span>
              <p className="truncate text-slate-500" title={item.summary}>{item.summary}</p>
            </article>
          )) : (
            <div className="py-12 text-center text-sm text-slate-500">当前筛选下暂无知识点。</div>
          )}
        </div>
      </div>
    </section>
  )
}
