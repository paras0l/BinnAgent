import { X } from 'lucide-react'
import { useId } from 'react'
import { ExerciseRenderer } from '@/components/exercise/ExerciseRenderer'
import { IconButton } from '@/components/ui/IconButton'
import { useFocusTrap } from '@/hooks/useFocusTrap'
import type { ExerciseSession } from '@/types'

interface ExerciseSessionDialogProps {
  session: ExerciseSession | null
  learnerId: string
  onClose: () => void
}

export function ExerciseSessionDialog({ session, learnerId, onClose }: ExerciseSessionDialogProps) {
  const titleId = useId()
  const { containerRef, handleKeyDown } = useFocusTrap<HTMLElement>({
    isActive: Boolean(session),
    onEscape: onClose,
  })

  if (!session) return null

  return (
    <div className="fixed inset-0 z-[75] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-950/35" aria-hidden="true" />
      <section
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        className="relative flex max-h-[calc(100dvh-2rem)] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-5">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.16em] text-primary">
              {session.questions.length} 道题
            </p>
            <h2 id={titleId} className="mt-1 text-xl font-extrabold text-slate-950">{session.title}</h2>
          </div>
          <IconButton label="关闭练习" onClick={onClose} className="border-transparent">
            <X className="size-5" />
          </IconButton>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <ExerciseRenderer
            exercises={session.questions}
            learnerId={learnerId}
            onComplete={onClose}
          />
        </div>
      </section>
    </div>
  )
}
