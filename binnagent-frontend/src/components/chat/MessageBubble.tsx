import { User } from 'lucide-react'
import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { XiaobingAvatar } from '@/components/ui/XiaobingAvatar'
import { ChatArtifactRenderer } from './artifacts/ChatArtifactRenderer'
import { parseChatArtifacts, sanitizeVisibleAssistantContent, streamingArtifactPreview, type ChatArtifactAction } from './artifacts/chatArtifacts'

interface MessageBubbleProps {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  isStreaming?: boolean
  onArtifactAction?: (action: ChatArtifactAction) => void
}

export function MessageBubble({
  id,
  role,
  content,
  timestamp,
  isStreaming,
  onArtifactAction,
}: MessageBubbleProps) {
  const isUser = role === 'user'
  const parsed = useMemo(
    () => isUser
      ? { content, artifacts: [] }
      : isStreaming
        ? { content: streamingArtifactPreview(content), artifacts: [] }
        : (() => {
            const result = parseChatArtifacts(id, content)
            return { ...result, content: sanitizeVisibleAssistantContent(result.content) }
          })(),
    [content, id, isStreaming, isUser],
  )
  const hasArtifacts = parsed.artifacts.length > 0

  return (
    <div
      className={`group flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}
      aria-live={isStreaming ? 'polite' : undefined}
    >
      {isUser ? (
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <User className="h-4 w-4" />
        </div>
      ) : (
        <XiaobingAvatar className="size-8 shrink-0 border border-sky-100 bg-sky-50 shadow-sm" />
      )}
      
      <div className={`min-w-0 rounded-2xl px-4 py-2.5 transition-[box-shadow,transform] duration-150 group-hover:-translate-y-0.5 group-hover:shadow-sm ${hasArtifacts ? 'max-w-[92%] lg:max-w-[860px]' : 'max-w-[80%]'} ${
        isUser
          ? 'bg-primary text-primary-foreground rounded-tr-sm'
          : 'bg-muted text-foreground rounded-tl-sm'
      }`}>
        {isUser ? (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">
            {content}
            {isStreaming && <span className="animate-pulse">▊</span>}
          </p>
        ) : (
          <div className="markdown-body text-sm leading-relaxed">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {parsed.content || (isStreaming ? ' ' : '')}
            </ReactMarkdown>
            {isStreaming && <span className="animate-pulse">▊</span>}
            {onArtifactAction
              ? parsed.artifacts.map((artifact) => (
                  <ChatArtifactRenderer
                    key={artifact.id}
                    artifact={artifact}
                    disabled={isStreaming}
                    onAction={onArtifactAction}
                  />
                ))
              : null}
          </div>
        )}
        <span className="mt-1 block text-[10px] opacity-60">
          {formatTime(timestamp)}
        </span>
      </div>
    </div>
  )
}

function formatTime(timestamp: number) {
  return new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
