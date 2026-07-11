import type { ToastVariant } from './ToastContext'

const BASE_DURATION: Record<ToastVariant, number> = {
  info: 3200,
  success: 4000,
  warning: 5200,
  error: 6500,
}

const MAX_DURATION: Record<ToastVariant, number> = {
  info: 10_000,
  success: 11_000,
  warning: 14_000,
  error: 16_000,
}

export function petMessageDuration({
  message,
  priority = 0,
  title,
  variant,
}: {
  message: string
  priority?: number
  title?: string
  variant: ToastVariant
}): number {
  const readableCharacters = Array.from(`${title ?? ''}${message}`.replace(/\s/gu, '')).length
  const readingTime = Math.max(0, readableCharacters - 12) * 110
  const importanceTime = Math.max(0, Math.min(priority, 9)) * 240
  return Math.min(MAX_DURATION[variant], BASE_DURATION[variant] + readingTime + importanceTime)
}
