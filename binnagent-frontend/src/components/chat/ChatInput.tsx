import { Send, Square } from 'lucide-react'
import { IconButton } from '@/components/ui/IconButton'

interface ChatInputProps {
  onSend: (message: string) => void
  onCancel: () => void
  isLoading: boolean
  isDisabled?: boolean
  message: string
  onMessageChange: (value: string) => void
}

export function ChatInput({
  onSend,
  onCancel,
  isLoading,
  isDisabled = false,
  message,
  onMessageChange,
}: ChatInputProps) {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (message.trim() && !isLoading && !isDisabled) {
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
          disabled={isLoading || isDisabled}
        />
      </label>
      {isLoading ? (
        <IconButton
          onClick={onCancel}
          label="停止生成"
          variant="dangerSolid"
          className="size-12"
        >
          <Square className="h-4 w-4" />
        </IconButton>
      ) : (
        <IconButton
          type="submit"
          disabled={!message.trim() || isDisabled}
          label={isDisabled ? '正在恢复对话' : '发送消息'}
          variant="primary"
          className="size-12"
        >
          <Send className="h-4 w-4" />
        </IconButton>
      )}
    </form>
  )
}
