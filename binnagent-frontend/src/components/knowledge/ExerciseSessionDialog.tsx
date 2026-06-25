import { CheckCircle2, LoaderCircle, X, XCircle } from 'lucide-react'
import { useState } from 'react'
import type { ExerciseAnswerResult, ExerciseSession } from '@/types'

interface ExerciseSessionDialogProps {
  session: ExerciseSession | null
  onClose: () => void
  onSubmit: (questionId: string, answer: string) => Promise<ExerciseAnswerResult>
}

export function ExerciseSessionDialog({ session, onClose, onSubmit }: ExerciseSessionDialogProps) {
  const [questionIndex, setQuestionIndex] = useState(0)
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null)
  const [result, setResult] = useState<ExerciseAnswerResult | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!session) return null
  const question = session.questions[questionIndex]
  if (!question) return null
  const isLast = questionIndex === session.questions.length - 1

  const handleSubmit = async () => {
    if (!selectedAnswer || result) return
    setIsSubmitting(true)
    setError(null)
    try {
      setResult(await onSubmit(question.id, selectedAnswer))
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : '答案提交失败。')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleNext = () => {
    if (isLast) {
      onClose()
      return
    }
    setQuestionIndex((current) => current + 1)
    setSelectedAnswer(null)
    setResult(null)
    setError(null)
  }

  return (
    <div className="fixed inset-0 z-[75] flex items-center justify-center bg-slate-950/35 p-4" role="presentation">
      <section role="dialog" aria-modal="true" aria-labelledby="exercise-title" className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.16em] text-indigo-600">
              第 {questionIndex + 1} / {session.questions.length} 题
            </p>
            <h2 id="exercise-title" className="mt-1 text-xl font-extrabold text-slate-950">{session.title}</h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100" aria-label="关闭练习">
            <X className="size-5" />
          </button>
        </div>

        <p className="mt-6 text-base font-bold leading-7 text-slate-900">{question.stem}</p>
        <div className="mt-4 space-y-2">
          {question.options.map((option) => {
            const selected = selectedAnswer === option
            const correct = result?.answer === option
            const wrong = Boolean(result && selected && !result.correct)
            return (
              <button
                key={option}
                type="button"
                disabled={Boolean(result)}
                onClick={() => setSelectedAnswer(option)}
                className={`flex w-full items-center justify-between rounded-xl border px-4 py-3 text-left text-sm font-bold transition ${
                  correct
                    ? 'border-emerald-300 bg-emerald-50 text-emerald-800'
                    : wrong
                      ? 'border-red-300 bg-red-50 text-red-700'
                      : selected
                        ? 'border-indigo-400 bg-indigo-50 text-indigo-800'
                        : 'border-slate-200 text-slate-700 hover:border-indigo-200 hover:bg-indigo-50/50'
                }`}
              >
                <span>{option}</span>
                {correct ? <CheckCircle2 className="size-5 shrink-0" /> : null}
                {wrong ? <XCircle className="size-5 shrink-0" /> : null}
              </button>
            )
          })}
        </div>

        {result ? (
          <div className={`mt-4 rounded-xl p-4 text-sm ${result.correct ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-900'}`}>
            <p className="font-extrabold">{result.correct ? '回答正确' : `正确答案：${result.answer}`}</p>
            <p className="mt-1 leading-6">{result.explanation}</p>
          </div>
        ) : null}
        {error ? <p className="mt-3 text-sm font-semibold text-red-600">{error}</p> : null}

        <div className="mt-6 flex justify-end">
          {result ? (
            <button type="button" onClick={handleNext} className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-extrabold text-white hover:bg-emerald-700">
              {isLast ? '完成练习' : '下一题'}
            </button>
          ) : (
            <button type="button" disabled={!selectedAnswer || isSubmitting} onClick={() => void handleSubmit()} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-extrabold text-white hover:bg-indigo-700 disabled:opacity-50">
              {isSubmitting ? <LoaderCircle className="size-4 animate-spin" /> : null}
              提交答案
            </button>
          )}
        </div>
      </section>
    </div>
  )
}
