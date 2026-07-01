import { useEffect, useState } from 'react'
import { BarChart3, CheckCircle2, Clock3, RotateCcw } from 'lucide-react'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import {
  EXERCISE_ATTEMPTS_UPDATED_EVENT,
  fetchExerciseSummaryForTarget,
  getExerciseSummaryForTarget,
  type ExerciseAttemptSummary as ExerciseAttemptSummaryData,
} from '@/services/exerciseRepository'
import type { ExerciseTarget } from '@/types/exercises'

interface ExerciseAttemptSummaryProps {
  target: ExerciseTarget
  className?: string
  learnerId?: string
}

export function ExerciseAttemptSummary({ target, className = '', learnerId }: ExerciseAttemptSummaryProps) {
  const scopeKey = `${learnerId ?? 'local'}:${target.type}:${target.id}`
  return (
    <ExerciseAttemptSummaryContent
      key={scopeKey}
      target={target}
      className={className}
      learnerId={learnerId}
    />
  )
}

function ExerciseAttemptSummaryContent({ target, className = '', learnerId }: ExerciseAttemptSummaryProps) {
  const [summary, setSummary] = useState<ExerciseAttemptSummaryData>(() => getExerciseSummaryForTarget(target))

  useEffect(() => {
    let isMounted = true
    const refreshSummary = () => {
      if (learnerId) {
        void fetchExerciseSummaryForTarget(learnerId, target).then((nextSummary) => {
          if (isMounted) setSummary(nextSummary)
        })
        return
      }
      setSummary(getExerciseSummaryForTarget(target))
    }
    refreshSummary()
    window.addEventListener(EXERCISE_ATTEMPTS_UPDATED_EVENT, refreshSummary)
    window.addEventListener('storage', refreshSummary)
    return () => {
      isMounted = false
      window.removeEventListener(EXERCISE_ATTEMPTS_UPDATED_EVENT, refreshSummary)
      window.removeEventListener('storage', refreshSummary)
    }
  }, [target, learnerId])

  return (
    <SurfaceCard className={className}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="size-5 text-primary" />
            <h2 className="text-lg font-black text-slate-950">练习结果</h2>
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            这份记录来自：<span className="font-black text-slate-700">{target.label}</span>
          </p>
        </div>
        <SummaryStatus summary={summary} />
      </div>

      {summary.total > 0 ? (
        <>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <Metric label="已练次数" value={`${summary.total} 次`} />
            <Metric label="正确率" value={`${summary.accuracy}%`} tone={summary.learningStatus === 'mastered' ? 'success' : 'warning'} />
            <Metric label="最近一次" value={resultLabel(summary.lastResult)} tone={summary.lastResult === 'incorrect' ? 'warning' : 'success'} />
          </div>
          <div className={adviceClassName(summary.learningStatus)}>
            <p className="flex items-center gap-2 text-sm font-black">
              {summary.learningStatus === 'mastered' ? <CheckCircle2 className="size-4" /> : <RotateCcw className="size-4" />}
              下一步建议
            </p>
            <p className="mt-1 text-sm leading-6">
              {learningAdvice(summary.learningStatus)}
            </p>
          </div>
          {summary.lastAttemptAt ? (
            <p className="mt-3 flex items-center gap-1 text-xs font-semibold text-slate-400">
              <Clock3 className="size-3.5" />
              最近练习：{formatAttemptTime(summary.lastAttemptAt)}
            </p>
          ) : null}
        </>
      ) : (
        <div className="mt-5 rounded-lg border border-dashed border-slate-200 bg-slate-50 p-4">
          <p className="text-sm font-black text-slate-800">还没有练习记录</p>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            {learningAdvice(summary.learningStatus)} 完成后这里会显示累计次数、正确率和下一步建议，让练习结果成为可见的学习证据。
          </p>
        </div>
      )}
    </SurfaceCard>
  )
}

function SummaryStatus({ summary }: { summary: ExerciseAttemptSummaryData }) {
  if (summary.learningStatus === 'not_started') {
    return <span className="rounded-md bg-slate-100 px-2.5 py-1 text-xs font-black text-slate-500">待练习</span>
  }
  if (summary.learningStatus === 'mastered') {
    return <span className="rounded-md bg-emerald-100 px-2.5 py-1 text-xs font-black text-emerald-800">已掌握</span>
  }
  if (summary.learningStatus === 'needs_review') {
    return <span className="rounded-md bg-amber-100 px-2.5 py-1 text-xs font-black text-amber-800">需复习</span>
  }
  return <span className="rounded-md bg-orange-100 px-2.5 py-1 text-xs font-black text-orange-800">不稳定</span>
}

function Metric({
  label,
  value,
  tone = 'default',
}: {
  label: string
  value: string
  tone?: 'default' | 'success' | 'warning'
}) {
  const toneClass = tone === 'success'
    ? 'bg-emerald-50 text-emerald-800'
    : tone === 'warning'
      ? 'bg-amber-50 text-amber-800'
      : 'bg-slate-50 text-slate-800'
  return (
    <div className={`rounded-lg px-3 py-2 ${toneClass}`}>
      <p className="text-xs font-bold opacity-75">{label}</p>
      <p className="mt-1 text-lg font-black">{value}</p>
    </div>
  )
}

function adviceClassName(status: ExerciseAttemptSummaryData['learningStatus']) {
  if (status === 'mastered') {
    return 'mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-emerald-900'
  }
  if (status === 'not_started') {
    return 'mt-4 rounded-lg border border-primary/20 bg-primary/5 p-4 text-primary'
  }
  return 'mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-900'
}

function resultLabel(result: ExerciseAttemptSummaryData['lastResult']) {
  if (result === 'correct') return '正确'
  if (result === 'incorrect') return '错误'
  return '暂无'
}

function learningAdvice(status: ExerciseAttemptSummaryData['learningStatus']) {
  if (status === 'not_started') return '建议完成验收练习。'
  if (status === 'mastered') return '可以继续下一个知识点。'
  if (status === 'needs_review') return '建议重新阅读讲解并再做一次。'
  return '建议加入今日复习。'
}

function formatAttemptTime(value: string) {
  const time = new Date(value)
  if (Number.isNaN(time.getTime())) return '时间未知'
  return time.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
