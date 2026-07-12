import { useRef, useEffect, useState } from 'react'
import { BookCheck, Brain, MessageSquarePlus, MessagesSquare, Route } from 'lucide-react'
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
  const messagesPaneRef = useRef<HTMLDivElement>(null)
  const shouldAutoScrollRef = useRef(true)
  const previousMessageCountRef = useRef(0)
  const consumedPromptIdRef = useRef<number | null>(null)

  useEffect(() => {
    shouldAutoScrollRef.current = true
  }, [threadId, isLoadingHistory])

  useEffect(() => {
    const pane = messagesPaneRef.current
    if (!pane) return
    const messageCountChanged = messages.length !== previousMessageCountRef.current
    previousMessageCountRef.current = messages.length

    if (messageCountChanged && messages[messages.length - 1]?.role === 'user') {
      shouldAutoScrollRef.current = true
    }

    if (!shouldAutoScrollRef.current) return
    pane.scrollTo({ top: pane.scrollHeight, behavior: messageCountChanged ? 'smooth' : 'auto' })
  }, [messages])

  const handleMessagesScroll = () => {
    const pane = messagesPaneRef.current
    if (!pane) return
    const distanceFromBottom = pane.scrollHeight - pane.scrollTop - pane.clientHeight
    shouldAutoScrollRef.current = distanceFromBottom < 96
  }

  const pauseAutoScrollForReading = () => {
    if (isLoading) shouldAutoScrollRef.current = false
  }

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
  const handleLearningWrapUp = () => guardContextChange(() => sendMessage(
    '请帮我收口本次学习：用简短清单总结我学会了什么、暴露了什么问题、建议保存哪些词或表达，以及下一次最值得练什么。需要保存到长期学习资产的内容，请先让我确认。',
  ))
  const handleTransferPractice = () => guardContextChange(() => sendMessage(
    '请根据刚才的对话给我一道最小迁移练习，让我把刚学到的词汇、语法或表达用在一个新语境里。先只出题，等我回答后再反馈。',
  ))
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
    <div className="binn-page-canvas binn-viewport-height flex overflow-hidden overscroll-none">
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

      <section className="flex min-w-0 flex-1 flex-col bg-white/42">
        <div className="flex items-center justify-between border-b border-slate-200/70 bg-white/72 px-4 py-3 backdrop-blur-sm">
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

        <div
          ref={messagesPaneRef}
          data-header-scroll-surface
          className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain bg-[radial-gradient(circle_at_50%_24%,rgba(255,255,255,0.92),rgba(248,250,252,0.58)_48%,transparent_76%)] p-4"
          aria-live="polite"
          onPointerDown={pauseAutoScrollForReading}
          onScroll={handleMessagesScroll}
          onTouchStart={pauseAutoScrollForReading}
          onWheel={pauseAutoScrollForReading}
        >
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
                id={msg.id}
                role={msg.role}
                content={msg.content}
                timestamp={msg.timestamp}
                isStreaming={isLoading && msg.role === 'assistant' && msg === messages[messages.length - 1]}
                onArtifactAction={(prompt) => guardContextChange(() => sendMessage(prompt))}
              />
            ))
          )}
          {isLoading && messages[messages.length - 1]?.content === '' && (
            <TypingIndicator />
          )}
          {!isLoading && messages.length > 1 && messages[messages.length - 1]?.role === 'assistant' ? (
            <div className="mx-auto flex w-full max-w-3xl flex-wrap gap-2 rounded-xl border border-indigo-100 bg-indigo-50/70 p-3">
              <p className="w-full text-xs font-bold text-indigo-800">把这次对话变成可继续的学习记录</p>
              <Button variant="secondary" className="px-3 py-2 text-xs" onClick={handleLearningWrapUp}>
                <BookCheck className="size-4" />收口本次学习
              </Button>
              <Button variant="secondary" className="px-3 py-2 text-xs" onClick={handleTransferPractice}>
                <Route className="size-4" />做一道迁移练习
              </Button>
            </div>
          ) : null}
        </div>

        <div className="border-t border-slate-200/70 bg-white/78 p-4 backdrop-blur-sm">
          {isLoading ? (
            <StatusBanner title="正在生成学习反馈">
              当前对话和草稿已经保留；需要切换任务时可以先取消，回来后仍能从这条会话继续。
            </StatusBanner>
          ) : null}
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
