import { lazy, Suspense, useEffect, useState } from 'react'
import { Header } from './components/layout/Header'
import { ChatPage } from './pages/ChatPage'
import { DashboardPage } from './pages/DashboardPage'
import { ExplorePage } from './pages/ExplorePage'
import { GrammarPage } from './pages/GrammarPage'
import { LoginPage } from './pages/LoginPage'
import { PronunciationPage } from './pages/PronunciationPage'
import { useToast } from './hooks/useToast'
import type { AppTab, Learner } from './types'

const KnowledgeBasePage = lazy(() =>
  import('./pages/KnowledgeBasePage').then((module) => ({ default: module.KnowledgeBasePage }))
)

function App() {
  const { showToast } = useToast()
  const [activeTab, setActiveTab] = useState<AppTab>('chat')
  const [learningCenterView, setLearningCenterView] = useState<'home' | 'daily-learning'>('home')
  const [chatDraft, setChatDraft] = useState('')
  const [chatSkillFocus, setChatSkillFocus] = useState<string | null>(null)
  const [isChatGenerating, setIsChatGenerating] = useState(false)
  const [currentLearner, setCurrentLearner] = useState<Learner | null>(() => {
    const cached = localStorage.getItem('binnLearner')
    if (!cached) return null
    try {
      return JSON.parse(cached) as Learner
    } catch {
      return null
    }
  })
  const [isRestoringLearner, setIsRestoringLearner] = useState(() =>
    Boolean(localStorage.getItem('binnLearnerId'))
  )

  useEffect(() => {
    const learnerId = localStorage.getItem('binnLearnerId')
    if (!learnerId) return

    fetch(`/api/learners/${learnerId}`)
      .then((response) => {
        if (!response.ok) throw new Error('Learner not found')
        return response.json() as Promise<Learner>
      })
      .then((learner) => {
        localStorage.setItem('binnLearner', JSON.stringify(learner))
        setCurrentLearner(learner)
      })
      .catch(() => {
        localStorage.removeItem('binnLearnerId')
        localStorage.removeItem('binnLearner')
        setCurrentLearner(null)
      })
      .finally(() => setIsRestoringLearner(false))
  }, [])

  const handleLogout = () => {
    if (isChatGenerating) {
      showToast('回答生成中，请先等待完成或点击取消。', { variant: 'warning' })
      return
    }
    localStorage.removeItem('binnLearnerId')
    localStorage.removeItem('binnLearner')
    setCurrentLearner(null)
    setActiveTab('chat')
    setChatDraft('')
    setChatSkillFocus(null)
  }

  const handleDraftPrompt = (prompt: string, skillFocus?: string | null) => {
    if (isChatGenerating) {
      showToast('回答生成中，请先等待完成或点击取消。', { variant: 'warning' })
      return
    }
    setChatDraft(prompt)
    setChatSkillFocus(skillFocus ?? null)
  }

  const handleTabChange = (tab: AppTab) => {
    if (isChatGenerating && tab !== 'chat') {
      showToast('回答生成中，请先等待完成或点击取消。', { variant: 'warning' })
      return
    }
    if (tab === 'dashboard') setLearningCenterView('home')
    setActiveTab(tab)
  }

  if (isRestoringLearner) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-sm text-muted-foreground">
        正在恢复学习空间...
      </div>
    )
  }

  if (!currentLearner) {
    return <LoginPage onLogin={setCurrentLearner} />
  }

  return (
    <div className="min-h-screen bg-background">
      <Header
        activeTab={activeTab}
        isLocked={isChatGenerating}
        learner={currentLearner}
        onLogout={handleLogout}
        onTabChange={handleTabChange}
      />
      <main className="pt-16">
        {activeTab === 'chat' ? (
          <ChatPage
            learner={currentLearner}
            draft={chatDraft}
            onDraftChange={setChatDraft}
            skillFocus={chatSkillFocus}
            onSkillFocusChange={setChatSkillFocus}
            onGeneratingChange={setIsChatGenerating}
            onLockedAction={() => {
              showToast('回答生成中，请先等待完成或点击取消。', { variant: 'warning' })
            }}
          />
        ) : activeTab === 'explore' ? (
          <ExplorePage
            learner={currentLearner}
            isLocked={isChatGenerating}
            onLockedAction={() => {
              showToast('回答生成中，请先等待完成或点击取消。', { variant: 'warning' })
            }}
            onTabChange={handleTabChange}
            onDraftPrompt={handleDraftPrompt}
          />
        ) : activeTab === 'pronunciation' ? (
          <PronunciationPage learner={currentLearner} />
        ) : activeTab === 'grammar' ? (
          <GrammarPage learner={currentLearner} onTabChange={handleTabChange} />
        ) : (
          learningCenterView === 'daily-learning' ? (
            <Suspense fallback={<div className="flex min-h-[calc(100vh-4rem)] items-center justify-center text-sm text-muted-foreground">正在打开每日学习...</div>}>
              <KnowledgeBasePage
                learner={currentLearner}
                onBack={() => setLearningCenterView('home')}
              />
            </Suspense>
          ) : (
            <DashboardPage
              learner={currentLearner}
              onOpenDailyLearning={() => setLearningCenterView('daily-learning')}
            />
          )
        )}
      </main>
    </div>
  )
}

export default App
