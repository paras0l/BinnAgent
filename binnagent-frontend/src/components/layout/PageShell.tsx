import type { ReactNode } from 'react'

interface PageShellProps {
  children: ReactNode
  className?: string
}

export function PageShell({ children, className = '' }: PageShellProps) {
  return (
    <div className={`min-h-[calc(100vh-4rem)] bg-[#f6f7f9] ${className}`}>
      <div className="mx-auto flex w-full max-w-[1180px] flex-col gap-5 px-4 py-6 sm:px-6 lg:px-8">
        {children}
      </div>
    </div>
  )
}
