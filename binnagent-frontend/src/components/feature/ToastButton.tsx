import { useToast } from '@/hooks/useToast'

interface ToastButtonProps {
  message: string
  duration?: number
  variant?: 'info' | 'success' | 'warning' | 'error'
  className?: string
}

export function ToastButton({ message, duration = 4000, variant = 'info', className }: ToastButtonProps) {
  const { showToast } = useToast()

  const handleClick = () => {
    showToast(message, { duration, variant })
  }

  return (
    <button
      onClick={handleClick}
      className={`px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors ${className}`}
    >
      Show Toast
    </button>
  )
}
