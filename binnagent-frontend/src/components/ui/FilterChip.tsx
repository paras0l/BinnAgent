import type { ReactNode } from 'react'

interface FilterChipProps {
  active?: boolean
  children: ReactNode
  onClick: () => void
}

export function FilterChip({ active = false, children, onClick }: FilterChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex min-h-9 shrink-0 items-center rounded-full border px-3 py-2 text-xs font-bold transition-colors active:translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
        active
          ? 'border-primary bg-primary/10 text-primary'
          : 'border-slate-200 bg-white text-slate-600 hover:border-indigo-200 hover:text-indigo-600'
      }`}
    >
      {children}
    </button>
  )
}
