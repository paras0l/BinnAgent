import type { ReactNode } from 'react'

interface FeatureHeroProps {
  eyebrow: string
  title: string
  description: string
  actions?: ReactNode
  stats?: Array<{
    label: string
    value: string | number
    tone?: 'default' | 'primary' | 'warning' | 'success'
  }>
}

const toneClass = {
  default: 'text-slate-950',
  primary: 'text-primary',
  warning: 'text-warning',
  success: 'text-success',
}

export function FeatureHero({ eyebrow, title, description, actions, stats = [] }: FeatureHeroProps) {
  return (
    <section className="relative overflow-hidden rounded-[1.5rem] border border-white/90 bg-white/78 p-6 shadow-[0_16px_48px_rgba(51,65,85,0.06)] ring-1 ring-slate-200/65 backdrop-blur-sm sm:p-7">
      <div className="pointer-events-none absolute -right-16 -top-20 size-64 rounded-full bg-indigo-100/55 blur-3xl" aria-hidden="true" />
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="relative min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">{eyebrow}</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950">{title}</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">{description}</p>
        </div>
        {actions && <div className="relative flex flex-wrap gap-2">{actions}</div>}
      </div>
      {stats.length > 0 && (
        <div className="relative mt-6 grid overflow-hidden rounded-2xl border border-slate-200/70 bg-slate-50/55 sm:grid-cols-2 sm:divide-x sm:divide-slate-200/70 lg:grid-cols-4">
          {stats.map((stat) => (
            <div key={stat.label} className="border-b border-slate-200/70 px-4 py-3.5 last:border-b-0 sm:[&:nth-last-child(-n+2)]:border-b-0 lg:border-b-0">
              <p className="text-xs font-semibold text-slate-500">{stat.label}</p>
              <p className={`mt-1 text-2xl font-black ${toneClass[stat.tone ?? 'default']}`}>
                {stat.value}
              </p>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
