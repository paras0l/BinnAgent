import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import {
  Bot,
  BookOpen,
  Check,
  ChevronDown,
  Compass,
  Copy,
  KeyRound,
  LogOut,
  MessageCircle,
  Sparkles,
  Settings,
  User,
} from 'lucide-react'
import type { AppTab, Learner } from '@/types'
import bookmarkPull from '@/assets/header/bookmark-pull.png'
import { XiaobingAvatar } from '@/components/ui/XiaobingAvatar'
import { copyTextToClipboard } from '@/utils/clipboard'

interface HeaderProps {
  activeTab: AppTab
  isLocked?: boolean
  learner: Learner
  onLogout: () => void
  onOpenGroupLearningSettings: () => void
  onOpenLearningSettings: () => void
  onOpenPetSpiritSettings: () => void
  onTabChange: (tab: AppTab) => void
}

export function Header({
  activeTab,
  isLocked = false,
  learner,
  onLogout,
  onOpenGroupLearningSettings,
  onOpenLearningSettings,
  onOpenPetSpiritSettings,
  onTabChange,
}: HeaderProps) {
  const isTabDisabled = (tab: AppTab) => isLocked && tab !== 'chat'
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [isInviteCopied, setIsInviteCopied] = useState(false)
  const [isHeaderCollapsed, setIsHeaderCollapsed] = useState(false)
  const [isPullVisible, setIsPullVisible] = useState(false)
  const [isPullRestoring, setIsPullRestoring] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const lastScrollYRef = useRef(0)
  const lastScrollSourceRef = useRef<EventTarget | null>(null)
  const isHeaderCollapsedRef = useRef(false)
  const suppressCollapseUntilRef = useRef(0)
  const pullStartYRef = useRef<number | null>(null)
  const isPullRestoringRef = useRef(false)
  const restoreHeaderTimerRef = useRef<number | null>(null)
  const hidePullTimerRef = useRef<number | null>(null)

  const copyInviteCode = async () => {
    if (!learner.invite_code) return
    setIsInviteCopied(await copyTextToClipboard(learner.invite_code))
  }

  useEffect(() => {
    if (!isMenuOpen) return
    const onPointerDown = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setIsMenuOpen(false)
    }
    window.addEventListener('pointerdown', onPointerDown)
    return () => window.removeEventListener('pointerdown', onPointerDown)
  }, [isMenuOpen])

  useEffect(() => {
    suppressCollapseUntilRef.current = Date.now() + 1200
    lastScrollYRef.current = window.scrollY
    lastScrollSourceRef.current = document
    let frame = 0

    const onScroll = (event: Event) => {
      const source = event.target
      const isWindowScroll = source === document
      const isDesignatedSurface = source instanceof HTMLElement
        && source.hasAttribute('data-header-scroll-surface')
      if (!isWindowScroll && !isDesignatedSurface) return

      if (frame) return
      frame = window.requestAnimationFrame(() => {
        frame = 0
        const nextScrollY = Math.max(
          isDesignatedSurface ? (source as HTMLElement).scrollTop : window.scrollY,
          0,
        )
        const previousScrollY = lastScrollSourceRef.current === source
          ? lastScrollYRef.current
          : nextScrollY
        const scrollDelta = nextScrollY - previousScrollY

        if (
          nextScrollY >= 112
          && scrollDelta > 0
          && !isHeaderCollapsedRef.current
          && !isPullRestoringRef.current
          && Date.now() >= suppressCollapseUntilRef.current
        ) {
          isHeaderCollapsedRef.current = true
          setIsHeaderCollapsed(true)
          setIsPullVisible(true)
          setIsMenuOpen(false)
        }

        lastScrollYRef.current = nextScrollY
        lastScrollSourceRef.current = source
      })
    }

    window.addEventListener('scroll', onScroll, { capture: true, passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll, { capture: true })
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [])

  useEffect(() => () => {
    if (restoreHeaderTimerRef.current !== null) window.clearTimeout(restoreHeaderTimerRef.current)
    if (hidePullTimerRef.current !== null) window.clearTimeout(hidePullTimerRef.current)
  }, [])

  const restoreHeader = () => {
    if (!isHeaderCollapsedRef.current || isPullRestoringRef.current) return
    isPullRestoringRef.current = true
    suppressCollapseUntilRef.current = Date.now() + 900
    setIsPullRestoring(true)
    pullStartYRef.current = null

    restoreHeaderTimerRef.current = window.setTimeout(() => {
      isHeaderCollapsedRef.current = false
      setIsHeaderCollapsed(false)
    }, 118)

    hidePullTimerRef.current = window.setTimeout(() => {
      setIsPullVisible(false)
      setIsPullRestoring(false)
      isPullRestoringRef.current = false
    }, 520)
  }

  const onPullStart = (event: ReactPointerEvent<HTMLButtonElement>) => {
    pullStartYRef.current = event.clientY
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const onPullMove = (event: ReactPointerEvent<HTMLButtonElement>) => {
    const pullStartY = pullStartYRef.current
    if (pullStartY === null || event.clientY - pullStartY < 24) return
    restoreHeader()
  }

  const onPullEnd = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    pullStartYRef.current = null
  }

  return (
    <header
      className="binn-header fixed top-0 left-0 right-0 z-50 h-16 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
      data-collapsed={isHeaderCollapsed}
      data-restoring={isPullRestoring}
    >
      <div className="binn-header__content flex h-full items-center justify-between px-3 sm:px-6">
        <div className="flex items-center gap-2">
          <XiaobingAvatar className="size-8 border border-sky-100 bg-sky-50 shadow-sm" />
          <span className="hidden text-xl font-bold text-foreground sm:inline">BinnAgent</span>
        </div>
        
        <div className="flex items-center gap-1 sm:gap-4">
          <nav className="flex gap-0.5 sm:gap-1">
            <button
              onClick={() => onTabChange('chat')}
              className={`flex items-center gap-2 rounded-full px-2.5 py-2 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-primary sm:px-4 ${
                activeTab === 'chat'
                  ? 'bg-primary/10 font-bold text-primary shadow-[0_2px_8px_rgba(99,102,241,0.12)]'
                  : 'text-muted-foreground hover:bg-indigo-50/70 hover:text-indigo-700'
              }`}
            >
              <Bot className="h-4 w-4" />
              <span className="hidden sm:inline">AI对话</span>
            </button>
            <button
              onClick={() => onTabChange('explore')}
              disabled={isTabDisabled('explore')}
              className={`flex items-center gap-2 rounded-full px-2.5 py-2 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-primary sm:px-4 ${
                activeTab === 'explore'
                  ? 'bg-primary/10 font-bold text-primary shadow-[0_2px_8px_rgba(99,102,241,0.12)]'
                  : 'text-muted-foreground hover:bg-indigo-50/70 hover:text-indigo-700'
              } disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent`}
              title={isTabDisabled('explore') ? '回答生成中，请先等待完成或取消' : '探索'}
            >
              <Compass className="h-4 w-4" />
              <span className="hidden sm:inline">探索</span>
            </button>
            <button
              onClick={() => onTabChange('dashboard')}
              disabled={isTabDisabled('dashboard')}
              className={`flex items-center gap-2 rounded-full px-2.5 py-2 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-primary sm:px-4 ${
                activeTab === 'dashboard'
                  ? 'bg-primary/10 font-bold text-primary shadow-[0_2px_8px_rgba(99,102,241,0.12)]'
                  : 'text-muted-foreground hover:bg-indigo-50/70 hover:text-indigo-700'
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
              onClick={() => {
                setIsInviteCopied(false)
                setIsMenuOpen((value) => !value)
              }}
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
                {learner.invite_code ? (
                  <div className="mx-1 mt-2 flex items-center gap-2 rounded-lg border border-indigo-100 bg-indigo-50/70 px-3 py-2.5">
                    <KeyRound className="size-4 shrink-0 text-indigo-600" />
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] font-bold text-indigo-600">我的邀请码</p>
                      <code className="block truncate text-xs font-black tracking-wide text-indigo-950">
                        {learner.invite_code}
                      </code>
                    </div>
                    <button
                      type="button"
                      onClick={() => void copyInviteCode()}
                      className="inline-flex size-8 shrink-0 items-center justify-center rounded-md text-indigo-600 transition hover:bg-indigo-100 focus-visible:outline-2 focus-visible:outline-primary"
                      aria-label={isInviteCopied ? '邀请码已复制' : '复制邀请码'}
                      title={isInviteCopied ? '已复制' : '复制邀请码'}
                    >
                      {isInviteCopied ? <Check className="size-4" /> : <Copy className="size-4" />}
                    </button>
                  </div>
                ) : null}
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setIsMenuOpen(false)
                    onOpenPetSpiritSettings()
                  }}
                  className="mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-bold text-slate-700 transition hover:bg-sky-50 hover:text-sky-700 focus-visible:outline-2 focus-visible:outline-primary"
                >
                  <Sparkles className="size-4" />
                  宠物精灵设置
                </button>
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
      {isPullVisible ? (
        <button
          type="button"
          className="binn-header__pull"
          aria-label="展开顶部菜单"
          title="点击或向下拉动，展开顶部菜单"
          onClick={restoreHeader}
          onPointerDown={onPullStart}
          onPointerMove={onPullMove}
          onPointerUp={onPullEnd}
          onPointerCancel={onPullEnd}
        >
          <span className="binn-header__pull-art" aria-hidden="true"><img src={bookmarkPull} alt="" draggable={false} /></span>
          <span className="sr-only">点击或向下拉动以展开顶部菜单</span>
        </button>
      ) : null}
    </header>
  )
}
