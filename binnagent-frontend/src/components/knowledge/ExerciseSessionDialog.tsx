import { X } from 'lucide-react'
import { ExerciseRenderer } from '@/components/exercise/ExerciseRenderer'
import type { ExerciseSession } from '@/types'

interface ExerciseSessionDialogProps {
  session: ExerciseSession | null
  learnerId: string
  onClose: () => void
}

export function ExerciseSessionDialog({ session, learnerId, onClose }: ExerciseSessionDialogProps) {
  if (!session) return null

  return (
    <div className="fixed inset-0 z-[75] flex items-center justify-center bg-slate-950/35 p-4" role="presentation">
      <section role="dialog" aria-modal="true" aria-labelledby="exercise-title" className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.16em] text-primary">
              {session.questions.length} 道题
            </p>
            <h2 id="exercise-title" className="mt-1 text-xl font-extrabold text-slate-950">{session.title}</h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100" aria-label="关闭练习">
            <X className="size-5" />
          </button>
        </div>

        <ExerciseRenderer
          className="mt-5"
          exercises={session.questions}
          learnerId={learnerId}
          onComplete={onClose}
        />
      </section>
    </div>
  )
}
