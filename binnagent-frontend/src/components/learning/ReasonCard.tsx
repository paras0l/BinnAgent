import type { ReactNode } from 'react'
import { Sparkles } from 'lucide-react'

interface ReasonCardProps {
  title: string
  reason: string
  evidence?: string[]
  outcome?: string
  action?: ReactNode
}

export function ReasonCard({ title, reason, evidence = [], outcome, action }: ReasonCardProps) {
  return (
    <article className="rounded-[13px] border border-slate-200 bg-white p-5 shadow-[0_4px_14px_rgba(15,23,42,0.05)]">
      <div className="flex items-start gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Sparkles className="size-4" />
        </div>
        <div className="min-w-0">
          <h3 className="text-base font-black text-slate-950">{title}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600">{reason}</p>
        </div>
      </div>
      {evidence.length > 0 && (
        <div className="mt-4 rounded-lg bg-slate-50 p-3">
          <p className="text-xs font-bold text-slate-500">依据</p>
          <ul className="mt-2 space-y-1 text-xs leading-5 text-slate-600">
            {evidence.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      )}
      {outcome && <p className="mt-3 text-xs font-semibold text-emerald-700">{outcome}</p>}
      {action && <div className="mt-4">{action}</div>}
    </article>
  )
}
