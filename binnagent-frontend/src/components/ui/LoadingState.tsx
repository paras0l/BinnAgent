import { RefreshCw } from 'lucide-react'

interface LoadingStateProps {
  title: string
  description?: string
}

export function LoadingState({ title, description }: LoadingStateProps) {
  return (
    <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-[#f6f7f9] px-4">
      <div className="rounded-[13px] border border-slate-200 bg-white p-6 text-center shadow-[0_4px_14px_rgba(15,23,42,0.05)]">
        <RefreshCw className="mx-auto size-5 animate-spin text-primary" />
        <p className="mt-3 text-sm font-bold text-slate-950">{title}</p>
        {description && <p className="mt-1 max-w-sm text-sm leading-6 text-slate-500">{description}</p>}
      </div>
    </div>
  )
}
