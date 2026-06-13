import { useRef, useEffect, useState } from 'react'
import { Brain, MessageSquarePlus, MessagesSquare } from 'lucide-react'
import { useChat } from '@/hooks/useChat'
import { MessageBubble } from './MessageBubble'
import { ChatInput } from './ChatInput'
import { TypingIndicator } from './TypingIndicator'
import { WelcomeScreen } from './WelcomeScreen'
import { ConversationSidebar } from './ConversationSidebar'
import { MemoryPanel } from './MemoryPanel'

interface ChatContainerProps {
  learnerId: string
}

export function ChatContainer({ learnerId }: ChatContainerProps) {
  const {
    messages,
    threadId,
    conversations,
    memorySummary,
    sendMessage,
    cancel,
    loadThread,
    startNewConversation,
    isLoading,
    isLoadingHistory,
  } = useChat(learnerId)
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(true)
  const [isMemoryCollapsed, setIsMemoryCollapsed] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleStartLesson = () => sendMessage('开始一节对话课')
  const handleReviewVocab = () => sendMessage('我想复习今天的词汇')
  const handlePracticeSpeaking = () => sendMessage('我想练习口语场景')
  const activeConversation = conversations.find((conversation) => conversation.thread_id === threadId)

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      <ConversationSidebar
        conversations={conversations}
        activeThreadId={threadId}
        isCollapsed={isHistoryCollapsed}
        onToggleCollapsed={() => setIsHistoryCollapsed(prev => !prev)}
        onNewConversation={startNewConversation}
        onSelectThread={(nextThreadId) => void loadThread(nextThreadId)}
      />

      <section className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">
              {activeConversation?.title || (threadId ? '当前对话' : '新对话')}
            </p>
            <p className="text-xs text-muted-foreground">
              {threadId ? '正在使用该会话的历史上下文' : '发送第一条消息后会创建新的记忆会话'}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <button
              onClick={() => setIsHistoryCollapsed(prev => !prev)}
              className="inline-flex rounded-lg border p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              title={isHistoryCollapsed ? '展开历史对话' : '收起历史对话'}
            >
              <MessagesSquare className="h-4 w-4" />
            </button>
            <button
              onClick={() => setIsMemoryCollapsed(prev => !prev)}
              className="inline-flex rounded-lg border p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              title={isMemoryCollapsed ? '展开记忆面板' : '收起记忆面板'}
            >
              <Brain className="h-4 w-4" />
            </button>
            <button
              onClick={startNewConversation}
              className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted"
            >
              <MessageSquarePlus className="h-4 w-4" />
              新建
            </button>
          </div>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {isLoadingHistory ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              正在恢复最近对话...
            </div>
          ) : messages.length === 0 ? (
            <WelcomeScreen
              onStartLesson={handleStartLesson}
              onReviewVocab={handleReviewVocab}
              onPracticeSpeaking={handlePracticeSpeaking}
            />
          ) : (
            messages.map(msg => (
              <MessageBubble
                key={msg.id}
                role={msg.role}
                content={msg.content}
                timestamp={msg.timestamp}
                isStreaming={isLoading && msg.role === 'assistant' && msg === messages[messages.length - 1]}
              />
            ))
          )}
          {isLoading && messages[messages.length - 1]?.content === '' && (
            <TypingIndicator />
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="border-t p-4">
          <ChatInput onSend={sendMessage} onCancel={cancel} isLoading={isLoading} />
        </div>
      </section>

      <MemoryPanel
        memory={memorySummary}
        isCollapsed={isMemoryCollapsed}
        onToggleCollapsed={() => setIsMemoryCollapsed(prev => !prev)}
      />
    </div>
  )
}
