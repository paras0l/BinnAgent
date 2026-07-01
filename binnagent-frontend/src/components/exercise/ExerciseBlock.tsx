import { useCallback, useEffect, useMemo, useState } from 'react'
import { BookOpenCheck } from 'lucide-react'
import { EmptyState } from '@/components/ui/EmptyState'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import { ExerciseRenderer, type ExerciseRendererProgress } from '@/components/exercise/ExerciseRenderer'
import {
  CORE_VOCABULARY_EXERCISE_TARGET,
  EXERCISES_UPDATED_EVENT,
  EXERCISE_ATTEMPTS_UPDATED_EVENT,
  fetchExerciseSummaryForTarget,
  fetchExercisesForTarget,
  getExerciseSummaryForTarget,
  getExercisesForTarget,
  type ExerciseAttemptSummary,
} from '@/services/exerciseRepository'
import type { ExerciseTarget } from '@/types/exercises'

interface ExerciseBlockProps {
  target: ExerciseTarget
  limit?: number
  className?: string
  learnerId?: string
}

const EMPTY_PROGRESS: ExerciseRendererProgress = {
  completedCount: 0,
  totalCount: 0,
  correctCount: 0,
}

export function ExerciseBlock({ target, limit = 3, className = '', learnerId }: ExerciseBlockProps) {
  const scopeKey = `${learnerId ?? 'local'}:${target.type}:${target.id}:${limit}`
  return (
    <ExerciseBlockContent
      key={scopeKey}
      target={target}
      limit={limit}
      className={className}
      learnerId={learnerId}
    />
  )
}

function ExerciseBlockContent({ target, limit = 3, className = '', learnerId }: ExerciseBlockProps) {
  const [exactExercises, setExactExercises] = useState(() => getExercisesForTarget(target, { limit }))
  const [rendererProgress, setRendererProgress] = useState<ExerciseRendererProgress>(EMPTY_PROGRESS)

  useEffect(() => {
    let isMounted = true
    const loadExercises = async () => {
      const nextExercises = learnerId
        ? await fetchExercisesForTarget(learnerId, target, { limit })
        : getExercisesForTarget(target, { limit })
      if (isMounted) setExactExercises(nextExercises)
    }
    void loadExercises()
    window.addEventListener(EXERCISES_UPDATED_EVENT, loadExercises)
    return () => {
      isMounted = false
      window.removeEventListener(EXERCISES_UPDATED_EVENT, loadExercises)
    }
  }, [learnerId, limit, target])

  const fallbackExercises = useMemo(() => {
    if (exactExercises.length > 0 || target.type !== 'vocabulary_item') return []
    return getExercisesForTarget(CORE_VOCABULARY_EXERCISE_TARGET, { limit })
  }, [exactExercises.length, limit, target.type])
  const exercises = exactExercises.length > 0 ? exactExercises : fallbackExercises
  const activeTarget = exactExercises.length > 0 || fallbackExercises.length === 0
    ? target
    : CORE_VOCABULARY_EXERCISE_TARGET
  const isFallback = exactExercises.length === 0 && fallbackExercises.length > 0
  const [attemptSummary, setAttemptSummary] = useState<ExerciseAttemptSummary>(() =>
    getExerciseSummaryForTarget(activeTarget)
  )

  useEffect(() => {
    let isMounted = true
    const refreshSummary = () => {
      if (learnerId) {
        void fetchExerciseSummaryForTarget(learnerId, activeTarget).then((summary) => {
          if (isMounted) setAttemptSummary(summary)
        })
        return
      }
      setAttemptSummary(getExerciseSummaryForTarget(activeTarget))
    }
    refreshSummary()
    window.addEventListener(EXERCISE_ATTEMPTS_UPDATED_EVENT, refreshSummary)
    window.addEventListener('storage', refreshSummary)
    return () => {
      isMounted = false
      window.removeEventListener(EXERCISE_ATTEMPTS_UPDATED_EVENT, refreshSummary)
      window.removeEventListener('storage', refreshSummary)
    }
  }, [activeTarget, learnerId])

  const handleProgressChange = useCallback((progress: ExerciseRendererProgress) => {
    setRendererProgress(progress)
  }, [])

  if (exercises.length === 0) {
    return (
      <SurfaceCard className={className}>
        <ExerciseHeader
          target={target}
          completedCount={0}
          totalCount={0}
          correctCount={0}
          summary={attemptSummary}
        />
        <div className="mt-5">
          <EmptyState
            icon={<BookOpenCheck className="size-5" />}
            title="这个知识点还没有配套练习"
            description={`当前没有匹配“${target.label}”的内置验收题。可以先完成讲解阅读和个人笔记；后续补题后，这里会直接变成知识点验收入口。`}
          />
        </div>
      </SurfaceCard>
    )
  }

  return (
    <SurfaceCard className={className}>
      <ExerciseHeader
        target={activeTarget}
        completedCount={rendererProgress.completedCount}
        totalCount={exercises.length}
        correctCount={rendererProgress.correctCount}
        summary={attemptSummary}
        fallbackLabel={isFallback ? target.label : undefined}
      />
      <ExerciseRenderer
        className="mt-5"
        exercises={exercises}
        learnerId={learnerId}
        onProgressChange={handleProgressChange}
      />
    </SurfaceCard>
  )
}

function ExerciseHeader({
  target,
  completedCount,
  totalCount,
  correctCount,
  summary,
  fallbackLabel,
}: {
  target: ExerciseTarget
  completedCount: number
  totalCount: number
  correctCount: number
  summary: ExerciseAttemptSummary
  fallbackLabel?: string
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <div className="flex items-center gap-2">
          <BookOpenCheck className="size-5 text-primary" />
          <h2 className="text-lg font-black text-slate-950">配套练习</h2>
        </div>
        <p className="mt-1 text-sm leading-6 text-slate-500">
          这组题在验收：<span className="font-black text-slate-700">{target.label}</span>
          {fallbackLabel ? `。当前词条“${fallbackLabel}”暂无专属题，先用通用词汇题验收基础用法。` : '。'}
        </p>
        <p className="mt-2 text-xs font-semibold text-slate-500">
          {summary.total > 0
            ? `累计练习 ${summary.total} 次 · 正确率 ${summary.accuracy}% · 最近一次：${resultLabel(summary.lastResult)}`
            : '累计练习 0 次 · 完成一题后会生成学习证据'}
        </p>
      </div>
      {totalCount > 0 ? (
        <div className="grid min-w-36 grid-cols-2 gap-2 text-center text-xs">
          <div className="rounded-lg bg-slate-50 px-3 py-2">
            <p className="font-black text-slate-950">{completedCount}/{totalCount}</p>
            <p className="mt-0.5 text-slate-500">已答</p>
          </div>
          <div className="rounded-lg bg-emerald-50 px-3 py-2">
            <p className="font-black text-emerald-700">{correctCount}</p>
            <p className="mt-0.5 text-emerald-700/80">正确</p>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function resultLabel(result: ExerciseAttemptSummary['lastResult']) {
  if (result === 'correct') return '正确'
  if (result === 'incorrect') return '错误'
  return '暂无'
}
