import { X } from 'lucide-react'
import { Button } from '@/components/ui/Button'

export interface CapabilityRecommendation {
  recommendation_id: string
  capability_id: string
  feature_id: string
  title: string
  reason: string
  priority_score: number
  category: string
  action: string
  tool_target?: string | null
  route_hint?: string | null
  prompt_seed?: string | null
  input_payload?: Record<string, unknown>
  evidence_refs?: unknown[]
  source?: string
}

interface CapabilityRecommendationCardProps {
  recommendation: CapabilityRecommendation
  isBusy?: boolean
  onOpen: (recommendation: CapabilityRecommendation) => void
  onDismiss: (recommendation: CapabilityRecommendation) => void
}

export function CapabilityRecommendationCard({
  recommendation,
  isBusy = false,
  onOpen,
  onDismiss,
}: CapabilityRecommendationCardProps) {
  return (
    <article className="flex min-h-[190px] flex-col rounded-lg border border-indigo-100 bg-indigo-50/50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-black uppercase tracking-wide text-indigo-600">
            {labelForCategory(recommendation.category)} · {Math.round(recommendation.priority_score * 100)}%
          </p>
          <h3 className="mt-1 text-base font-black text-slate-950">{recommendation.title}</h3>
        </div>
        <button
          type="button"
          onClick={() => onDismiss(recommendation)}
          disabled={isBusy}
          className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg text-slate-500 transition hover:bg-white hover:text-slate-900 disabled:opacity-50"
          aria-label="暂不需要"
          title="暂不需要"
        >
          <X className="size-4" />
        </button>
      </div>

      <p className="mt-3 flex-1 text-sm leading-6 text-slate-700">{recommendation.reason}</p>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs font-bold text-slate-500">
          evidence_refs: {recommendation.evidence_refs?.length ?? 0}
        </p>
        <Button variant="secondary" onClick={() => onOpen(recommendation)} disabled={isBusy}>
          {recommendation.action === 'tool' || recommendation.action === 'vocabulary-detail' ? '打开入口' : '去练习'}
        </Button>
      </div>
    </article>
  )
}

function labelForCategory(category: string) {
  const labels: Record<string, string> = {
    listening: '听力',
    speaking: '口语',
    reading: '阅读',
    writing: '写作',
    vocabulary: '词汇',
    grammar: '语法',
    exam: '考试冲刺',
  }
  return labels[category] ?? category
}
