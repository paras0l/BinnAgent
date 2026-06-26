import type { ReactNode } from 'react'

interface FilterChipProps {
  active?: boolean
  children: ReactNode
  onClick: () => void
}

export function FilterChip({ active = false, children, onClick }: FilterChipProps) {
  return (
    <button
      onClick={onClick}
      className={`shrink-0 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
        active
          ? 'border-primary bg-primary/10 text-primary'
          : 'border-slate-200 bg-white text-slate-600 hover:border-indigo-200 hover:text-indigo-600'
      }`}
    >
      {children}
    </button>
  )
}
