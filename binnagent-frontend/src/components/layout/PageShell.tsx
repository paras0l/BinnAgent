import type { ReactNode } from 'react'

interface PageShellProps {
  children: ReactNode
  className?: string
  contentClassName?: string
  variant?: 'standard' | 'full'
}

export function PageShell({ children, className = '', contentClassName = '', variant = 'standard' }: PageShellProps) {
  const widthClass = variant === 'full' ? 'max-w-none' : 'max-w-[1180px]'

  return (
    <div className={`binn-page-canvas binn-min-viewport-height ${className}`}>
      <div className={`mx-auto flex w-full ${widthClass} flex-col gap-6 px-4 py-7 sm:px-6 lg:px-8 lg:py-9 ${contentClassName}`}>
        {children}
      </div>
    </div>
  )
}
