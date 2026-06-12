import { Bot, User } from 'lucide-react'

interface MessageBubbleProps {
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  isStreaming?: boolean
}

export function MessageBubble({ role, content, timestamp, isStreaming }: MessageBubbleProps) {
  const isUser = role === 'user'
  
  const formatTime = (ts: number) => {
    return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`flex size-8 shrink-0 items-center justify-center rounded-full ${
        isUser ? 'bg-primary text-primary-foreground' : 'bg-accent/20 text-accent'
      }`}>
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      
      <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 ${
        isUser
          ? 'bg-primary text-primary-foreground rounded-tr-sm'
          : 'bg-muted text-foreground rounded-tl-sm'
      }`}>
        <p className="text-sm leading-relaxed whitespace-pre-wrap">
          {content}
          {isStreaming && <span className="animate-pulse">▊</span>}
        </p>
        <span className="mt-1 block text-[10px] opacity-60">
          {formatTime(timestamp)}
        </span>
      </div>
    </div>
  )
}
