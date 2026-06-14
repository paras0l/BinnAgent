import { Bot, BookOpen, Compass, LogOut, User } from 'lucide-react'
import type { AppTab, Learner } from '@/types'

interface HeaderProps {
  activeTab: AppTab
  isLocked?: boolean
  lockMessage?: string
  learner: Learner
  onLogout: () => void
  onTabChange: (tab: AppTab) => void
}

export function Header({
  activeTab,
  isLocked = false,
  lockMessage = '',
  learner,
  onLogout,
  onTabChange,
}: HeaderProps) {
  const isTabDisabled = (tab: AppTab) => isLocked && tab !== 'chat'

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-16 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-full items-center justify-between px-6">
        <div className="flex items-center gap-2">
          <Bot className="h-6 w-6 text-primary" />
          <span className="text-xl font-bold text-foreground">BinnAgent</span>
        </div>
        
        <div className="flex items-center gap-4">
          <nav className="flex gap-1">
            <button
              onClick={() => onTabChange('chat')}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors sm:px-4 ${
                activeTab === 'chat'
                  ? 'bg-primary/10 font-medium text-primary'
                  : 'text-muted-foreground hover:bg-muted'
              }`}
            >
              <Bot className="h-4 w-4" />
              <span className="hidden sm:inline">AI对话</span>
            </button>
            <button
              onClick={() => onTabChange('explore')}
              disabled={isTabDisabled('explore')}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors sm:px-4 ${
                activeTab === 'explore'
                  ? 'bg-primary/10 font-medium text-primary'
                  : 'text-muted-foreground hover:bg-muted'
              } disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent`}
              title={isTabDisabled('explore') ? '回答生成中，请先等待完成或取消' : '探索'}
            >
              <Compass className="h-4 w-4" />
              <span className="hidden sm:inline">探索</span>
            </button>
            <button
              onClick={() => onTabChange('dashboard')}
              disabled={isTabDisabled('dashboard')}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors sm:px-4 ${
                activeTab === 'dashboard'
                  ? 'bg-primary/10 font-medium text-primary'
                  : 'text-muted-foreground hover:bg-muted'
              } disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent`}
              title={isTabDisabled('dashboard') ? '回答生成中，请先等待完成或取消' : '学习中心'}
            >
              <BookOpen className="h-4 w-4" />
              <span className="hidden sm:inline">学习中心</span>
            </button>
          </nav>

          {isLocked && (
            <div className="hidden rounded-lg border border-warning/30 bg-warning/5 px-3 py-2 text-xs text-foreground lg:block">
              {lockMessage || '回答生成中，请先等待完成或取消。'}
            </div>
          )}

          <div className="flex items-center gap-2 border-l pl-4">
            <User className="h-4 w-4 text-muted-foreground" />
            <span className="max-w-28 truncate text-sm font-medium text-foreground">
              {learner.nickname}
            </span>
            <button
              onClick={onLogout}
              disabled={isLocked}
              className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
              title={isLocked ? '回答生成中，请先等待完成或取消' : '切换学习者'}
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}
