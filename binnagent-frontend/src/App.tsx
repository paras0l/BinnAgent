import { useEffect, useState } from 'react'
import { Header } from './components/layout/Header'
import { ChatPage } from './pages/ChatPage'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import type { Learner } from './types'

function App() {
  const [activeTab, setActiveTab] = useState<'chat' | 'dashboard'>('chat')
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
    localStorage.removeItem('binnLearnerId')
    localStorage.removeItem('binnLearner')
    setCurrentLearner(null)
    setActiveTab('chat')
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
        learner={currentLearner}
        onLogout={handleLogout}
        onTabChange={setActiveTab}
      />
      <main className="pt-16">
        {activeTab === 'chat' ? (
          <ChatPage learner={currentLearner} />
        ) : (
          <DashboardPage learner={currentLearner} />
        )}
      </main>
    </div>
  )
}

export default App
