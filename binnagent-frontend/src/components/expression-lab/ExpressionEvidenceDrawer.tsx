/* eslint-disable react-refresh/only-export-components -- Evidence normalizers are exported for regression tests. */
import { useId } from 'react'
import { FileText, ShieldCheck, X } from 'lucide-react'
import { EvidencePanel } from '@/components/learning/EvidencePanel'
import { IconButton } from '@/components/ui/IconButton'
import { useFocusTrap } from '@/hooks/useFocusTrap'
import type { ExpressionLabSessionDetail } from '@/services/expressionLabApi'
import { asRecord, displayValue, firstText } from './blockData'

interface ExpressionEvidenceDrawerProps {
  session: ExpressionLabSessionDetail
  open: boolean
  onClose: () => void
}

export function ExpressionEvidenceDrawer({ session, open, onClose }: ExpressionEvidenceDrawerProps) {
  const titleId = useId()
  const { containerRef, handleKeyDown } = useFocusTrap<HTMLElement>({ isActive: open, onEscape: onClose })
  const content = <ExpressionEvidenceContent session={session} />
  return (
    <>
      <aside className="hidden min-h-0 overflow-y-auto border-l border-slate-200 bg-white p-4 xl:block" aria-label="来源与证据">
        {content}
      </aside>
      {open ? (
        <div className="fixed inset-0 z-[70] xl:hidden">
          <button type="button" aria-label="关闭来源与证据" onClick={onClose} className="absolute inset-0 bg-slate-950/35" />
          <section ref={containerRef} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} onKeyDown={handleKeyDown} className="absolute inset-x-0 bottom-0 flex max-h-[78dvh] flex-col overflow-hidden rounded-t-2xl bg-white shadow-2xl focus-visible:outline-2 focus-visible:outline-primary sm:left-auto sm:top-0 sm:h-full sm:max-h-none sm:w-[min(420px,92vw)] sm:rounded-none">
            <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
              <h2 id={titleId} className="text-lg font-black text-slate-950">来源与证据</h2>
              <IconButton label="关闭来源与证据" onClick={onClose}><X className="size-4" /></IconButton>
            </header>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))]">{content}</div>
          </section>
        </div>
      ) : null}
    </>
  )
}

function ExpressionEvidenceContent({ session }: { session: ExpressionLabSessionDetail }) {
  const source = session.source ?? { type: 'manual' }
  const evidenceItems = normalizeExpressionEvidence(session.evidence).map(evidenceLabel).filter(Boolean)
  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs font-black uppercase tracking-wide text-primary">Context</p>
        <h2 className="mt-1 text-lg font-black text-slate-950">来源与学习依据</h2>
        <p className="mt-1 text-sm leading-6 text-slate-500">保存的资产会保留本次会话和来源引用，方便后续回看。</p>
      </div>
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
        <div className="flex items-center gap-2 text-primary"><FileText className="size-4" /><p className="text-xs font-black uppercase tracking-wide">输入来源</p></div>
        <p className="mt-2 text-sm font-black text-slate-900">{source.type === 'group_learning_signal' ? '群聊学习线索' : source.label || '手动输入'}</p>
        {source.text ? <blockquote className="mt-2 border-l-2 border-indigo-300 pl-3 text-sm leading-6 text-slate-600">{source.text}</blockquote> : null}
        {source.confidence !== null && source.confidence !== undefined ? <p className="mt-2 text-xs font-bold text-slate-500">线索可信度 {Math.round(source.confidence * 100)}%</p> : null}
      </div>
      <EvidencePanel title="证据引用" items={evidenceItems} emptyText="本次为手动输入，没有外部来源证据。" />
      <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-4 text-emerald-800">
        <div className="flex items-center gap-2 text-sm font-black"><ShieldCheck className="size-4" />保存边界</div>
        <p className="mt-2 text-xs leading-5">生成内容只会提出保存建议；你确认并可编辑后，系统才会写入好句、词汇或语法资产。</p>
      </div>
    </div>
  )
}

export function normalizeExpressionEvidence(evidence: ExpressionLabSessionDetail['evidence']): unknown[] {
  if (Array.isArray(evidence)) return evidence
  if (!evidence || typeof evidence !== 'object') return []
  return Object.entries(evidence).flatMap(([key, value]) => {
    if (Array.isArray(value)) return value.map((item) => ({ type: key, ...asRecord(item) }))
    if (value && typeof value === 'object') return [{ type: key, ...asRecord(value) }]
    return value === null || value === undefined || value === '' ? [] : [{ type: key, label: displayValue(value) }]
  })
}

export function evidenceLabel(value: unknown) {
  if (typeof value === 'string') return value
  const record = asRecord(value)
  const type = firstText(record, ['type', 'source_type', 'kind'])
  const label = firstText(record, ['label', 'text', 'summary', 'id'])
  return [type, label].filter(Boolean).join(' · ') || displayValue(value)
}
