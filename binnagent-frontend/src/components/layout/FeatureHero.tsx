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
    <section className="rounded-[13px] border border-slate-200 bg-white p-5 shadow-[0_4px_14px_rgba(15,23,42,0.05)]">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">{eyebrow}</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950">{title}</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">{description}</p>
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
      {stats.length > 0 && (
        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat) => (
            <div key={stat.label} className="rounded-[13px] border border-slate-100 bg-slate-50 px-4 py-3">
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
