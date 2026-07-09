import { lazy, Suspense, useEffect, useState } from 'react'
import { Header } from './components/layout/Header'
import { GroupLearningSettingsDialog } from './components/learning/GroupLearningSettingsDialog'
import { LearningSettingsDialog } from './components/learning/LearningSettingsDialog'
import { Button } from './components/ui/Button'
import { StatusBanner } from './components/ui/StatusBanner'
import { useToast } from './hooks/useToast'
import { useLearningPreferences } from './hooks/useLearningPreferences'
import type { VocabularyPracticeMode } from './pages/VocabularyPracticePage'
import type { AppTab, Learner, LearnerProfile, PronunciationWorkspace } from './types'

type LearningCenterView = 'home' | 'daily-learning' | 'vocabulary' | 'vocabulary-practice' | 'profile'

interface LearnerProfileReadiness {
  learner_id: string
  target_exam?: string | null
  current_level?: string | null
  has_learning_goal: boolean
  has_current_level: boolean
  is_complete: boolean
}

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
  const [learningCenterView, setLearningCenterView] = useState<LearningCenterView>('home')
  const [practiceMode, setPracticeMode] = useState<VocabularyPracticeMode>('review')
  const [practiceNodeId, setPracticeNodeId] = useState<string | null>(null)
  const [practiceSourceLabel, setPracticeSourceLabel] = useState<string | null>(null)
  const [pronunciationWorkspace, setPronunciationWorkspace] = useState<PronunciationWorkspace>('phonetic')
  const [chatDraft, setChatDraft] = useState('')
  const [chatSkillFocus, setChatSkillFocus] = useState<string | null>(null)
  const [pendingChatPrompt, setPendingChatPrompt] = useState<{
    id: number
    prompt: string
    skillFocus: string | null
  } | null>(null)
  const [isChatGenerating, setIsChatGenerating] = useState(false)
  const [isLearningSettingsOpen, setIsLearningSettingsOpen] = useState(false)
  const [isGroupLearningSettingsOpen, setIsGroupLearningSettingsOpen] = useState(false)
  const [learnerProfile, setLearnerProfile] = useState<LearnerProfile | null>(null)
  const [learnerProfileReadiness, setLearnerProfileReadiness] = useState<LearnerProfileReadiness | null>(null)
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
  const { preferences, resetPreferences, updatePreferences } = useLearningPreferences(currentLearner?.id)

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

  useEffect(() => {
    if (!currentLearner?.id) {
      return
    }
    let isMounted = true
    fetch(`/api/learners/${currentLearner.id}/profile`)
      .then((response) => {
        if (!response.ok) throw new Error('Learner profile unavailable')
        return response.json() as Promise<LearnerProfile>
      })
      .then((profile) => {
        if (isMounted) {
          setLearnerProfile(profile)
        }
      })
      .catch(() => {
        if (isMounted) {
          setLearnerProfile(null)
        }
      })
    return () => {
      isMounted = false
    }
  }, [currentLearner?.id])

  useEffect(() => {
    if (!currentLearner?.id) {
      return
    }
    let isMounted = true
    fetch(`/api/learners/${currentLearner.id}/profile-readiness`)
      .then((response) => {
        if (!response.ok) throw new Error('Learner profile readiness unavailable')
        return response.json() as Promise<LearnerProfileReadiness>
      })
      .then((readiness) => {
        if (isMounted) setLearnerProfileReadiness(readiness)
      })
      .catch(() => {
        if (isMounted) setLearnerProfileReadiness(null)
      })
    return () => {
      isMounted = false
    }
  }, [currentLearner?.id])

  const updateLearnerProfile = async (patch: Partial<LearnerProfile>) => {
    if (!currentLearner) return
    const nextProfile: LearnerProfile = {
      learner_id: currentLearner.id,
      target_exam: learnerProfile?.target_exam ?? null,
      target_score: learnerProfile?.target_score ?? null,
      exam_date: learnerProfile?.exam_date ?? null,
      current_level: learnerProfile?.current_level ?? null,
      daily_time_budget_minutes: learnerProfile?.daily_time_budget_minutes ?? null,
      ...patch,
    }
    setLearnerProfile(nextProfile)
    setLearnerProfileReadiness({
      learner_id: currentLearner.id,
      target_exam: nextProfile.target_exam,
      current_level: nextProfile.current_level,
      has_learning_goal: Boolean(nextProfile.target_exam),
      has_current_level: Boolean(nextProfile.current_level),
      is_complete: Boolean(nextProfile.target_exam && nextProfile.current_level),
    })
    try {
      const response = await fetch(`/api/learners/${currentLearner.id}/profile`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(nextProfile),
      })
      if (!response.ok) throw new Error('Failed to save learner profile')
      setLearnerProfile(await response.json() as LearnerProfile)
    } catch {
      showToast('学习画像暂时无法保存，请稍后重试。', { variant: 'warning' })
    }
  }

  const handleLogout = () => {
    if (isChatGenerating) {
      showToast('回答生成中，请先等待完成或点击取消。', { variant: 'warning' })
      return
    }
    localStorage.removeItem('binnLearnerId')
    localStorage.removeItem('binnLearner')
    setCurrentLearner(null)
    setLearnerProfile(null)
    setLearnerProfileReadiness(null)
    setActiveTab('chat')
    setChatDraft('')
    setChatSkillFocus(null)
  }

  const handleDraftPrompt = (
    prompt: string,
    skillFocus?: string | null,
    options: { autoSend?: boolean } = {},
  ) => {
    if (isChatGenerating) {
      showToast('回答生成中，请先等待完成或点击取消。', { variant: 'warning' })
      return
    }
    const nextSkillFocus = skillFocus ?? null
    setChatSkillFocus(nextSkillFocus)
    if (options.autoSend) {
      setChatDraft('')
      setPendingChatPrompt({
        id: Date.now(),
        prompt,
        skillFocus: nextSkillFocus,
      })
    } else {
      setChatDraft(prompt)
      setPendingChatPrompt(null)
    }
  }

  const handleTabChange = (tab: AppTab) => {
    if (isChatGenerating && tab !== 'chat') {
      showToast('回答生成中，请先等待完成或点击取消。', { variant: 'warning' })
      return
    }
    if (tab === 'dashboard') setLearningCenterView('home')
    setActiveTab(tab)
  }

  const handleOpenLearnerProfile = () => {
    if (isChatGenerating) {
      showToast('回答生成中，请先等待完成或点击取消。', { variant: 'warning' })
      return
    }
    setLearningCenterView('profile')
    setActiveTab('dashboard')
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

  const openVocabularyManager = () => {
    setLearningCenterView('vocabulary')
    setActiveTab('dashboard')
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

  const isProfileMissingGoalAndLevel =
    learnerProfileReadiness?.learner_id === currentLearner.id &&
    !learnerProfileReadiness.has_learning_goal &&
    !learnerProfileReadiness.has_current_level
  const profileSetupBanner = isProfileMissingGoalAndLevel ? (
    <div className="mx-auto max-w-7xl px-4 pt-4 sm:px-6 lg:px-8">
      <StatusBanner
        tone="warning"
        title="完善学习目标和当前水平"
        action={
          <Button variant="secondary" className="px-3 py-2 text-xs" onClick={handleOpenLearnerProfile}>
            去设置
          </Button>
        }
      >
        设置后，BinnAgent 会按你的目标和水平调整讲解难度、例句和练习推荐。
      </StatusBanner>
    </div>
  ) : null

  if (activeTab === 'dashboard' && learningCenterView === 'vocabulary-practice') {
    return (
      <div className="min-h-screen bg-background">
        {profileSetupBanner}
        <Suspense fallback={<PageLoadingFallback label="正在打开词汇练习..." />}>
          <VocabularyPracticePage
            learner={currentLearner}
            initialMode={practiceMode}
            curriculumNodeId={practiceNodeId}
            preferences={preferences}
            sourceLabel={practiceSourceLabel}
            onExit={() => setLearningCenterView(practiceNodeId ? 'daily-learning' : 'home')}
          />
        </Suspense>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      <Header
        activeTab={activeTab}
        isLocked={isChatGenerating}
        learner={currentLearner}
        onLogout={handleLogout}
        onOpenGroupLearningSettings={() => setIsGroupLearningSettingsOpen(true)}
        onOpenLearningSettings={() => setIsLearningSettingsOpen(true)}
        onTabChange={handleTabChange}
      />
      <GroupLearningSettingsDialog
        learner={currentLearner}
        open={isGroupLearningSettingsOpen}
        onClose={() => setIsGroupLearningSettingsOpen(false)}
      />
      <LearningSettingsDialog
        open={isLearningSettingsOpen}
        preferences={preferences}
        onClose={() => setIsLearningSettingsOpen(false)}
        onReset={resetPreferences}
        onUpdate={updatePreferences}
      />
      <main className="pt-16">
        {profileSetupBanner}
        <Suspense fallback={<PageLoadingFallback />}>
          {activeTab === 'chat' ? (
            <ChatPage
              learner={currentLearner}
              draft={chatDraft}
              onDraftChange={setChatDraft}
              pendingPrompt={pendingChatPrompt}
              onPendingPromptConsumed={() => setPendingChatPrompt(null)}
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
              learnerProfile={learnerProfile}
              isLocked={isChatGenerating}
              onLockedAction={() => {
                showToast('回答生成中，请先等待完成或点击取消。', { variant: 'warning' })
              }}
              onTabChange={handleTabChange}
              onDraftPrompt={handleDraftPrompt}
              onOpenVocabularyManager={openVocabularyManager}
              onOpenPronunciationWorkspace={openPronunciationWorkspace}
            />
          ) : activeTab === 'pronunciation' ? (
            <PronunciationPage
              key={pronunciationWorkspace}
              learner={currentLearner}
              initialWorkspace={pronunciationWorkspace}
            />
          ) : activeTab === 'grammar' ? (
            <GrammarPage
              learner={currentLearner}
              learnerProfile={learnerProfile}
              onBack={() => handleTabChange('explore')}
            />
          ) : (
            learningCenterView === 'daily-learning' ? (
              <KnowledgeBasePage
                learner={currentLearner}
                onBack={() => setLearningCenterView('home')}
                onStartVocabularyPractice={openVocabularyPractice}
                onOpenPronunciationWorkspace={openPronunciationWorkspace}
              />
            ) : (
              <DashboardPage
                key={learningCenterView === 'vocabulary' || learningCenterView === 'profile' ? learningCenterView : 'home'}
                learner={currentLearner}
                learnerProfile={learnerProfile}
                initialVocabularyListOpen={learningCenterView === 'vocabulary'}
                initialWorkspace={
                  learningCenterView === 'vocabulary' || learningCenterView === 'profile'
                    ? learningCenterView
                    : 'home'
                }
                onOpenDailyLearning={() => setLearningCenterView('daily-learning')}
                onOpenGroupLearningSettings={() => setIsGroupLearningSettingsOpen(true)}
                onProfileUpdate={(patch) => void updateLearnerProfile(patch)}
                onStartVocabularyPractice={(mode) => openVocabularyPractice(mode ?? preferences.defaultPracticeMode)}
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
