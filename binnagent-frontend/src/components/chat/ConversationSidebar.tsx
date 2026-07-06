import { MessageSquarePlus, MessagesSquare, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import type { ConversationThread } from '@/types'
import { Button } from '@/components/ui/Button'
import { IconButton } from '@/components/ui/IconButton'

interface ConversationSidebarProps {
  conversations: ConversationThread[]
  activeThreadId: string | null
  isCollapsed: boolean
  isLocked?: boolean
  onToggleCollapsed: () => void
  onNewConversation: () => void
  onSelectThread: (threadId: string) => void
}

export function ConversationSidebar({
  conversations,
  activeThreadId,
  isCollapsed,
  isLocked = false,
  onToggleCollapsed,
  onNewConversation,
  onSelectThread,
}: ConversationSidebarProps) {
  if (isCollapsed) {
    return (
      <aside className="hidden w-14 shrink-0 border-r bg-background lg:flex lg:flex-col lg:items-center lg:gap-2 lg:py-3">
        <IconButton
          onClick={onToggleCollapsed}
          label="展开历史对话"
          className="border-transparent text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <PanelLeftOpen className="h-4 w-4" />
        </IconButton>
        <IconButton
          onClick={onNewConversation}
          disabled={isLocked}
          label={isLocked ? '回答生成中，请先等待完成或取消' : '新建对话'}
          className="border-transparent text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <MessageSquarePlus className="h-4 w-4" />
        </IconButton>
      </aside>
    )
  }

  return (
    <aside className="fixed bottom-0 left-0 top-16 z-40 flex w-72 shrink-0 flex-col overscroll-contain border-r bg-background shadow-lg lg:static lg:shadow-none">
      <div className="space-y-3 border-b p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <MessagesSquare className="h-4 w-4 text-primary" />
            历史对话
          </div>
          <IconButton
            onClick={onToggleCollapsed}
            label="收起历史对话"
            className="border-transparent text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <PanelLeftClose className="h-4 w-4" />
          </IconButton>
        </div>
        <Button
          onClick={onNewConversation}
          disabled={isLocked}
          title={isLocked ? '回答生成中，请先等待完成或取消' : '新建对话'}
          className="w-full px-3 py-2"
        >
          <MessageSquarePlus className="h-4 w-4" />
          新建对话
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {conversations.length === 0 ? (
          <p className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
            暂无历史对话。开始聊天后，这里会保存你的学习上下文。
          </p>
        ) : (
          <div className="space-y-2">
            {conversations.map((conversation) => (
              <button
                type="button"
                key={conversation.thread_id}
                onClick={() => onSelectThread(conversation.thread_id)}
                disabled={isLocked}
                className={`w-full rounded-lg border p-3 text-left transition-[background-color,border-color,box-shadow] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 ${
                  activeThreadId === conversation.thread_id
                    ? 'border-primary bg-primary/5 shadow-sm'
                    : 'hover:bg-muted hover:shadow-sm'
                } disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-transparent`}
                title={isLocked ? '回答生成中，请先等待完成或取消' : conversation.title}
                aria-current={activeThreadId === conversation.thread_id ? 'page' : undefined}
              >
                <p className="truncate text-sm font-medium text-foreground">
                  {conversation.title}
                </p>
                <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                  {conversation.last_message || '暂无消息摘要'}
                </p>
                <p className="mt-2 text-[11px] text-muted-foreground">
                  {conversation.message_count} 条消息
                </p>
              </button>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
