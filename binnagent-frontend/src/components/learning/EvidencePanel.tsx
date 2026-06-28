interface EvidencePanelProps {
  title?: string
  items: string[]
  emptyText?: string
}

export function EvidencePanel({ title = '来源证据', items, emptyText = '暂无证据链接' }: EvidencePanelProps) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <div className="text-xs font-bold text-slate-500">{title}</div>
      <div className="mt-1 space-y-1 text-xs leading-5 text-slate-600">
        {items.length > 0 ? items.map((item) => <div key={item}>{item}</div>) : <div>{emptyText}</div>}
      </div>
    </div>
  )
}
