import { createContext } from 'react'
import type { ToastProps } from './Toast'

export type ToastVariant = NonNullable<ToastProps['variant']>

export interface ToastOptions {
  title?: string
  variant?: ToastVariant
  duration?: number
}

export interface ToastContextType {
  showToast: (message: string, options?: ToastOptions) => string
  hideToast: (id: string) => void
}

export const ToastContext = createContext<ToastContextType | undefined>(undefined)
