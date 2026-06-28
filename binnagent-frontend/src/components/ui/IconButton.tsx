import type { ButtonHTMLAttributes, ReactNode } from 'react'

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode
  label: string
  danger?: boolean
}

export function IconButton({ children, label, className = '', danger = false, type = 'button', ...props }: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={`inline-flex size-9 items-center justify-center rounded-lg border transition disabled:cursor-not-allowed disabled:opacity-50 ${
        danger
          ? 'border-rose-200 text-rose-600 hover:bg-rose-50'
          : 'border-slate-200 text-slate-500 hover:bg-slate-100 hover:text-slate-950'
      } ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
