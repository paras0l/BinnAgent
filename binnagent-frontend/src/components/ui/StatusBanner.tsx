import type { ReactNode } from 'react'
import { AlertCircle, CheckCircle2, Info } from 'lucide-react'

type StatusTone = 'info' | 'success' | 'warning'

interface StatusBannerProps {
  title?: string
  children: ReactNode
  action?: ReactNode
  tone?: StatusTone
}

const toneClass: Record<StatusTone, string> = {
  info: 'border-primary/20 bg-primary/5 text-primary',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  warning: 'border-amber-200 bg-amber-50 text-amber-700',
}

export function StatusBanner({ title, children, action, tone = 'info' }: StatusBannerProps) {
  const Icon = tone === 'success' ? CheckCircle2 : tone === 'warning' ? AlertCircle : Info

  return (
    <div className={`flex flex-col gap-2 rounded-lg border px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between ${toneClass[tone]}`}>
      <div className="flex min-w-0 items-start gap-2">
        <Icon className="mt-0.5 size-4 shrink-0" />
        <div className="min-w-0">
          {title && <p className="font-bold">{title}</p>}
          <div className="leading-6">{children}</div>
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}
