import { useCallback, useEffect, useState } from 'react'
import { BookOpen, Plus, RefreshCw } from 'lucide-react'
import { StatsCards } from '@/components/dashboard/StatsCards'
import { VocabReviewCard } from '@/components/dashboard/VocabReviewCard'
import { ErrorPatternList } from '@/components/dashboard/ErrorPatternList'
import { LearningGoalProgress } from '@/components/dashboard/LearningGoalProgress'
import type { DashboardSummary, Learner } from '@/types'

interface DashboardPageProps {
  learner: Learner
}

export function DashboardPage({ learner }: DashboardPageProps) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [currentVocabIndex, setCurrentVocabIndex] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [isReviewing, setIsReviewing] = useState(false)
  const [isAddingWord, setIsAddingWord] = useState(false)
  const [newWord, setNewWord] = useState('')
  const [newMeaning, setNewMeaning] = useState('')
  const [error, setError] = useState('')

  const loadDashboard = useCallback(async () => {
    setError('')
    setIsLoading(true)
    try {
      const response = await fetch(`/api/learners/${learner.id}/dashboard`)
      if (!response.ok) throw new Error('Failed to load dashboard')
      const data: DashboardSummary = await response.json()
      setSummary(data)
      setCurrentVocabIndex(0)
    } catch (err) {
      console.error('Dashboard error:', err)
      setError('学习中心暂时无法加载，请稍后重试。')
    } finally {
      setIsLoading(false)
    }
  }, [learner.id])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadDashboard(), 0)
    return () => window.clearTimeout(timer)
  }, [loadDashboard])

  const reviewItems = summary?.review_items ?? []
  const currentVocab = reviewItems[currentVocabIndex]

  const handleRate = async (rating: 1 | 2 | 3 | 4) => {
    if (!currentVocab) return
    setIsReviewing(true)
    try {
      const response = await fetch(`/api/learners/${learner.id}/vocabulary/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          word_id: currentVocab.id,
          correct: rating >= 3,
        }),
      })
      if (!response.ok) throw new Error('Review failed')
      await loadDashboard()
    } catch (err) {
      console.error('Vocabulary review error:', err)
      setError('词卡评分失败，请稍后重试。')
    } finally {
      setIsReviewing(false)
    }
  }

  const handleAddWord = async () => {
    const word = newWord.trim()
    const meaning = newMeaning.trim()
    if (!word) {
      setError('请输入要加入词汇本的单词。')
      return
    }

    setIsAddingWord(true)
    setError('')
    try {
      const response = await fetch(`/api/learners/${learner.id}/vocabulary/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          word,
          meanings: meaning ? [meaning] : null,
        }),
      })
      if (!response.ok) throw new Error('Add word failed')
      setNewWord('')
      setNewMeaning('')
      await loadDashboard()
    } catch (err) {
      console.error('Add vocabulary error:', err)
      setError('加入词汇本失败，请稍后重试。')
    } finally {
      setIsAddingWord(false)
    }
  }

  if (isLoading && !summary) {
    return (
      <div className="container mx-auto flex min-h-[calc(100vh-4rem)] items-center justify-center p-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <RefreshCw className="h-4 w-4 animate-spin" />
          正在加载学习记录...
        </div>
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="container mx-auto p-6">
        <div className="rounded-xl border bg-card p-8 text-center">
          <p className="text-sm text-error">{error || '学习中心暂时不可用。'}</p>
          <button
            onClick={() => void loadDashboard()}
            className="mt-4 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            重新加载
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto space-y-6 p-6">
      <StatsCards
        todayReviews={summary.stats.today_reviews}
        streakDays={summary.stats.streak_days}
        accuracy={summary.stats.accuracy}
        totalVocab={summary.stats.total_vocab}
      />

      {error && (
        <div className="rounded-lg border border-error/30 bg-error/5 px-4 py-3 text-sm text-error">
          {error}
        </div>
      )}

      <section className="rounded-xl border bg-card p-4">
        <div className="mb-3 flex items-center gap-2">
          <Plus className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-semibold text-foreground">加入词汇本</h2>
        </div>
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto]">
          <input
            value={newWord}
            onChange={(event) => setNewWord(event.target.value)}
            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
            placeholder="significant"
            maxLength={255}
          />
          <input
            value={newMeaning}
            onChange={(event) => setNewMeaning(event.target.value)}
            className="rounded-lg border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
            placeholder="可选释义，例如：重要的，显著的"
            maxLength={255}
          />
          <button
            onClick={() => void handleAddWord()}
            disabled={isAddingWord}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Plus className="h-4 w-4" />
            加入
          </button>
        </div>
      </section>

      {currentVocab ? (
        <div className={isReviewing ? 'pointer-events-none opacity-70' : ''}>
          <VocabReviewCard
            key={currentVocab.id}
            word={currentVocab.word}
            definition={currentVocab.definition}
            example={currentVocab.example}
            currentIndex={currentVocabIndex}
            totalCount={reviewItems.length}
            onRate={handleRate}
          />
        </div>
      ) : (
        <div className="flex flex-col items-center rounded-xl border bg-card p-8 text-center">
          <div className="mb-3 flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <BookOpen className="h-5 w-5" />
          </div>
          <h2 className="text-lg font-semibold text-foreground">暂无待复习词卡</h2>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">
            当你在对话或课程里沉淀新词后，系统会按复习计划把词卡放到这里。
          </p>
        </div>
      )}

      <ErrorPatternList patterns={summary.error_patterns} />

      <LearningGoalProgress
        dailyGoal={summary.today_goal}
        weeklyGoal={summary.weekly_goal}
      />
    </div>
  )
}
