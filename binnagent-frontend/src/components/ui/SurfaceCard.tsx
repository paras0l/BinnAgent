import type { ReactNode } from 'react'

interface SurfaceCardProps {
  children: ReactNode
  className?: string
}

export function SurfaceCard({ children, className = '' }: SurfaceCardProps) {
  return (
   <section className={`relative rounded-2xl border border-slate-200/80 bg-white/88 p-5 shadow-[0_10px_32px_rgba(51,65,85,0.045)] backdrop-blur-sm focus-within:z-20 ${className}`}>
      {children}
    </section>
  )
}
