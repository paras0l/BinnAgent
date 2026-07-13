import { Component, lazy, Suspense, useCallback, useEffect, useRef, useState, type ErrorInfo, type ReactNode } from 'react'
import { Header } from './components/layout/Header'
import { GroupLearningSettingsDialog } from './components/learning/GroupLearningSettingsDialog'
import { LearningSettingsDialog } from './components/learning/LearningSettingsDialog'
import { PetSpiritSettingsDialog } from './components/learning/PetSpiritSettingsDialog'
import { Button } from './components/ui/Button'
import { StatusBanner } from './components/ui/StatusBanner'
import { useToast } from './hooks/useToast'
import { useLearningPreferences } from './hooks/useLearningPreferences'
import type { VocabularyPracticeMode } from './pages/VocabularyPracticePage'
import type { ExpressionLabSourceSeed } from './pages/ExpressionLabPage'
import type { ExpressionInputType } from './services/expressionLabApi'
import type { AppTab, Learner, LearnerProfile, PronunciationWorkspace } from './types'

type LearningCenterView = 'home' | 'daily-learning' | 'reading' | 'vocabulary' | 'vocabulary-practice' | 'profile' | 'group-signals'

type ExpressionLabReturnTo = 'explore' | 'dashboard' | 'group-signals'

interface ExpressionLabLaunch {
  sessionId: string | null
  sourceSignal?: ExpressionLabSourceSeed | null
  initialInputType?: ExpressionInputType
  initialText?: string
  returnTo: ExpressionLabReturnTo
}

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

const ExpressionLabPage = lazy(() =>
  import('./pages/ExpressionLabPage').then((module) => ({ default: module.ExpressionLabPage }))
)

const GrammarPage = lazy(() =>
  import('./pages/GrammarPage').then((module) => ({ default: module.GrammarPage }))
)

const KnowledgeBasePage = lazy(() =>
  import('./pages/KnowledgeBasePage').then((module) => ({ default: module.KnowledgeBasePage }))
)

const ReadingWorkshopPage = lazy(() =>
  import('./pages/ReadingWorkshopPage').then((module) => ({ default: module.ReadingWorkshopPage }))
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
    <div className="binn-min-viewport-height flex items-center justify-center text-sm text-muted-foreground">
      {label}
    </div>
  )
}

interface RouteErrorBoundaryProps {
  children: ReactNode
  fallback: (reset: () => void) => ReactNode
  resetKey: string
}

interface RouteErrorBoundaryState {
  hasError: boolean
}

class RouteErrorBoundary extends Component<RouteErrorBoundaryProps, RouteErrorBoundaryState> {
  state: RouteErrorBoundaryState = { hasError: false }

  static getDerivedStateFromError(): RouteErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Route render error:', error, errorInfo)
  }

  componentDidUpdate(previousProps: RouteErrorBoundaryProps) {
    if (previousProps.resetKey !== this.props.resetKey && this.state.hasError) {
      this.setState({ hasError: false })
    }
  }

  reset = () => this.setState({ hasError: false })

  render() {
    if (this.state.hasError) return this.props.fallback(this.reset)
    return this.props.children
  }
}

