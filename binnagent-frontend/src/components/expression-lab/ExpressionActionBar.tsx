import { CheckCircle2, FileText, Flag, ListPlus, LoaderCircle, LogOut } from 'lucide-react'
import { Button } from '@/components/ui/Button'

interface ExpressionActionBarProps {
  isCompleting: boolean
  isCompleted: boolean
  savedCount: number
  candidateCount: number
  canCreatePractice: boolean
  isCreatingPractice: boolean
  onComplete: () => void
  onDismiss: () => void
  onExit: () => void
  onOpenEvidence: () => void
  onCreatePractice: () => void
}

export function ExpressionActionBar({
  isCompleting,
  isCompleted,
  savedCount,
  candidateCount,
  canCreatePractice,
  isCreatingPractice,
  onComplete,
  onDismiss,
  onExit,
  onOpenEvidence,
  onCreatePractice,
}: ExpressionActionBarProps) {
  return (
    <footer className="shrink-0 border-t border-slate-200 bg-white px-3 py-3 shadow-[0_-10px_30px_rgba(15,23,42,0.06)] sm:px-6 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
      <div className="mx-auto flex max-w-[1400px] flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center justify-between gap-2 sm:justify-start">
          <Button variant="ghost" className="px-3 py-2 text-xs" onClick={onExit}><LogOut className="size-4" />退出并保留</Button>
          <Button variant="ghost" className="px-3 py-2 text-xs xl:hidden" onClick={onOpenEvidence}><FileText className="size-4" />来源</Button>
          {!isCompleted ? <Button variant="ghost" className="px-3 py-2 text-xs text-slate-500" onClick={onDismiss}><Flag className="size-4" />不适合我</Button> : null}
        </div>
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          <p className="hidden text-xs font-bold text-slate-500 md:block">已保存 {savedCount} 项{candidateCount > 0 ? ` · 还有 ${candidateCount} 项可选择` : ''}</p>
          {!isCompleted && canCreatePractice ? (
            <Button variant="secondary" className="shrink-0 px-3 text-xs" onClick={onCreatePractice} disabled={isCreatingPractice}>
              {isCreatingPractice ? <LoaderCircle className="size-4 animate-spin" /> : <ListPlus className="size-4" />}
              {isCreatingPractice ? '生成中' : '再练一组'}
            </Button>
          ) : null}
          <Button className="flex-1 sm:flex-none" onClick={onComplete} disabled={isCompleting || isCompleted}>
            {isCompleting ? <LoaderCircle className="size-4 animate-spin" /> : <CheckCircle2 className="size-4" />}
            {isCompleting ? '正在完成…' : isCompleted ? '本次学习已完成' : '完成本次学习'}
          </Button>
        </div>
      </div>
    </footer>
  )
}
