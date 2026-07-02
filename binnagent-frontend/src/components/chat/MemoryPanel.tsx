import {
  BookMarked,
  Brain,
  CircleAlert,
  Clock3,
  MessageSquareText,
  PanelRightClose,
  PanelRightOpen,
} from 'lucide-react'
import type { MemorySummary } from '@/types'

interface MemoryPanelProps {
  memory: MemorySummary | null
  isCollapsed: boolean
  onToggleCollapsed: () => void
}

export function MemoryPanel({ memory, isCollapsed, onToggleCollapsed }: MemoryPanelProps) {
  if (isCollapsed) {
    return (
      <aside className="hidden w-14 shrink-0 border-l bg-background xl:flex xl:flex-col xl:items-center xl:py-3">
        <button
          onClick={onToggleCollapsed}
          className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          title="展开学习状态"
        >
          <PanelRightOpen className="h-4 w-4" />
        </button>
        <Brain className="mt-2 h-4 w-4 text-primary" />
      </aside>
    )
  }

  return (
    <aside className="fixed bottom-0 right-0 top-16 z-40 flex w-80 shrink-0 flex-col border-l bg-background shadow-lg xl:static xl:shadow-none">
      <div className="border-b p-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-primary" />
            <h2 className="text-sm font-semibold text-foreground">学习状态</h2>
          </div>
          <button
            onClick={onToggleCollapsed}
            className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            title="收起学习状态"
          >
            <PanelRightClose className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          来自真实对话、词汇复习和课程记录
        </p>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {!memory ? (
          <p className="rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
            正在整理学习状态...
          </p>
        ) : (
          <>
            <section className="rounded-lg border p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
                <MessageSquareText className="h-4 w-4 text-primary" />
                对话记录
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <MemoryStat label="对话" value={memory.stats.conversation_count} />
                <MemoryStat label="消息" value={memory.stats.message_count} />
              </div>
              <p className="mt-3 text-sm text-muted-foreground">
                {memory.latest_thread_summary ||
                  memory.latest_thread_title ||
                  '还没有形成对话摘要。持续对话后，我会总结你正在学什么。'}
              </p>
            </section>

            <section className="rounded-lg border p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
                <BookMarked className="h-4 w-4 text-accent" />
                词汇进度
              </div>
              <div className="grid grid-cols-3 gap-2 text-sm">
                <MemoryStat label="总词汇" value={memory.stats.total_vocab} />
                <MemoryStat label="待复习" value={memory.stats.due_reviews} />
                <MemoryStat label="已掌握" value={memory.stats.mastered_vocab} />
              </div>
            </section>

            <section className="rounded-lg border p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
                <CircleAlert className="h-4 w-4 text-warning" />
                错因 Top 5
              </div>
              {memory.error_patterns.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  暂无错因记录。完成练习后这里会沉淀薄弱点。
                </p>
              ) : (
                <div className="space-y-2">
                  {memory.error_patterns.map((pattern) => (
                    <div key={pattern.id} className="rounded-md bg-muted p-2">
                      <p className="text-sm font-medium text-foreground">{pattern.name}</p>
                      <p className="text-xs text-muted-foreground">{pattern.count} 次</p>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="rounded-lg border p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-medium text-foreground">
                <Clock3 className="h-4 w-4 text-success" />
                最近学习
              </div>
              {memory.recent_sessions.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  暂无课程记录。开始每日课程后，这里会展示学习总结。
                </p>
              ) : (
                <div className="space-y-2">
                  {memory.recent_sessions.map((session) => (
                    <div key={session.id} className="rounded-md bg-muted p-2">
                      <p className="text-sm text-foreground">
                        {session.summary || session.active_skill || '学习 session 已完成'}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </aside>
  )
}

function MemoryStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-muted p-2">
      <p className="text-lg font-bold text-foreground">{value}</p>
      <p className="text-[11px] text-muted-foreground">{label}</p>
    </div>
  )
}
