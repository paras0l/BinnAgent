import { Send, Square } from 'lucide-react'
import { IconButton } from '@/components/ui/IconButton'

interface ChatInputProps {
  onSend: (message: string) => void
  onCancel: () => void
  isLoading: boolean
  message: string
  onMessageChange: (value: string) => void
}

export function ChatInput({
  onSend,
  onCancel,
  isLoading,
  message,
  onMessageChange,
}: ChatInputProps) {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (message.trim() && !isLoading) {
      onSend(message.trim())
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
      <label className="min-w-0 flex-1">
        <span className="sr-only">聊天消息</span>
        <input
          type="text"
          name="chat_message"
          autoComplete="off"
          value={message}
          onChange={(e) => onMessageChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入你想练习的内容…"
          className="w-full rounded-xl border bg-background px-4 py-3 text-sm transition-colors focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isLoading}
        />
      </label>
      {isLoading ? (
        <IconButton
          onClick={onCancel}
          label="停止生成"
          danger
          className="size-12 border-error bg-error text-primary-foreground hover:bg-error/90 hover:text-primary-foreground"
        >
          <Square className="h-4 w-4 text-primary-foreground" />
        </IconButton>
      ) : (
        <IconButton
          type="submit"
          disabled={!message.trim()}
          label="发送消息"
          className="group size-12 border-primary bg-primary text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground disabled:border-slate-200 disabled:bg-slate-100"
        >
          <Send className="h-4 w-4 text-primary-foreground group-disabled:text-slate-400" />
        </IconButton>
      )}
    </form>
  )
}
