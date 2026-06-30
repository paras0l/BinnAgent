import { lazy, Suspense, useEffect, useState } from 'react'
import { Header } from './components/layout/Header'
import { useToast } from './hooks/useToast'
import type { VocabularyPracticeMode } from './pages/VocabularyPracticePage'
import type { AppTab, Learner, PronunciationWorkspace } from './types'

const ChatPage = lazy(() =>
  import('./pages/ChatPage').then((module) => ({ default: module.ChatPage }))
)

const DashboardPage = lazy(() =>
  import('./pages/DashboardPage').then((module) => ({ default: module.DashboardPage }))
)

const ExplorePage = lazy(() =>
  import('./pages/ExplorePage').then((module) => ({ default: module.ExplorePage }))
)

const GrammarPage = lazy(() =>
  import('./pages/GrammarPage').then((module) => ({ default: module.GrammarPage }))
)

const KnowledgeBasePage = lazy(() =>
  import('./pages/KnowledgeBasePage').then((module) => ({ default: module.KnowledgeBasePage }))
)

const LoginPage = lazy(() =>
  import('./pages/LoginPage').then((module) => ({ default: module.LoginPage }))
)

const MemoryCenterPage = lazy(() =>
  import('./pages/MemoryCenterPage').then((module) => ({ default: module.MemoryCenterPage }))
)

const PronunciationPage = lazy(() =>
  import('./pages/PronunciationPage').then((module) => ({ default: module.PronunciationPage }))
)

const VocabularyPracticePage = lazy(() =>
  import('./pages/VocabularyPracticePage').then((module) => ({ default: module.VocabularyPracticePage }))
)

function PageLoadingFallback({ label = '正在打开学习空间...' }: { label?: string }) {
  return (
    <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center text-sm text-muted-foreground">
      {label}
    </div>
  )
}

function App() {
  const { showToast } = useToast()
  const [activeTab, setActiveTab] = useState<AppTab>('chat')
  const [learningCenterView, setLearningCenterView] = useState<'home' | 'daily-learning' | 'vocabulary-practice'>('home')
  const [practiceMode, setPracticeMode] = useState<VocabularyPracticeMode>('review')
  const [practiceNodeId, setPracticeNodeId] = useState<string | null>(null)
  const [practiceSourceLabel, setPracticeSourceLabel] = useState<string | null>(null)
  const [pronunciationWorkspace, setPronunciationWorkspace] = useState<PronunciationWorkspace>('phonetic')
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

  const openVocabularyPractice = (mode: VocabularyPracticeMode, nodeId?: string | null, sourceLabel?: string | null) => {
    setPracticeMode(mode)
    setPracticeNodeId(nodeId ?? null)
    setPracticeSourceLabel(sourceLabel ?? null)
    setLearningCenterView('vocabulary-practice')
  }

  const openPronunciationWorkspace = (workspace: PronunciationWorkspace) => {
    setPronunciationWorkspace(workspace)
    handleTabChange('pronunciation')
  }

  if (isRestoringLearner) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-sm text-muted-foreground">
        正在恢复学习空间...
      </div>
    )
  }

  if (!currentLearner) {
    return (
      <Suspense fallback={<PageLoadingFallback />}>
        <LoginPage onLogin={setCurrentLearner} />
      </Suspense>
    )
  }

  if (activeTab === 'dashboard' && learningCenterView === 'vocabulary-practice') {
    return (
      <Suspense fallback={<PageLoadingFallback label="正在打开词汇练习..." />}>
        <VocabularyPracticePage
          learner={currentLearner}
          initialMode={practiceMode}
          curriculumNodeId={practiceNodeId}
          sourceLabel={practiceSourceLabel}
          onExit={() => setLearningCenterView(practiceNodeId ? 'daily-learning' : 'home')}
        />
      </Suspense>
    )
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
        <Suspense fallback={<PageLoadingFallback />}>
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
              onOpenPronunciationWorkspace={openPronunciationWorkspace}
            />
          ) : activeTab === 'pronunciation' ? (
            <PronunciationPage
              key={pronunciationWorkspace}
              learner={currentLearner}
              initialWorkspace={pronunciationWorkspace}
            />
          ) : activeTab === 'grammar' ? (
            <GrammarPage learner={currentLearner} onBack={() => handleTabChange('explore')} />
          ) : activeTab === 'memory' ? (
            <MemoryCenterPage learner={currentLearner} />
          ) : (
            learningCenterView === 'daily-learning' ? (
              <KnowledgeBasePage
                learner={currentLearner}
                onBack={() => setLearningCenterView('home')}
                onStartVocabularyPractice={openVocabularyPractice}
              />
            ) : (
              <DashboardPage
                learner={currentLearner}
                onOpenDailyLearning={() => setLearningCenterView('daily-learning')}
                onStartVocabularyPractice={(mode) => openVocabularyPractice(mode)}
              />
            )
          )
          }
        </Suspense>
      </main>
    </div>
  )
}

export default App
