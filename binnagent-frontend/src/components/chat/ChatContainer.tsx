import { useRef, useEffect, useState } from 'react'
import { Brain, MessageSquarePlus, MessagesSquare } from 'lucide-react'
import { useChat } from '@/hooks/useChat'
import { MessageBubble } from './MessageBubble'
import { ChatInput } from './ChatInput'
import { TypingIndicator } from './TypingIndicator'
import { WelcomeScreen } from './WelcomeScreen'
import { ConversationSidebar } from './ConversationSidebar'
import { MemoryPanel } from './MemoryPanel'
import { Button } from '@/components/ui/Button'
import { IconButton } from '@/components/ui/IconButton'
import { StatusBanner } from '@/components/ui/StatusBanner'
import { useMediaQuery } from '@/hooks/useMediaQuery'

interface ChatContainerProps {
  learnerId: string
  draft: string
  onDraftChange: (value: string) => void
  pendingPrompt?: {
    id: number
    prompt: string
    skillFocus: string | null
  } | null
  onPendingPromptConsumed?: () => void
  skillFocus: string | null
  onSkillFocusChange: (value: string | null) => void
  onGeneratingChange: (isGenerating: boolean) => void
  onLockedAction: () => void
}

export function ChatContainer({
  learnerId,
  draft,
  onDraftChange,
  pendingPrompt = null,
  onPendingPromptConsumed,
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
  const isHistoryDrawer = useMediaQuery('(max-width: 1023px)')
  const isMemoryDrawer = useMediaQuery('(max-width: 1279px)')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const consumedPromptIdRef = useRef<number | null>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (!pendingPrompt || isLoading || isLoadingHistory) return
    if (consumedPromptIdRef.current === pendingPrompt.id) return
    consumedPromptIdRef.current = pendingPrompt.id
    onDraftChange('')
    onSkillFocusChange(pendingPrompt.skillFocus)
    void sendMessage(pendingPrompt.prompt, pendingPrompt.skillFocus)
    onPendingPromptConsumed?.()
  }, [
    isLoading,
    isLoadingHistory,
    onDraftChange,
    onPendingPromptConsumed,
    onSkillFocusChange,
    pendingPrompt,
    sendMessage,
  ])

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
    if (isLoadingHistory) {
      onLockedAction()
      return
    }
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
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      <ConversationSidebar
        conversations={conversations}
        activeThreadId={threadId}
        isCollapsed={isHistoryCollapsed}
        isModal={isHistoryDrawer}
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
              {threadId ? '正在使用该会话的历史上下文' : '发送第一条消息后会创建新的学习会话'}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <IconButton
              onClick={() => setIsHistoryCollapsed(prev => !prev)}
              label={isHistoryCollapsed ? '展开历史对话' : '收起历史对话'}
              aria-expanded={!isHistoryCollapsed}
              className="border-border text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <MessagesSquare className="h-4 w-4" />
            </IconButton>
            <IconButton
              onClick={() => setIsMemoryCollapsed(prev => !prev)}
              label={isMemoryCollapsed ? '展开学习状态' : '收起学习状态'}
              aria-expanded={!isMemoryCollapsed}
              className="border-border text-muted-foreground hover:bg-muted hover:text-foreground"
            >
              <Brain className="h-4 w-4" />
            </IconButton>
            <Button
              variant="secondary"
              onClick={handleNewConversation}
              disabled={isLoading}
              title={isLoading ? '回答生成中，请先等待完成或取消' : '新建对话'}
              className="px-3 py-2"
            >
              <MessageSquarePlus className="h-4 w-4" />
              新建
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4" aria-live="polite">
          {isLoadingHistory ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              正在恢复最近对话…
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
            <StatusBanner
              title={currentSkillId ? 'Agent Skill 已启用' : '对话状态'}
              action={currentSkillId && (
                <Button
                  variant="secondary"
                  onClick={handleExitSkill}
                  disabled={isLoading}
                  className="px-2 py-1 text-xs"
                >
                  退出 Skill
                </Button>
              )}
            >
                {skillStatus ||
                  `${currentSkillName || 'Agent Skill'} 已启用：本会话会持续沉淀高质量词卡。`}
            </StatusBanner>
          )}
          <ChatInput
            onSend={handleSendMessage}
            onCancel={cancel}
            isLoading={isLoading}
            isDisabled={isLoadingHistory}
            message={draft}
            onMessageChange={onDraftChange}
          />
        </div>
      </section>

      <MemoryPanel
        memory={memorySummary}
        isCollapsed={isMemoryCollapsed}
        isModal={isMemoryDrawer}
        onToggleCollapsed={() => setIsMemoryCollapsed(prev => !prev)}
      />
    </div>
  )
}
