import { useEffect, useState } from 'react'
import { Header } from './components/layout/Header'
import { ChatPage } from './pages/ChatPage'
import { DashboardPage } from './pages/DashboardPage'
import { ExplorePage } from './pages/ExplorePage'
import { LoginPage } from './pages/LoginPage'
import type { AppTab, Learner } from './types'

function App() {
  const [activeTab, setActiveTab] = useState<AppTab>('chat')
  const [chatDraft, setChatDraft] = useState('')
  const [chatSkillFocus, setChatSkillFocus] = useState<string | null>(null)
  const [isChatGenerating, setIsChatGenerating] = useState(false)
  const [lockMessage, setLockMessage] = useState('')
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
      setLockMessage('回答生成中，请先等待完成或点击取消。')
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
      setLockMessage('回答生成中，请先等待完成或点击取消。')
      return
    }
    setChatDraft(prompt)
    setChatSkillFocus(skillFocus ?? null)
  }

  const handleTabChange = (tab: AppTab) => {
    if (isChatGenerating && tab !== 'chat') {
      setLockMessage('回答生成中，请先等待完成或点击取消。')
      return
    }
    setLockMessage('')
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
        lockMessage={lockMessage}
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
            onLockedAction={() => setLockMessage('回答生成中，请先等待完成或点击取消。')}
          />
        ) : activeTab === 'explore' ? (
          <ExplorePage
            learner={currentLearner}
            isLocked={isChatGenerating}
            onLockedAction={() => setLockMessage('回答生成中，请先等待完成或点击取消。')}
            onTabChange={handleTabChange}
            onDraftPrompt={handleDraftPrompt}
          />
        ) : (
          <DashboardPage learner={currentLearner} />
        )}
      </main>
    </div>
  )
}

export default App
