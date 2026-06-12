import { useState } from 'react'
import { Send, Square } from 'lucide-react'

interface ChatInputProps {
  onSend: (message: string) => void
  onCancel: () => void
  isLoading: boolean
}

export function ChatInput({ onSend, onCancel, isLoading }: ChatInputProps) {
  const [message, setMessage] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (message.trim() && !isLoading) {
      onSend(message.trim())
      setMessage('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="输入你想练习的内容..."
        className="flex-1 rounded-xl border bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
        disabled={isLoading}
      />
      {isLoading ? (
        <button
          type="button"
          onClick={onCancel}
          className="rounded-xl bg-error px-4 py-3 text-primary-foreground transition-colors hover:bg-error/90"
        >
          <Square className="h-4 w-4" />
        </button>
      ) : (
        <button
          type="submit"
          disabled={!message.trim()}
          className="rounded-xl bg-primary px-4 py-3 text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      )}
    </form>
  )
}
