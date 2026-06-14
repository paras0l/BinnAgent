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
  draft: string
  onDraftChange: (value: string) => void
  skillFocus: string | null
  onSkillFocusChange: (value: string | null) => void
  onGeneratingChange: (isGenerating: boolean) => void
  onLockedAction: () => void
}

export function ChatContainer({
  learnerId,
  draft,
  onDraftChange,
  skillFocus,
  onSkillFocusChange,
  onGeneratingChange,
  onLockedAction,
}: ChatContainerProps) {
  const {
    messages,
    threadId,
    conversations,
    memorySummary,
    skillStatus,
    activeSkillId,
    activeSkillName,
    sendMessage,
    cancel,
    exitSkill,
    loadThread,
    startNewConversation,
    isLoading,
    isLoadingHistory,
  } = useChat(learnerId, { onGeneratingChange })
  const [isHistoryCollapsed, setIsHistoryCollapsed] = useState(true)
  const [isMemoryCollapsed, setIsMemoryCollapsed] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const guardContextChange = (action: () => void) => {
    if (isLoading) {
      onLockedAction()
      return
    }
    action()
  }

  const handleStartLesson = () => guardContextChange(() => sendMessage('开始一节对话课'))
  const handleReviewVocab = () => guardContextChange(() => sendMessage('我想复习今天的词汇'))
  const handlePracticeSpeaking = () => guardContextChange(() => sendMessage('我想练习口语场景'))
  const handleSendMessage = (content: string) => {
    onDraftChange('')
    sendMessage(content, skillFocus)
  }
  const handleNewConversation = () =>
    guardContextChange(() => {
      startNewConversation()
      onSkillFocusChange(null)
    })
  const handleSelectThread = (nextThreadId: string) =>
    guardContextChange(() => {
      onSkillFocusChange(null)
      void loadThread(nextThreadId)
    })
  const handleExitSkill = () => {
    onSkillFocusChange(null)
    void exitSkill()
  }
  const activeConversation = conversations.find((conversation) => conversation.thread_id === threadId)
  const currentSkillId = activeSkillId || skillFocus
  const currentSkillName = activeSkillName || (currentSkillId === 'vocabulary_deposit' ? '词汇 Skill' : null)

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      <ConversationSidebar
        conversations={conversations}
        activeThreadId={threadId}
        isCollapsed={isHistoryCollapsed}
        onToggleCollapsed={() => setIsHistoryCollapsed(prev => !prev)}
        isLocked={isLoading}
        onNewConversation={handleNewConversation}
        onSelectThread={handleSelectThread}
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
              onClick={handleNewConversation}
              disabled={isLoading}
              className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
              title={isLoading ? '回答生成中，请先等待完成或取消' : '新建对话'}
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
              isLocked={isLoading}
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
          {(currentSkillId || skillStatus) && (
            <div className="mb-3 flex flex-col gap-2 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2 text-sm text-primary sm:flex-row sm:items-center sm:justify-between">
              <span>
                {skillStatus ||
                  `${currentSkillName || 'Agent Skill'} 已启用：本会话会持续沉淀高质量词卡。`}
              </span>
              {currentSkillId && (
                <button
                  type="button"
                  onClick={handleExitSkill}
                  disabled={isLoading}
                  className="self-start rounded-md border border-primary/30 px-2 py-1 text-xs font-medium transition-colors hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-50 sm:self-auto"
                >
                  退出 Skill
                </button>
              )}
            </div>
          )}
          <ChatInput
            onSend={handleSendMessage}
            onCancel={cancel}
            isLoading={isLoading}
            message={draft}
            onMessageChange={onDraftChange}
          />
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