function App() {
  const { beginPetActivity, completePetActivity, introduceFeature, petPreferences, resetIntroductions, showToast, signalMemoryChange, updatePetPreferences } = useToast()
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
  const chatActivityRef = useRef<string | null>(null)
  const [isLearningSettingsOpen, setIsLearningSettingsOpen] = useState(false)
  const [isGroupLearningSettingsOpen, setIsGroupLearningSettingsOpen] = useState(false)
  const [isPetSpiritSettingsOpen, setIsPetSpiritSettingsOpen] = useState(false)
  const [learnerProfile, setLearnerProfile] = useState<LearnerProfile | null>(null)
  const [learnerProfileReadiness, setLearnerProfileReadiness] = useState<LearnerProfileReadiness | null>(null)
  const [currentLearner, setCurrentLearner] = useState<Learner | null>(() => readCachedLearner())
  const [expressionLabLaunch, setExpressionLabLaunch] = useState<ExpressionLabLaunch | null>(() => readExpressionLabLocation())
  const [isRestoringLearner, setIsRestoringLearner] = useState(() =>
    Boolean(readLocalStorageItem('binnLearnerId'))
  )
  const { preferences, resetPreferences, updatePreferences } = useLearningPreferences(currentLearner?.id)

  useEffect(() => {
    if (!currentLearner?.id) return
    if (expressionLabLaunch) {
      introduceFeature('expression-lab', '表达实验室', '把一句想说的话放进来，我会陪你拆解、改写，再沉淀成可复用的表达。')
      return
    }
    const introductions: Partial<Record<AppTab, [string, string, string]>> = {
      chat: ['ai-chat', 'AI 对话', '这里可以自由提问、练习英语，我们也可以接着上次的学习线索继续往前走。'],
      explore: ['explore', '探索', '这里集合了发音、语法和表达等专项工具，选一个现在最想提升的能力吧。'],
      dashboard: ['learning-center', '学习中心', '这里能看到学习进度、今日任务和复习入口，适合每天从这里开始。'],
      pronunciation: ['pronunciation', '发音训练', '在这里可以查音标、跟读并获得发音反馈。'],
      grammar: ['grammar', '语法学习', '选择一个语法点，我会提供讲解、例句和练习路径。'],
    }
    const introduction = introductions[activeTab]
    if (introduction) introduceFeature(...introduction)
  }, [activeTab, currentLearner?.id, expressionLabLaunch, introduceFeature])

  useEffect(() => {
    if (isChatGenerating && !chatActivityRef.current) {
      chatActivityRef.current = beginPetActivity('我陪你整理思路和学习记录，稍等一下，我们一起看结果。', '正在一起想')
      return
    }
    if (!isChatGenerating && chatActivityRef.current) {
      completePetActivity(chatActivityRef.current, '整理好了，我们一起看看。', 'info')
      chatActivityRef.current = null
    }
  }, [beginPetActivity, completePetActivity, isChatGenerating])

  useEffect(() => {
    const handlePopState = () => setExpressionLabLaunch(readExpressionLabLocation())
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  useEffect(() => {
    const learnerId = readLocalStorageItem('binnLearnerId')
    if (!learnerId) return

    fetch(`/api/learners/${learnerId}`)
      .then((response) => {
        if (!response.ok) throw new Error('Learner not found')
        return response.json() as Promise<Learner>
      })
      .then((learner) => {
        writeLocalStorageItem('binnLearner', JSON.stringify(learner))
        setCurrentLearner(learner)
      })
      .catch(() => {
        removeLocalStorageItem('binnLearnerId')
        removeLocalStorageItem('binnLearner')
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
    const previousProfile = learnerProfile
    const previousReadiness = learnerProfileReadiness
    const nextProfile: LearnerProfile = {
      learner_id: currentLearner.id,
      learning_track: learnerProfile?.learning_track ?? 'school',
      target_exam: learnerProfile?.target_exam ?? null,
      target_score: learnerProfile?.target_score ?? null,
      exam_date: learnerProfile?.exam_date ?? null,
      current_level: learnerProfile?.current_level ?? null,
      daily_time_budget_minutes: learnerProfile?.daily_time_budget_minutes ?? null,
      interest_topics: learnerProfile?.interest_topics ?? [],
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
      signalMemoryChange('我把新的学习目标记住了，之后我们会一起按这个方向调整。')
    } catch {
      setLearnerProfile(previousProfile)
      setLearnerProfileReadiness(previousReadiness)
      showToast('学习画像这次还没保存好，我们一起再试一次。', { variant: 'warning' })
    }
  }

  const handleLogout = () => {
    if (isChatGenerating) {
      showToast('回答生成中，请先等待完成或点击取消。', { variant: 'warning' })
      return
    }
    removeLocalStorageItem('binnLearnerId')
    removeLocalStorageItem('binnLearner')
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
    if (expressionLabLaunch) {
      setExpressionLabLaunch(null)
      replaceLearnerPath(tab === 'chat' ? '/' : `/${tab}`)
    }
    setActiveTab(tab)
  }

  const handleOpenExpressionLab = useCallback((launch: Omit<ExpressionLabLaunch, 'sessionId'> & { sessionId?: string | null }) => {
    const next: ExpressionLabLaunch = { ...launch, sessionId: launch.sessionId ?? null }
    setExpressionLabLaunch(next)
    window.history.pushState({ expressionLabReturnTo: next.returnTo }, '', expressionLabPath(next.sessionId))
  }, [])

  const handleExpressionLabSessionChange = useCallback((sessionId: string | null) => {
    setExpressionLabLaunch((current) => current ? { ...current, sessionId } : current)
    const current = readExpressionLabLocation()
    window.history.replaceState(
      { expressionLabReturnTo: current?.returnTo ?? 'explore' },
      '',
      expressionLabPath(sessionId),
    )
  }, [])

  const handleCloseExpressionLab = useCallback(() => {
    const returnTo = expressionLabLaunch?.returnTo ?? 'explore'
    setExpressionLabLaunch(null)
    if (returnTo === 'group-signals') {
      setLearningCenterView('group-signals')
      setActiveTab('dashboard')
      replaceLearnerPath('/dashboard')
    } else if (returnTo === 'dashboard') {
      setLearningCenterView('home')
      setActiveTab('dashboard')
      replaceLearnerPath('/dashboard')
    } else {
      setActiveTab('explore')
      replaceLearnerPath('/explore')
    }
  }, [expressionLabLaunch?.returnTo])

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

  if (!currentLearner.email) {
    return (
      <Suspense fallback={<PageLoadingFallback label="正在打开邮箱绑定页..." />}>
        <LoginPage learnerToBind={currentLearner} onLogin={setCurrentLearner} />
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
        onOpenPetSpiritSettings={() => setIsPetSpiritSettingsOpen(true)}
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
      <PetSpiritSettingsDialog
        open={isPetSpiritSettingsOpen}
        preferences={petPreferences}
        onClose={() => setIsPetSpiritSettingsOpen(false)}
        onResetIntroductions={resetIntroductions}
        onUpdate={updatePetPreferences}
      />
      <main className="binn-app-main">
        {expressionLabLaunch ? null : profileSetupBanner}
        <RouteErrorBoundary
          resetKey={`${currentLearner.id}:${activeTab}:${learningCenterView}:${expressionLabLaunch?.sessionId ?? 'no-expression-lab'}`}
          fallback={(reset) => (
            <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6 lg:px-8">
              <StatusBanner
                tone="warning"
                title="这个页面暂时没有打开"
                action={
                  <Button
                    variant="secondary"
                    className="px-3 py-2 text-xs"
                    onClick={() => {
                      reset()
                      setActiveTab('chat')
                      setLearningCenterView('home')
                    }}
                  >
                    返回 AI 对话
                  </Button>
                }
              >
                可以先回到 AI 对话继续学习，或者切换回来重试学习中心。
              </StatusBanner>
            </div>
          )}
        >
          <Suspense fallback={<PageLoadingFallback />}>
          {expressionLabLaunch ? (
            <ExpressionLabPage
              key={`${expressionLabLaunch.sessionId ?? 'new'}:${expressionLabLaunch.sourceSignal?.id ?? 'manual'}`}
              learner={currentLearner}
              learnerProfile={learnerProfile}
              initialSessionId={expressionLabLaunch.sessionId}
              sourceSignal={expressionLabLaunch.sourceSignal}
              initialInputType={expressionLabLaunch.initialInputType}
              initialText={expressionLabLaunch.initialText}
              onBack={handleCloseExpressionLab}
              onSessionChange={handleExpressionLabSessionChange}
            />
          ) : activeTab === 'chat' ? (
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
            ) : learningCenterView === 'reading' ? (
              <ReadingWorkshopPage
                learner={currentLearner}
                learnerProfile={learnerProfile}
                readingTrackMode
                onBack={() => setLearningCenterView('home')}
              />
            ) : (
              <DashboardPage
                key={learningCenterView === 'vocabulary' || learningCenterView === 'profile' || learningCenterView === 'group-signals' ? learningCenterView : 'home'}
                learner={currentLearner}
                learnerProfile={learnerProfile}
                initialVocabularyListOpen={learningCenterView === 'vocabulary'}
                initialWorkspace={
                  learningCenterView === 'vocabulary' || learningCenterView === 'profile' || learningCenterView === 'group-signals'
                    ? learningCenterView
                    : 'home'
                }
                onOpenAiConversation={() => handleTabChange('chat')}
                onOpenDailyLearning={() => setLearningCenterView('daily-learning')}
                onOpenReadingTrack={() => setLearningCenterView('reading')}
                onOpenGroupLearningSettings={() => setIsGroupLearningSettingsOpen(true)}
                onOpenExpressionLab={(options) => handleOpenExpressionLab({ ...options, returnTo: options.sourceSignal ? 'group-signals' : 'dashboard' })}
                onProfileUpdate={(patch) => void updateLearnerProfile(patch)}
                onStartVocabularyPractice={(mode) => openVocabularyPractice(mode ?? preferences.defaultPracticeMode)}
              />
            )
          )
          }
          </Suspense>
        </RouteErrorBoundary>
      </main>
    </div>
  )
}

function readCachedLearner() {
  const cached = readLocalStorageItem('binnLearner')
  if (!cached) return null
  try {
    return JSON.parse(cached) as Learner
  } catch {
    return null
  }
}

function readLocalStorageItem(key: string) {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeLocalStorageItem(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Some mobile/private browsers can deny storage; keep the in-memory session usable.
  }
}

function removeLocalStorageItem(key: string) {
  try {
    localStorage.removeItem(key)
  } catch {
    // Ignore storage cleanup failures.
  }
}

function readExpressionLabLocation(): ExpressionLabLaunch | null {
  if (typeof window === 'undefined') return null
  const match = window.location.pathname.match(/^\/expression-lab\/(new|[^/]+)$/)
  if (!match) return null
  const returnTo = window.history.state?.expressionLabReturnTo
  return {
    sessionId: match[1] === 'new' ? null : decodeURIComponent(match[1]),
    returnTo: returnTo === 'dashboard' || returnTo === 'group-signals' ? returnTo : 'explore',
  }
}

function expressionLabPath(sessionId: string | null) {
  return `/expression-lab/${sessionId ? encodeURIComponent(sessionId) : 'new'}`
}

function replaceLearnerPath(path: string) {
  if (typeof window === 'undefined') return
  window.history.replaceState({}, '', path)
}

export default App
