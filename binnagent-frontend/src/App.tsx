import { useState } from 'react'
import { Header } from './components/layout/Header'
import { ChatPage } from './pages/ChatPage'
import { DashboardPage } from './pages/DashboardPage'

function App() {
  const [activeTab, setActiveTab] = useState<'chat' | 'dashboard'>('chat')

  return (
    <div className="min-h-screen bg-background">
      <Header activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="pt-16">
        {activeTab === 'chat' ? <ChatPage /> : <DashboardPage />}
      </main>
    </div>
  )
}

export default App
