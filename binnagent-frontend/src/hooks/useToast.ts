import { useContext } from 'react'
import { ToastContext, type ToastOptions } from '../components/ui/ToastContext'

export interface UseToastReturn {
  showToast: (message: string, options?: ToastOptions) => string
  hideToast: (id: string) => void
}

export function useToast(): UseToastReturn {
  const context = useContext(ToastContext)

  if (!context) {
    throw new Error('useToast must be used within a ToastProvider')
  }

  return context
}
