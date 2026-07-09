import { useEffect, useRef, useState } from 'react'
import { Bot, ChevronDown, Compass, LogOut, MessageCircle, Settings, User } from 'lucide-react'
import type { AppTab, Learner } from '@/types'

interface HeaderProps {
  activeTab: AppTab
  isLocked?: boolean
  learner: Learner
  onLogout: () => void
  onOpenGroupLearningSettings: () => void
  onOpenLearningSettings: () => void
  onTabChange: (tab: AppTab) => void
}

export function Header({
  activeTab,
  isLocked = false,
  learner,
  onLogout,
  onOpenGroupLearningSettings,
  onOpenLearningSettings,
  onTabChange,
}: HeaderProps) {
  const isTabDisabled = (tab: AppTab) => isLocked && tab !== 'chat'
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isMenuOpen) return
    const onPointerDown = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setIsMenuOpen(false)
    }
    window.addEventListener('pointerdown', onPointerDown)
    return () => window.removeEventListener('pointerdown', onPointerDown)
  }, [isMenuOpen])

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-16 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-full items-center justify-between px-3 sm:px-6">
        <div className="flex items-center gap-2">
          <Bot className="h-6 w-6 text-primary" />
          <span className="hidden text-xl font-bold text-foreground sm:inline">BinnAgent</span>
        </div>
        
        <div className="flex items-center gap-1 sm:gap-4">
          <nav className="flex gap-0.5 sm:gap-1">
            <button
              onClick={() => onTabChange('chat')}
              className={`flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-primary sm:px-4 ${
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
              className={`flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-primary sm:px-4 ${
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
              className={`flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-primary sm:px-4 ${
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

          <div className="relative border-l pl-1 sm:pl-4" ref={menuRef}>
            <button
              type="button"
              onClick={() => setIsMenuOpen((value) => !value)}
              className="inline-flex max-w-44 items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted active:bg-muted/80 focus-visible:outline-2 focus-visible:outline-primary"
              aria-expanded={isMenuOpen}
              aria-haspopup="menu"
            >
              <User className="h-4 w-4 text-muted-foreground" />
              <span className="hidden min-w-0 truncate md:block">{learner.nickname}</span>
              <ChevronDown className={`h-4 w-4 text-muted-foreground transition ${isMenuOpen ? 'rotate-180' : ''}`} />
            </button>

            {isMenuOpen ? (
              <div
                className="absolute right-0 top-[calc(100%+0.5rem)] w-72 rounded-lg border border-slate-200 bg-white p-2 shadow-xl"
                role="menu"
              >
                <div className="border-b border-slate-100 px-3 py-3">
                  <p className="truncate text-sm font-black text-slate-950">{learner.nickname}</p>
                  <p className="mt-1 truncate text-xs text-slate-500">
                    {learner.email ?? `学习者 ID ${learner.id.slice(0, 8)}`}
                  </p>
                </div>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setIsMenuOpen(false)
                    onOpenLearningSettings()
                  }}
                  className="mt-2 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-bold text-slate-700 transition hover:bg-slate-50 hover:text-indigo-700 focus-visible:outline-2 focus-visible:outline-primary"
                >
                  <Settings className="size-4" />
                  学习设置
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setIsMenuOpen(false)
                    onOpenGroupLearningSettings()
                  }}
                  className="mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-bold text-slate-700 transition hover:bg-slate-50 hover:text-teal-700 focus-visible:outline-2 focus-visible:outline-primary"
                >
                  <MessageCircle className="size-4" />
                  群聊学习线索设置
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setIsMenuOpen(false)
                    onLogout()
                  }}
                  disabled={isLocked}
                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-bold text-slate-700 transition hover:bg-slate-50 hover:text-rose-600 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent disabled:hover:text-slate-700"
                  title={isLocked ? '回答生成中，请先等待完成或取消' : '切换学习者'}
                >
                  <LogOut className="size-4" />
                  登出 / 切换学习者
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </header>
  )
}
