import type { ToastVariant } from './ToastContext'

export interface QueueMessage {
  id: string
  message: string
  variant: ToastVariant
  priority?: number
}

const PRIORITY: Record<ToastVariant, number> = {
  error: 3,
  warning: 2,
  success: 1,
  info: 0,
}

export function enqueuePetMessage<T extends QueueMessage>(current: T[], next: T, maxMessages: number): T[] {
  const withoutDuplicate = current.filter((item) => item.message !== next.message || item.variant !== next.variant)
  return [...withoutDuplicate, next]
    .sort((left, right) => (
      PRIORITY[right.variant] * 10 + (right.priority ?? 0)
      - (PRIORITY[left.variant] * 10 + (left.priority ?? 0))
    ))
    .slice(0, maxMessages)
}
