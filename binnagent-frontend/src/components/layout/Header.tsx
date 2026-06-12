import { Bot, BookOpen } from 'lucide-react'

interface HeaderProps {
  activeTab: 'chat' | 'dashboard'
  onTabChange: (tab: 'chat' | 'dashboard') => void
}

export function Header({ activeTab, onTabChange }: HeaderProps) {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-16 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-full items-center justify-between px-6">
        <div className="flex items-center gap-2">
          <Bot className="h-6 w-6 text-primary" />
          <span className="text-xl font-bold text-foreground">BinnAgent</span>
        </div>
        
        <nav className="flex gap-1">
          <button
            onClick={() => onTabChange('chat')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              activeTab === 'chat'
                ? 'bg-primary/10 text-primary font-medium'
                : 'text-muted-foreground hover:bg-muted'
            }`}
          >
            <Bot className="h-4 w-4" />
            AI对话
          </button>
          <button
            onClick={() => onTabChange('dashboard')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              activeTab === 'dashboard'
                ? 'bg-primary/10 text-primary font-medium'
                : 'text-muted-foreground hover:bg-muted'
            }`}
          >
            <BookOpen className="h-4 w-4" />
            学习中心
          </button>
        </nav>
      </div>
    </header>
  )
}
