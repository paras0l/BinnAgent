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
  remainingMs: number
  startedAt: number
  isPaused: boolean
  isPinned: boolean
}

const DEFAULT_DURATION = 4000
const MAX_TOASTS = 3

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastState[]>([])

  const hideToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const pauseToast = useCallback((id: string, pin = false) => {
    setToasts((current) =>
      current.map((toast) => {
        if (toast.id !== id) return toast
        const elapsedMs = toast.isPaused ? 0 : Date.now() - toast.startedAt
        return {
          ...toast,
          remainingMs: Math.max(0, toast.remainingMs - elapsedMs),
          isPaused: true,
          isPinned: toast.isPinned || pin,
        }
      })
    )
  }, [])

  const resumeToast = useCallback((id: string, force = false) => {
    setToasts((current) =>
      current.map((toast) => {
        if (toast.id !== id) return toast
        if (toast.isPinned && !force) return toast
        return {
          ...toast,
          startedAt: Date.now(),
          isPaused: false,
          isPinned: false,
        }
      })
    )
  }, [])

  const toggleToastPause = useCallback((id: string) => {
    setToasts((current) =>
      current.map((toast) => {
        if (toast.id !== id) return toast
        if (toast.isPaused && toast.isPinned) {
          return {
            ...toast,
            startedAt: Date.now(),
            isPaused: false,
            isPinned: false,
          }
        }
        const elapsedMs = toast.isPaused ? 0 : Date.now() - toast.startedAt
        return {
          ...toast,
          remainingMs: Math.max(0, toast.remainingMs - elapsedMs),
          isPaused: true,
          isPinned: true,
        }
      })
    )
  }, [])

  const showToast = useCallback((message: string, options: ToastOptions = {}) => {
    const duration = options.duration ?? DEFAULT_DURATION
    const id = crypto.randomUUID()
    const nextToast: ToastState = {
      id,
      message,
      title: options.title,
      variant: options.variant ?? 'info',
      duration,
      remainingMs: duration,
      startedAt: Date.now(),
      isPaused: false,
      isPinned: false,
    }
    setToasts((current) => [...current, nextToast].slice(-MAX_TOASTS))
    return id
  }, [])

  useEffect(() => {
    if (toasts.length === 0) return undefined
    const timers = toasts
      .filter((toast) => !toast.isPaused)
      .map((toast) => window.setTimeout(() => hideToast(toast.id), toast.remainingMs))
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
              <Toast
                {...toast}
                onDismiss={hideToast}
                onPause={pauseToast}
                onResume={resumeToast}
                onTogglePause={toggleToastPause}
              />
            </div>
          ))}
        </div>,
        document.body
      )}
    </ToastContext.Provider>
  )
}
