import { AlertCircle } from 'lucide-react'
import type { ReactNode } from 'react'

interface ErrorStateProps {
  title: string
  description: string
  action?: ReactNode
}

export function ErrorState({ title, description, action }: ErrorStateProps) {
  return (
    <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-[#f6f7f9] px-4">
      <div className="w-full max-w-md rounded-[13px] border border-slate-200 bg-white p-6 text-center shadow-[0_4px_14px_rgba(15,23,42,0.05)]">
        <AlertCircle className="mx-auto size-6 text-rose-600" />
        <h1 className="mt-3 text-lg font-black text-slate-950">{title}</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">{description}</p>
        {action && <div className="mt-5 flex justify-center">{action}</div>}
      </div>
    </div>
  )
}
