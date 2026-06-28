import type { ButtonHTMLAttributes, ReactNode } from 'react'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode
  variant?: ButtonVariant
}

const variantClass: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-primary-foreground hover:bg-primary/90',
  secondary: 'border border-slate-200 bg-white text-slate-700 shadow-sm hover:border-primary/30 hover:text-primary',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-950',
  danger: 'border border-rose-200 bg-white text-rose-600 shadow-sm hover:bg-rose-50',
}

export function Button({ children, className = '', variant = 'primary', type = 'button', ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-60 ${variantClass[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
