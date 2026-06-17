import { AlertCircle, CheckCircle2, Info, TriangleAlert, X } from 'lucide-react'

export interface ToastProps {
  id: string
  message: string
  title?: string
  variant?: 'info' | 'success' | 'warning' | 'error'
  duration?: number
  onDismiss: (id: string) => void
}

const variantStyles = {
  info: {
    icon: Info,
    iconClassName: 'bg-primary/10 text-primary',
    progressClassName: 'bg-primary',
  },
  success: {
    icon: CheckCircle2,
    iconClassName: 'bg-success/10 text-success',
    progressClassName: 'bg-success',
  },
  warning: {
    icon: TriangleAlert,
    iconClassName: 'bg-warning/15 text-warning',
    progressClassName: 'bg-warning',
  },
  error: {
    icon: AlertCircle,
    iconClassName: 'bg-error/10 text-error',
    progressClassName: 'bg-error',
  },
} satisfies Record<Required<ToastProps>['variant'], {
  icon: typeof Info
  iconClassName: string
  progressClassName: string
}>

export function Toast({
  id,
  message,
  title,
  variant = 'info',
  duration = 4000,
  onDismiss,
}: ToastProps) {
  const styles = variantStyles[variant]
  const Icon = styles.icon

  return (
    <div
      className="toast-card relative w-full max-w-[min(92vw,28rem)] overflow-hidden rounded-lg border border-border bg-background/95 p-4 pr-11 text-left shadow-[0_18px_50px_rgba(15,23,42,0.18)] backdrop-blur"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg ${styles.iconClassName}`}>
          <Icon className="h-4 w-4" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          {title && <p className="text-sm font-semibold text-foreground">{title}</p>}
          <p className={`${title ? 'mt-0.5' : ''} text-sm font-medium leading-5 text-foreground`}>
            {message}
          </p>
        </div>
      </div>
      <button
        type="button"
        onClick={() => onDismiss(id)}
        className="absolute right-3 top-3 inline-flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        aria-label="关闭通知"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
      <div className="absolute inset-x-0 bottom-0 h-1 bg-muted">
        <div
          className={`h-full origin-left ${styles.progressClassName} toast-progress`}
          style={{ animationDuration: `${duration}ms` }}
        />
      </div>
    </div>
  )
}
