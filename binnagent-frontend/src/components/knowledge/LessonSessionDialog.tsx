import { Check, LoaderCircle, RotateCcw, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { KnowledgeAttemptResult, KnowledgeLessonSession } from '@/types'

interface LessonSessionDialogProps {
  session: KnowledgeLessonSession | null
  onClose: () => void
  onAttempt: (knowledgePointId: string, correct: boolean) => Promise<KnowledgeAttemptResult>
  onComplete: () => Promise<void>
}

export function LessonSessionDialog({ session, onClose, onAttempt, onComplete }: LessonSessionDialogProps) {
  const [completedIds, setCompletedIds] = useState<Set<string>>(() => new Set())
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isCompleting, setIsCompleting] = useState(false)
  const completedCount = completedIds.size
  const allCompleted = useMemo(
    () => Boolean(session && completedCount === session.knowledge_points.length),
    [completedCount, session]
  )

  if (!session) return null

  const handleAttempt = async (knowledgePointId: string, correct: boolean) => {
    setPendingId(knowledgePointId)
    setError(null)
    try {
      await onAttempt(knowledgePointId, correct)
      setCompletedIds((current) => new Set(current).add(knowledgePointId))
    } catch (attemptError) {
      setError(attemptError instanceof Error ? attemptError.message : '学习记录保存失败。')
    } finally {
      setPendingId(null)
    }
  }

  const handleFinish = async () => {
    if (!allCompleted) {
      onClose()
      return
    }
    setIsCompleting(true)
    setError(null)
    try {
      await onComplete()
    } catch (completeError) {
      setError(completeError instanceof Error ? completeError.message : '课程完成状态保存失败。')
      setIsCompleting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/35 p-4" role="presentation">
      <section role="dialog" aria-modal="true" aria-labelledby="lesson-title" className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="lesson-title" className="text-xl font-extrabold text-slate-950">{session.title}</h2>
            <p className="mt-1 text-sm text-slate-500">逐个确认掌握情况，结果会写入学习记忆并安排复习。</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="关闭课程">
            <X className="size-5" />
          </button>
        </div>

        <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div className="h-full rounded-full bg-emerald-500 transition-[width]" style={{ width: `${session.knowledge_points.length ? completedCount / session.knowledge_points.length * 100 : 100}%` }} />
        </div>
        <p className="mt-2 text-right text-xs font-semibold text-slate-500">{completedCount} / {session.knowledge_points.length}</p>

        <div className="mt-4 max-h-[55vh] space-y-3 overflow-y-auto pr-1">
          {session.knowledge_points.map((point) => {
            const completed = completedIds.has(point.id)
            const pending = pendingId === point.id
            return (
              <article key={point.id} className={`rounded-xl border p-4 ${completed ? 'border-emerald-200 bg-emerald-50/50' : 'border-slate-200'}`}>
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h3 className="font-extrabold text-slate-900">{point.title}</h3>
                    <p className="mt-1 text-sm text-slate-500">{point.summary}</p>
                  </div>
                  {completed ? (
                    <span className="inline-flex shrink-0 items-center gap-1.5 text-sm font-bold text-emerald-700"><Check className="size-4" />已记录</span>
                  ) : (
                    <div className="flex shrink-0 gap-2">
                      <button type="button" disabled={pendingId !== null} onClick={() => void handleAttempt(point.id, false)} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-50">
                        {pending ? <LoaderCircle className="size-3.5 animate-spin" /> : <RotateCcw className="size-3.5" />}
                        还需复习
                      </button>
                      <button type="button" disabled={pendingId !== null} onClick={() => void handleAttempt(point.id, true)} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-extrabold text-white hover:bg-indigo-700 disabled:opacity-50">
                        <Check className="size-3.5" />
                        掌握了
                      </button>
                    </div>
                  )}
                </div>
              </article>
            )
          })}
        </div>
        {error ? <p className="mt-3 text-sm font-semibold text-red-600">{error}</p> : null}

        <div className="mt-5 flex justify-end">
          <button type="button" disabled={isCompleting || pendingId !== null} onClick={() => void handleFinish()} className={`inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-extrabold text-white disabled:cursor-not-allowed disabled:opacity-60 ${allCompleted ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-slate-700 hover:bg-slate-800'}`}>
            {isCompleting ? <LoaderCircle className="size-4 animate-spin" /> : null}
            {allCompleted ? '完成并进入下一单元' : '稍后继续'}
          </button>
        </div>
      </section>
    </div>
  )
}
