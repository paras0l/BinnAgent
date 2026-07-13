import { memo, useState } from 'react'
import { AlertTriangle, Boxes, MessageSquarePlus, RefreshCw, Send, X } from 'lucide-react'
import { SandboxWidget, type SandboxTelemetryEvent } from '@/components/expression-lab/SandboxWidget'
import { Button } from '@/components/ui/Button'
import type { ExpressionUiBlock } from '@/services/expressionLabApi'
import type { ChatArtifactAction, InteractiveHtmlArtifact as InteractiveHtmlArtifactData } from './chatArtifacts'

interface InteractiveHtmlArtifactProps {
  artifact: InteractiveHtmlArtifactData
  disabled?: boolean
  onAction: (action: ChatArtifactAction) => void
}

export const InteractiveHtmlArtifact = memo(function InteractiveHtmlArtifact({
  artifact,
  disabled = false,
  onAction,
}: InteractiveHtmlArtifactProps) {
  const [pendingEvent, setPendingEvent] = useState<SandboxTelemetryEvent | null>(null)
  const [runtimeError, setRuntimeError] = useState<string | null>(null)
  const block: ExpressionUiBlock = {
    id: artifact.id,
    type: 'sandbox_widget',
    title: artifact.title,
    data: {
      html: artifact.html,
      css: artifact.css,
      javascript: artifact.javascript,
      height: artifact.height,
      allowed_events: artifact.allowedEvents,
      timeout_ms: 8_000,
    },
  }

  const handleEvent = (event: SandboxTelemetryEvent) => {
    if (disabled || ['ready', 'resize', 'timeout', 'rebuild'].includes(event.type)) return
    const error = typeof event.payload.error === 'string' ? event.payload.error : ''
    if (error) {
      setPendingEvent(null)
      setRuntimeError(error)
      return
    }
    setRuntimeError(null)
    setPendingEvent(event)
  }

  const requestSafeRebuild = () => {
    if (disabled || !runtimeError) return
    onAction({
      message: `这个「${artifact.title}」没能正常打开，请帮我重新生成。`,
      context: {
        artifactId: artifact.id,
        artifactType: artifact.type,
        artifactTitle: artifact.title,
        eventType: 'safe_rebuild_requested',
        payload: { error: runtimeError },
      },
    })
    setRuntimeError(null)
  }

  const sendPendingEvent = () => {
    if (!pendingEvent || disabled) return
    onAction({
      message: naturalInteractionMessage(artifact.title, pendingEvent.payload),
      context: {
        artifactId: artifact.id,
        artifactType: artifact.type,
        artifactTitle: artifact.title,
        eventType: pendingEvent.type,
        payload: pendingEvent.payload,
      },
    })
    setPendingEvent(null)
  }

  return (
    <section className="mt-3 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <header className="flex items-center justify-between gap-3 border-b border-slate-100 px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-indigo-50 text-indigo-600">
            <Boxes className="size-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-xs font-bold text-slate-800">{artifact.title}</p>
            <p className="flex items-center gap-1 text-[11px] text-slate-500">
              <MessageSquarePlus className="size-3" />操作结果可继续带入当前对话
            </p>
          </div>
        </div>
        {pendingEvent ? (
          <Button
            className="shrink-0 px-2.5 py-1.5 text-xs"
            disabled={disabled}
            onClick={sendPendingEvent}
          >
            <Send className="size-3.5" />结果待确认 · 带入对话
          </Button>
        ) : runtimeError ? (
          <span className="shrink-0 rounded-full bg-amber-100 px-2 py-1 text-[10px] font-bold text-amber-800">
            脚本已拦截
          </span>
        ) : (
          <span className="shrink-0 rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-bold text-emerald-700">
            安全沙箱
          </span>
        )}
      </header>
      <div className="p-1.5">
        <SandboxWidget
          block={block}
          actions={[]}
          onAction={() => undefined}
          onEvent={handleEvent}
        />
      </div>
      {runtimeError ? (
        <footer className="flex items-center justify-between gap-3 border-t border-amber-200 bg-amber-50 px-3 py-2.5">
          <p className="flex min-w-0 items-center gap-2 text-xs text-amber-900">
            <AlertTriangle className="size-4 shrink-0" />
            组件脚本触发安全限制，没有执行，也没有发送任何学习结果。
          </p>
          <Button
            variant="secondary"
            className="shrink-0 px-2.5 py-1.5 text-xs"
            disabled={disabled}
            onClick={requestSafeRebuild}
          >
            <RefreshCw className="size-3.5" />请求安全重建
          </Button>
        </footer>
      ) : null}
      {pendingEvent ? (
        <footer className="flex items-center justify-between gap-3 border-t border-indigo-100 bg-indigo-50/70 px-3 py-2.5">
          <p className="min-w-0 text-xs text-indigo-900">
            组件已产生结果，确认后再发送给 AI。
          </p>
          <div className="flex shrink-0 items-center gap-1.5">
            <Button
              variant="ghost"
              className="px-2.5 py-1.5 text-xs"
              onClick={() => setPendingEvent(null)}
            >
              <X className="size-3.5" />忽略
            </Button>
            <Button
              className="px-2.5 py-1.5 text-xs"
              disabled={disabled}
              onClick={sendPendingEvent}
            >
              <Send className="size-3.5" />带入对话
            </Button>
          </div>
        </footer>
      ) : null}
    </section>
  )
})

function naturalInteractionMessage(title: string, payload: Record<string, unknown>): string {
  const answer = [payload.answer, payload.value, payload.selection, payload.choice]
    .find((value) => typeof value === 'string' || typeof value === 'number')
  if (answer !== undefined) return `我在「${title}」中提交了答案：${String(answer)}。请给我反馈。`
  return `我完成了「${title}」中的操作，请结合结果继续指导我。`
}
