import type { ReactNode } from 'react'

interface PageShellProps {
  children: ReactNode
  className?: string
  variant?: 'standard' | 'full'
}

export function PageShell({ children, className = '', variant = 'standard' }: PageShellProps) {
  const widthClass = variant === 'full' ? 'max-w-none' : 'max-w-[1180px]'

  return (
    <div className={`min-h-[calc(100vh-4rem)] bg-[#f6f7f9] ${className}`}>
      <div className={`mx-auto flex w-full ${widthClass} flex-col gap-5 px-4 py-6 sm:px-6 lg:px-8`}>
        {children}
      </div>
    </div>
  )
}
