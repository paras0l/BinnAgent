import type { ReactNode } from 'react'

interface SurfaceCardProps {
  children: ReactNode
  className?: string
}

export function SurfaceCard({ children, className = '' }: SurfaceCardProps) {
  return (
    <section className={`rounded-[13px] border border-slate-200 bg-white p-5 shadow-[0_4px_14px_rgba(15,23,42,0.05)] ${className}`}>
      {children}
    </section>
  )
}
