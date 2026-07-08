import type { ButtonHTMLAttributes, ReactNode } from 'react'

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode
  label: string
  danger?: boolean
  variant?: 'default' | 'primary' | 'dangerSolid'
}

export function IconButton({
  children,
  label,
  className = '',
  danger = false,
  variant = 'default',
  type = 'button',
  ...props
}: IconButtonProps) {
  const toneClass = {
    default: danger
      ? 'border-rose-200 text-rose-600 hover:bg-rose-50'
      : 'border-slate-200 text-slate-500 hover:bg-slate-100 hover:text-slate-950',
    primary: 'border-primary bg-primary text-primary-foreground hover:border-primary hover:bg-primary/90 hover:text-primary-foreground disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400',
    dangerSolid: 'border-error bg-error text-primary-foreground hover:border-error hover:bg-error/90 hover:text-primary-foreground disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400',
  }[variant]

  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={`inline-flex size-9 items-center justify-center rounded-lg border transition active:translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50 ${toneClass} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
