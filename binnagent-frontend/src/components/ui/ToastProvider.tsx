import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Toast } from './Toast'
import { ToastContext, type ToastOptions, type ToastVariant } from './ToastContext'

interface ToastState {
  id: string
  message: string
  title?: string
  variant: ToastVariant
  duration: number
}

const DEFAULT_DURATION = 4000
const MAX_TOASTS = 3

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastState[]>([])

  const hideToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const showToast = useCallback((message: string, options: ToastOptions = {}) => {
    const id = crypto.randomUUID()
    const nextToast: ToastState = {
      id,
      message,
      title: options.title,
      variant: options.variant ?? 'info',
      duration: options.duration ?? DEFAULT_DURATION,
    }
    setToasts((current) => [...current, nextToast].slice(-MAX_TOASTS))
    return id
  }, [])

  useEffect(() => {
    if (toasts.length === 0) return undefined
    const timers = toasts.map((toast) =>
      window.setTimeout(() => hideToast(toast.id), toast.duration)
    )
    return () => timers.forEach(window.clearTimeout)
  }, [hideToast, toasts])

  const value = useMemo(() => ({ showToast, hideToast }), [hideToast, showToast])

  return (
    <ToastContext.Provider value={value}>
      {children}
      {createPortal(
        <div className="pointer-events-none fixed left-1/2 top-20 z-[100] flex w-full -translate-x-1/2 flex-col items-center gap-3 px-4 sm:top-6">
          {toasts.map((toast) => (
            <div key={toast.id} className="pointer-events-auto toast-enter">
              <Toast {...toast} onDismiss={hideToast} />
            </div>
          ))}
        </div>,
        document.body
      )}
    </ToastContext.Provider>
  )
}
