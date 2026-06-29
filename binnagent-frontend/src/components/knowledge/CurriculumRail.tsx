import { BookMarked, Check, Circle } from 'lucide-react'
import type { CurriculumNode, KnowledgeBaseOverview } from '@/types'

interface CurriculumRailProps {
  nodes: CurriculumNode[]
  currentNodeId: string
  sourceTitle: string
  sources: KnowledgeBaseOverview['sources']
  currentSourceId: string
  progress: number
  onSourceChange: (sourceId: string) => void
  onSelect: (nodeId: string) => void
  onManage: () => void
}

export function CurriculumRail({
  nodes,
  currentNodeId,
  sourceTitle,
  sources,
  currentSourceId,
  progress,
  onSourceChange,
  onSelect,
  onManage,
}: CurriculumRailProps) {
  return (
    <aside className="knowledge-rail flex min-h-[calc(100vh-4rem)] flex-col border-r border-slate-200 bg-white px-5 py-7">
      <div>
        <h2 className="text-lg font-extrabold tracking-tight text-slate-950">{sourceTitle}</h2>
        {sources.length > 1 ? (
          <label className="mt-4 block">
            <span className="text-xs font-bold text-slate-500">切换教材</span>
            <select
              value={currentSourceId}
              onChange={(event) => onSourceChange(event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-bold text-slate-800 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
            >
              {sources.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.title}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
          <span>进度</span>
          <span className="font-semibold text-slate-700">{Math.round(progress * 100)}%</span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-emerald-500 transition-[width] duration-500"
            style={{ width: `${Math.round(progress * 100)}%` }}
          />
        </div>
      </div>

      <nav className="relative mt-8 flex-1" aria-label="教材目录">
        <div className="absolute bottom-8 left-[17px] top-6 w-px bg-slate-200" />
        <ol className="relative space-y-3">
          {nodes.map((node, index) => {
            const isCurrent = node.id === currentNodeId
            const isCompleted = node.status === 'completed'
            return (
              <li key={node.id}>
                <button
                  type="button"
                  onClick={() => onSelect(node.id)}
                  className={`group grid w-full grid-cols-[36px_minmax(0,1fr)] items-start rounded-xl px-2 py-4 text-left transition-colors ${
                    isCurrent ? 'bg-indigo-50 text-indigo-700' : 'hover:bg-slate-50'
                  }`}
                  aria-current={isCurrent ? 'step' : undefined}
                >
                  <span
                    className={`relative z-10 flex size-5 items-center justify-center rounded-full border bg-white ${
                      isCurrent
                        ? 'border-indigo-600 text-indigo-600'
                        : isCompleted
                          ? 'border-emerald-500 bg-emerald-500 text-white'
                          : 'border-slate-300 text-slate-300'
                    }`}
                  >
                    {isCompleted ? <Check className="size-3" strokeWidth={3} /> : <Circle className="size-2 fill-current" />}
                  </span>
                  <span className="min-w-0">
                    <span className="flex items-baseline gap-2">
                      <span className="text-sm font-semibold text-slate-500">{index + 1}</span>
                      <span className={`truncate text-[15px] font-bold ${isCurrent ? 'text-indigo-700' : 'text-slate-800'}`}>
                        {node.title}
                      </span>
                    </span>
                    {node.subtitle ? (
                      <span className={`mt-1 block truncate pl-6 text-sm ${isCurrent ? 'text-indigo-600' : 'text-slate-500'}`}>
                        {node.subtitle}
                      </span>
                    ) : null}
                  </span>
                </button>
              </li>
            )
          })}
        </ol>
      </nav>

      <button
        type="button"
        onClick={onManage}
        className="mt-8 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-indigo-200 px-4 py-2.5 text-sm font-bold text-indigo-600 transition-colors hover:bg-indigo-50"
      >
        <BookMarked className="size-4" />
        管理教材
      </button>
    </aside>
  )
}
