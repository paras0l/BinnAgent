/* eslint-disable react-refresh/only-export-components -- Draft persistence helpers are exported for regression tests. */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowLeft,
  Beaker,
  Clock3,
  History,
  LoaderCircle,
  PenLine,
  RefreshCw,
  Sparkles,
  Trash2,
} from 'lucide-react'
import { ExpressionActionBar } from '@/components/expression-lab/ExpressionActionBar'
import { ExpressionActionDialog } from '@/components/expression-lab/ExpressionActionDialog'
import { ExpressionEvidenceDrawer } from '@/components/expression-lab/ExpressionEvidenceDrawer'
import {
  ExpressionBlockSkeleton,
  GeneratedUiRenderer,
} from '@/components/expression-lab/GeneratedUiRenderer'
import type { SandboxTelemetryEvent } from '@/components/expression-lab/SandboxWidget'
import { FeatureHero } from '@/components/layout/FeatureHero'
import { PageShell } from '@/components/layout/PageShell'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { FormField } from '@/components/ui/FormField'
import { Select } from '@/components/ui/Select'
import { StatusBanner } from '@/components/ui/StatusBanner'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import { useToast } from '@/hooks/useToast'
import {
  completeExpressionLabSession,
  createExpressionLabSession,
  deleteExpressionLabSession,
  executeExpressionLabAction,
  getExpressionLabSession,
  listExpressionLabSessionPage,
  recordExpressionLabSessionEvent,
  regenerateExpressionLabBlock,
  submitExpressionLabAttempt,
  type ExpressionAttemptResult,
  type ExpressionInputType,
  type ExpressionLabSessionDetail,
  type ExpressionLabSessionSummary,
  type ExpressionSystemAction,
  type ExpressionUiBlock,
} from '@/services/expressionLabApi'
import type { Learner, LearnerProfile } from '@/types'
import { copyTextToClipboard } from '@/utils/clipboard'

const DRAFT_STORAGE_PREFIX = 'binnExpressionLabDraft:v1:'
const GROUP_LEARNING_REFRESH_EVENT = 'binnagent:group-learning-signals-updated'
const SAVE_ACTION_TYPES = new Set(['save_writing_phrase', 'save_vocabulary', 'save_grammar_point', 'create_practice'])
const SUCCESSFUL_ACTION_STATES = new Set(['applied', 'saved', 'dismissed'])

export interface ExpressionLabSourceSeed {
  id: string
  signalType: string
  text: string
  label?: string | null
}

export interface ExpressionLabPageProps {
  learner: Learner
  learnerProfile?: LearnerProfile | null
  initialSessionId?: string | null
  sourceSignal?: ExpressionLabSourceSeed | null
  initialInputType?: ExpressionInputType
  initialText?: string
  onBack: () => void
  onSessionChange?: (sessionId: string | null) => void
}

export interface ExpressionLabDraft {
  inputType: ExpressionInputType
  text: string
  context: string
  style: string
  level: string
  needsPractice: boolean
}

export function ExpressionLabPage({
  learner,
  learnerProfile,
  initialSessionId = null,
  sourceSignal = null,
  initialInputType,
  initialText,
  onBack,
  onSessionChange,
}: ExpressionLabPageProps) {
  const { showToast } = useToast()
  const [draft, setDraft] = useState<ExpressionLabDraft>(() => initialDraft(
    learner.id,
    learnerProfile,
    sourceSignal,
    initialInputType,
    initialText,
  ))
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId)
  const [session, setSession] = useState<ExpressionLabSessionDetail | null>(null)
  const [recentSessions, setRecentSessions] = useState<ExpressionLabSessionSummary[]>([])
  const [pendingSessionCount, setPendingSessionCount] = useState(0)
  const [isRecentLoading, setIsRecentLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [isSessionLoading, setIsSessionLoading] = useState(Boolean(initialSessionId))
  const [isCompleting, setIsCompleting] = useState(false)
  const [regeneratingBlockId, setRegeneratingBlockId] = useState<string | null>(null)
  const [selectedAction, setSelectedAction] = useState<ExpressionSystemAction | null>(null)
  const [actionStates, setActionStates] = useState<Record<string, string>>({})
  const [actionError, setActionError] = useState<string | null>(null)
  const [pageError, setPageError] = useState<string | null>(null)
  const [isEvidenceOpen, setIsEvidenceOpen] = useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const reportedEventsRef = useRef(new Set<string>())

  const refreshRecent = useCallback(async (signal?: AbortSignal) => {
    try {
      const page = await listExpressionLabSessionPage(learner.id, 8, signal)
      setRecentSessions(page.sessions)
      setPendingSessionCount(page.pending_count)
    } catch (error) {
      if (!isAbortError(error)) console.error('Expression Lab recent sessions failed', error)
    } finally {
      if (!signal?.aborted) setIsRecentLoading(false)
    }
  }, [learner.id])

  const refreshSession = useCallback(async (targetSessionId: string, signal?: AbortSignal) => {
    const detail = await getExpressionLabSession(learner.id, targetSessionId, signal)
    setSession(detail)
    setPageError(detail.status === 'error' ? detail.error_message || '本次生成没有完成，可以保留输入后重试。' : null)
    setActionStates(Object.fromEntries(detail.actions.map((action) => [action.id, normalizeActionState(action.status)])))
    return detail
  }, [learner.id])

  useEffect(() => {
    saveExpressionLabDraft(learner.id, draft)
  }, [draft, learner.id])

  useEffect(() => {
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      void refreshRecent(controller.signal)
    }, 0)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [refreshRecent])

  useEffect(() => {
    if (!sessionId) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      void refreshSession(sessionId, controller.signal)
        .catch((error: unknown) => {
          if (!isAbortError(error)) setPageError(errorMessage(error, '这次表达学习暂时无法打开。'))
        })
        .finally(() => {
          if (!controller.signal.aborted) setIsSessionLoading(false)
        })
    }, 0)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [refreshSession, sessionId])

  useEffect(() => {
    if (!sessionId || session?.status !== 'generating') return
    let active = true
    let timer: number | null = null
    let attempt = 0
    const poll = async () => {
      try {
        const detail = await refreshSession(sessionId)
        if (!active || detail.status !== 'generating') {
          void refreshRecent()
          return
        }
        attempt += 1
        timer = window.setTimeout(poll, Math.min(3_000, 900 + attempt * 200))
      } catch (error) {
        if (!active) return
        attempt += 1
        if (attempt >= 8) setPageError(errorMessage(error, '生成等待时间较长，可以稍后从最近会话继续。'))
        else timer = window.setTimeout(poll, Math.min(4_000, 1_200 + attempt * 300))
      }
    }
    timer = window.setTimeout(poll, 900)
    return () => {
      active = false
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [refreshRecent, refreshSession, session?.status, sessionId])

  const actions = useMemo(() => {
    if (!session) return []
    if (session.actions.length > 0) return session.actions
    return session.ui_spec?.learning_actions ?? []
  }, [session])
  const blocks = session?.ui_spec?.blocks ?? []
  const savedCount = actions.filter((action) => ['save_writing_phrase', 'save_vocabulary', 'save_grammar_point'].includes(action.type) && (actionStates[action.id] === 'saved' || normalizeActionState(action.status) === 'saved')).length
  const candidateCount = actions.filter((action) => SAVE_ACTION_TYPES.has(action.type) && !['saved', 'saving'].includes(actionStates[action.id] ?? normalizeActionState(action.status))).length
  const practiceAction = actions.find((action) => action.type === 'create_practice')
  const practiceActionState = practiceAction ? actionStates[practiceAction.id] ?? normalizeActionState(practiceAction.status) : null
  const pageStatus = pageError ? 'error' : session?.status ?? (sessionId || isCreating || isSessionLoading ? 'generating' : 'idle')

  const reportSessionEvent = useCallback((eventType: 'block_viewed' | 'source_opened' | 'sandbox_interaction', payload: Record<string, unknown>, dedupeKey: string) => {
    if (!sessionId) return
    const fingerprint = `${sessionId}:${dedupeKey}`
    if (reportedEventsRef.current.has(fingerprint)) return
    reportedEventsRef.current.add(fingerprint)
    void recordExpressionLabSessionEvent(learner.id, sessionId, eventType, payload).catch((error) => {
      console.warn(`Expression Lab ${eventType} event was not recorded`, error)
    })
  }, [learner.id, sessionId])

  const handleBlockViewed = useCallback((block: ExpressionUiBlock, index: number) => {
    reportSessionEvent('block_viewed', { block_id: block.id, block_type: block.type, position: index }, `block_viewed:${block.id}`)
  }, [reportSessionEvent])

  const handleSandboxEvent = useCallback((blockId: string, message: SandboxTelemetryEvent) => {
    const payload = { block_id: blockId, event_type: message.type, payload: message.payload }
    reportSessionEvent('sandbox_interaction', payload, `sandbox_interaction:${blockId}:${message.type}:${safeFingerprint(message.payload)}`)
  }, [reportSessionEvent])

  const handleCreate = async () => {
    if (!draft.text.trim()) {
      showToast('先输入想表达、想修正或想迁移的内容。', { variant: 'warning' })
      return
    }
    setIsCreating(true)
    setPageError(null)
    try {
      const created = await createExpressionLabSession(learner.id, {
        input_type: draft.inputType,
        text: draft.text.trim(),
        context: draft.context || null,
        style: draft.style || null,
        current_level: draft.level || null,
        needs_practice: draft.needsPractice,
        source_signal_id: sourceSignal?.id ?? null,
      })
      setSessionId(created.session_id)
      setSession({
        session_id: created.session_id,
        status: 'generating',
        input_type: draft.inputType,
        input_text: draft.text.trim(),
        context: draft.context || null,
        style_goal: draft.style || null,
        current_level: draft.level || null,
        needs_practice: draft.needsPractice,
        source: sourceSignal ? { type: 'group_learning_signal', source_id: sourceSignal.id, label: sourceSignal.label, text: sourceSignal.text } : { type: 'manual' },
        actions: [], attempts: [], evidence: [], diagnostics: null, created_at: new Date().toISOString(), completed_at: null,
      })
      onSessionChange?.(created.session_id)
      void refreshRecent()
    } catch (error) {
      setPageError(errorMessage(error, '表达学习界面生成失败，请保留输入后重试。'))
    } finally {
      setIsCreating(false)
    }
  }

  const executeAction = useCallback(async (action: ExpressionSystemAction, edits: Record<string, unknown> = {}) => {
    if (!sessionId) return
    setActionStates((current) => ({ ...current, [action.id]: 'saving' }))
    setActionError(null)
    try {
      const result = await executeExpressionLabAction(learner.id, sessionId, action.id, { confirmed: true, edits })
      if (!SUCCESSFUL_ACTION_STATES.has(result.status)) {
        setActionStates((current) => ({ ...current, [action.id]: 'failed' }))
        setActionError(actionFailureMessage(result))
        void refreshSession(sessionId)
        return
      }
      setActionStates((current) => ({ ...current, [action.id]: 'saved' }))
      setSelectedAction(null)
      void refreshSession(sessionId)
    } catch (error) {
      setActionStates((current) => ({ ...current, [action.id]: 'failed' }))
      setActionError(errorMessage(error, '这项学习资产保存失败，内容仍保留在页面中。'))
    }
  }, [learner.id, refreshSession, sessionId])

  const handleAction = useCallback((action: ExpressionSystemAction) => {
    if (action.requires_confirmation || SAVE_ACTION_TYPES.has(action.type)) setSelectedAction(action)
    else void executeAction(action)
  }, [executeAction])

  const handleCopy = useCallback(async (text: string, action?: ExpressionSystemAction) => {
    if (!text) return
    const copied = await copyTextToClipboard(text)
    showToast(copied ? '表达已复制。' : '浏览器未允许自动复制，请手动选择文本。', { variant: copied ? 'success' : 'warning' })
    if (copied && action) void executeAction(action)
  }, [executeAction, showToast])

  const handleAttempt = useCallback(async (blockId: string, questionId: string, answer: unknown): Promise<ExpressionAttemptResult> => {
    if (!sessionId) throw new Error('Session is not ready')
    const result = await submitExpressionLabAttempt(learner.id, sessionId, { block_id: blockId, question_id: questionId, answer })
    void refreshSession(sessionId)
    return result
  }, [learner.id, refreshSession, sessionId])

  const handleRegenerate = useCallback(async (blockId: string) => {
    if (!sessionId || regeneratingBlockId) return
    setRegeneratingBlockId(blockId)
    setActionError(null)
    try {
      const detail = await regenerateExpressionLabBlock(learner.id, sessionId, blockId)
      setSession(detail)
      setActionStates(Object.fromEntries(detail.actions.map((action) => [action.id, normalizeActionState(action.status)])))
    } catch (error) {
      setActionError(errorMessage(error, '这个模块重新生成失败，原内容已经保留。'))
    } finally {
      setRegeneratingBlockId(null)
    }
  }, [learner.id, regeneratingBlockId, sessionId])

  const handleComplete = async () => {
    if (!sessionId || isCompleting) return
    setIsCompleting(true)
    try {
      const detail = await completeExpressionLabSession(learner.id, sessionId)
      setSession(detail)
      window.dispatchEvent(new CustomEvent(GROUP_LEARNING_REFRESH_EVENT))
      void refreshRecent()
    } catch (error) {
      setActionError(errorMessage(error, '本次学习暂时无法完成，已保存的内容不会丢失。'))
    } finally {
      setIsCompleting(false)
    }
  }

  const handleDismiss = () => {
    const action = actions.find((item) => item.type === 'dismiss_suggestion' && actionStates[item.id] !== 'saved')
    if (action) handleAction(action)
    else showToast('已记录反馈，后续会减少类似推荐。', { variant: 'success' })
  }

  const handleDelete = async () => {
    if (!sessionId) return
    setIsDeleting(true)
    try {
      await deleteExpressionLabSession(learner.id, sessionId)
      setIsDeleteOpen(false)
      openSession(null)
      void refreshRecent()
      showToast('这次表达学习记录已删除。', { variant: 'success' })
    } catch (error) {
      setActionError(errorMessage(error, '删除失败，请稍后重试。'))
    } finally {
      setIsDeleting(false)
    }
  }

  const openSession = (nextSessionId: string | null) => {
    setPageError(null)
    setActionError(null)
    setSession(null)
    setSessionId(nextSessionId)
    onSessionChange?.(nextSessionId)
  }

  const editAsNew = () => {
    if (session) setDraft({
      inputType: session.input_type,
      text: session.input_text,
      context: session.context ?? '',
      style: session.style_goal ?? '',
      level: session.current_level ?? session.level ?? draft.level,
      needsPractice: session.needs_practice ?? session.include_practice ?? true,
    })
    openSession(null)
  }

  const handleOpenEvidence = () => {
    setIsEvidenceOpen(true)
    reportSessionEvent('source_opened', {
      source_type: session?.source?.type ?? 'manual',
      source_id: session?.source?.source_id ?? null,
    }, 'source_opened')
  }

  if (pageStatus === 'idle') {
    return (
      <ExpressionLabStart
        draft={draft}
        learnerName={learner.nickname}
        pendingCount={pendingSessionCount}
        recentSessions={recentSessions}
        isRecentLoading={isRecentLoading}
        isCreating={isCreating}
        sourceSignal={sourceSignal}
        onBack={onBack}
        onCreate={() => void handleCreate()}
        onDraftChange={setDraft}
        onOpenSession={(id) => openSession(id)}
      />
    )
  }

  if (pageStatus === 'error') {
    return (
      <PageShell>
        <FeatureHero eyebrow="Expression Lab" title="英语表达实验室" description="你的输入仍保留在当前浏览器中，可以调整后重新生成。" actions={<Button variant="secondary" onClick={onBack}><ArrowLeft className="size-4" />返回</Button>} />
        <StatusBanner tone="warning" title="这次生成没有完成" action={<Button onClick={editAsNew}><RefreshCw className="size-4" />保留输入重试</Button>}>{pageError}</StatusBanner>
        <RecentSessionsPanel sessions={recentSessions} isLoading={isRecentLoading} onOpen={openSession} />
      </PageShell>
    )
  }

  if (!session || pageStatus === 'generating') {
    return (
      <PageShell variant="full" className="h-[calc(100dvh-4rem)] overflow-hidden" contentClassName="h-full min-h-0 max-w-[1400px] gap-3 py-3 sm:py-4">
        <GeneratingHeader inputText={session?.input_text ?? draft.text} onBack={onBack} />
        <StatusBanner title="正在生成你的表达学习界面">系统正在比较表达、组织结构并准备练习；已通过校验的模块会在完成后显示。</StatusBanner>
        <main className="min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1">
          <div className="space-y-4"><ExpressionBlockSkeleton /><ExpressionBlockSkeleton /><ExpressionBlockSkeleton /></div>
        </main>
        <div className="shrink-0 border-t border-slate-200 bg-white px-3 py-3"><Button variant="secondary" onClick={onBack}><ArrowLeft className="size-4" />退出，稍后从最近会话继续</Button></div>
      </PageShell>
    )
  }

  return (
    <PageShell variant="full" className="h-[calc(100dvh-4rem)] overflow-hidden" contentClassName="h-full min-h-0 max-w-[1400px] gap-3 py-3 sm:py-4">
      <SessionInputSummary session={session} onBack={onBack} onDelete={() => setIsDeleteOpen(true)} onEdit={editAsNew} />
      {session.status === 'partial' ? <StatusBanner tone="warning" title="部分模块已安全降级">有些生成内容没有通过校验，页面已保留可用模块；你可以单独重新生成。</StatusBanner> : null}
      {session.status === 'completed' ? <StatusBanner tone="success" title="本次表达学习已完成">已保存 {savedCount} 项学习资产，练习和来源证据也已记录。</StatusBanner> : null}
      {actionError ? <StatusBanner tone="warning" title="操作没有完成" action={<Button variant="ghost" className="px-3 py-2 text-xs" onClick={() => setActionError(null)}>关闭</Button>}>{actionError}</StatusBanner> : null}
      <div className="grid min-h-0 flex-1 overflow-hidden xl:grid-cols-[minmax(0,1fr)_340px]">
        <main className="min-h-0 overflow-y-auto overscroll-contain pb-4 pr-1 xl:pr-4" aria-label="表达学习内容">
          <GeneratedUiRenderer blocks={blocks} attempts={session.attempts} actions={actions} actionStates={actionStates} regeneratingBlockId={regeneratingBlockId} canRegenerate={session.status !== 'completed'} onAction={handleAction} onCopy={(text, action) => void handleCopy(text, action)} onAttempt={handleAttempt} onRegenerate={(blockId) => void handleRegenerate(blockId)} onBlockViewed={handleBlockViewed} onSandboxEvent={handleSandboxEvent} />
        </main>
        <ExpressionEvidenceDrawer session={session} open={isEvidenceOpen} onClose={() => setIsEvidenceOpen(false)} />
      </div>
      <ExpressionActionBar isCompleting={isCompleting} isCompleted={session.status === 'completed'} savedCount={savedCount} candidateCount={candidateCount} canCreatePractice={Boolean(practiceAction && !['saved', 'saving'].includes(practiceActionState ?? 'candidate'))} isCreatingPractice={practiceActionState === 'saving'} onCreatePractice={() => practiceAction && handleAction(practiceAction)} onComplete={() => void handleComplete()} onDismiss={handleDismiss} onExit={onBack} onOpenEvidence={handleOpenEvidence} />
      <ExpressionActionDialog action={selectedAction} isBusy={Boolean(selectedAction && actionStates[selectedAction.id] === 'saving')} onCancel={() => setSelectedAction(null)} onConfirm={(edits) => selectedAction && void executeAction(selectedAction, edits)} />
      <ConfirmDialog open={isDeleteOpen} title="删除这次表达学习？" description="会删除本次生成界面、动作和练习记录；已经单独保存到词汇本或好句收藏馆的资产不会自动删除。" confirmLabel="删除会话" danger isBusy={isDeleting} onCancel={() => setIsDeleteOpen(false)} onConfirm={() => void handleDelete()} />
    </PageShell>
  )
}

function ExpressionLabStart({
  draft,
  learnerName,
  pendingCount,
  recentSessions,
  isRecentLoading,
  isCreating,
  sourceSignal,
  onBack,
  onCreate,
  onDraftChange,
  onOpenSession,
}: {
  draft: ExpressionLabDraft
  learnerName: string
  pendingCount: number
  recentSessions: ExpressionLabSessionSummary[]
  isRecentLoading: boolean
  isCreating: boolean
  sourceSignal: ExpressionLabSourceSeed | null
  onBack: () => void
  onCreate: () => void
  onDraftChange: (draft: ExpressionLabDraft) => void
  onOpenSession: (sessionId: string) => void
}) {
  return (
    <PageShell>
      <FeatureHero eyebrow="Expression Lab" title="英语表达实验室" description="把中文意图、英文草稿、收藏好句或学习线索，变成可比较、可练习、可保存的英语表达。" stats={[{ label: '最近会话', value: recentSessions.length }, { label: '待继续', value: pendingCount, tone: pendingCount > 0 ? 'warning' : 'success' }, { label: '输入方式', value: 4 }, { label: '动态模块', value: 10, tone: 'primary' }]} actions={<Button variant="secondary" onClick={onBack}><ArrowLeft className="size-4" />返回</Button>} />
      {sourceSignal ? <StatusBanner title="来自群聊学习线索">已带入“{sourceSignal.label || signalTypeLabel(sourceSignal.signalType)}”的来源消息；打开实验室不会自动接受或写入资产。</StatusBanner> : null}
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_330px]">
        <SurfaceCard>
          <div className="flex items-center gap-2"><Beaker className="size-5 text-primary" /><h2 className="text-lg font-black text-slate-950">{learnerName}，这次想解决什么表达？</h2></div>
          <p className="mt-1 text-sm leading-6 text-slate-500">先选择输入类型，系统会决定最合适的比较、结构、纠错和练习模块。</p>
          <div className="mt-5 grid gap-2 sm:grid-cols-2" role="group" aria-label="输入类型">
            {INPUT_TYPES.map((item) => <button key={item.id} type="button" aria-pressed={draft.inputType === item.id} onClick={() => onDraftChange({ ...draft, inputType: item.id })} className={`rounded-xl border p-3 text-left transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${draft.inputType === item.id ? 'border-primary bg-primary/10' : 'border-slate-200 bg-white hover:border-primary/30'}`}><span className="block text-sm font-black text-slate-950">{item.label}</span><span className="mt-1 block text-xs leading-5 text-slate-500">{item.description}</span></button>)}
          </div>
          <div className="mt-5">
            <FormField as="textarea" label={inputLabel(draft.inputType)} description="可以直接粘贴群聊原句、英文草稿或完整好句。" name="expression_lab_text" value={draft.text} onChange={(event) => onDraftChange({ ...draft, text: event.target.value })} rows={5} placeholder={inputPlaceholder(draft.inputType)} />
            <p className="mt-1 text-right text-xs text-slate-400">{draft.text.length} / 4000</p>
          </div>
          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            <LabeledSelect label="使用场景" value={draft.context} onChange={(value) => onDraftChange({ ...draft, context: value })} options={CONTEXT_OPTIONS} />
            <LabeledSelect label="目标风格" value={draft.style} onChange={(value) => onDraftChange({ ...draft, style: value })} options={STYLE_OPTIONS} />
            <LabeledSelect label="当前水平" value={draft.level} onChange={(value) => onDraftChange({ ...draft, level: value })} options={LEVEL_OPTIONS} />
          </div>
          <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4"><input type="checkbox" checked={draft.needsPractice} onChange={(event) => onDraftChange({ ...draft, needsPractice: event.target.checked })} className="mt-1 size-4 accent-indigo-600" /><span><span className="block text-sm font-black text-slate-900">生成 1–3 道小练习</span><span className="mt-1 block text-xs leading-5 text-slate-500">用翻译、改写、填空或情景选择检查是否真正会用。</span></span></label>
          <Button className="mt-6 w-full py-3" onClick={onCreate} disabled={isCreating || !draft.text.trim()}>{isCreating ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4" />}{isCreating ? '正在创建表达学习界面…' : '生成表达学习界面'}</Button>
        </SurfaceCard>
        <RecentSessionsPanel sessions={recentSessions} isLoading={isRecentLoading} onOpen={onOpenSession} />
      </div>
    </PageShell>
  )
}

function RecentSessionsPanel({ sessions, isLoading, onOpen }: { sessions: ExpressionLabSessionSummary[]; isLoading: boolean; onOpen: (sessionId: string) => void }) {
  return (
    <SurfaceCard className="self-start">
      <div className="flex items-center gap-2"><History className="size-5 text-primary" /><h2 className="text-base font-black text-slate-950">最近表达学习</h2></div>
      <p className="mt-1 text-xs leading-5 text-slate-500">生成中的会话也可以从这里继续，不需要停在页面等待。</p>
      <div className="mt-4 space-y-2">
        {isLoading ? <div className="flex items-center gap-2 py-6 text-sm text-slate-500"><LoaderCircle className="size-4 animate-spin" />正在读取最近会话…</div> : sessions.length > 0 ? sessions.map((item) => <button key={item.session_id} type="button" onClick={() => onOpen(item.session_id)} className="w-full rounded-xl border border-slate-200 p-3 text-left transition hover:border-primary/30 hover:bg-indigo-50/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"><span className="flex items-center justify-between gap-2"><span className="min-w-0 truncate text-sm font-black text-slate-900">{item.input_text}</span><SessionStatusBadge status={item.status} /></span><span className="mt-2 block text-xs text-slate-500">{inputTypeLabel(item.input_type)} · {formatDate(item.created_at)}</span></button>) : <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-center"><Clock3 className="mx-auto size-5 text-slate-400" /><p className="mt-2 text-sm font-black text-slate-800">还没有表达学习记录</p><p className="mt-1 text-xs leading-5 text-slate-500">完成上面的输入后，生成结果会出现在这里。</p></div>}
      </div>
    </SurfaceCard>
  )
}

function GeneratingHeader({ inputText, onBack }: { inputText: string; onBack: () => void }) {
  return <SurfaceCard className="shrink-0 p-4"><div className="flex items-center justify-between gap-3"><div className="min-w-0"><p className="text-xs font-black uppercase tracking-wide text-primary">正在生成</p><p className="mt-1 truncate text-sm font-black text-slate-900">{inputText}</p></div><Button variant="secondary" className="shrink-0 px-3 py-2 text-xs" onClick={onBack}><ArrowLeft className="size-4" />返回</Button></div></SurfaceCard>
}

function SessionInputSummary({ session, onBack, onDelete, onEdit }: { session: ExpressionLabSessionDetail; onBack: () => void; onDelete: () => void; onEdit: () => void }) {
  return (
    <SurfaceCard className="shrink-0 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className="rounded-md bg-indigo-50 px-2 py-1 text-xs font-black text-indigo-700">{inputTypeLabel(session.input_type)}</span>{session.context ? <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-bold text-slate-600">{optionLabel(CONTEXT_OPTIONS, session.context)}</span> : null}{session.style_goal ? <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-bold text-slate-600">{optionLabel(STYLE_OPTIONS, session.style_goal)}</span> : null}</div><p className="mt-2 truncate text-base font-black text-slate-950">{session.input_text}</p></div>
        <div className="flex shrink-0 flex-wrap gap-2"><Button variant="ghost" className="px-3 py-2 text-xs" onClick={onBack}><ArrowLeft className="size-4" />返回</Button><Button variant="secondary" className="px-3 py-2 text-xs" onClick={onEdit}><PenLine className="size-4" />调整输入</Button><Button variant="ghost" className="px-3 py-2 text-xs text-rose-600" onClick={onDelete}><Trash2 className="size-4" />删除</Button></div>
      </div>
    </SurfaceCard>
  )
}

function LabeledSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: Array<{ value: string; label: string }> }) {
  return <label className="text-sm font-bold text-slate-700"><span>{label}</span><Select name={`expression_lab_${label}`} value={value} onChange={(event) => onChange(event.target.value)} wrapperClassName="mt-1.5" className="font-normal">{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</Select></label>
}

function SessionStatusBadge({ status }: { status: string }) {
  const className = status === 'completed' ? 'bg-emerald-50 text-emerald-700' : status === 'generating' ? 'bg-sky-50 text-sky-700' : status === 'error' ? 'bg-rose-50 text-rose-700' : status === 'partial' ? 'bg-amber-50 text-amber-700' : 'bg-indigo-50 text-indigo-700'
  return <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-black ${className}`}>{statusLabel(status)}</span>
}

export function readExpressionLabDraft(learnerId: string): ExpressionLabDraft | null {
  try {
    const raw = sessionStorage.getItem(`${DRAFT_STORAGE_PREFIX}${learnerId}`)
    if (!raw) return null
    const value = JSON.parse(raw) as Partial<ExpressionLabDraft>
    const inputType = value.inputType
    if (!inputType || !INPUT_TYPES.some((item) => item.id === inputType)) return null
    return { inputType, text: typeof value.text === 'string' ? value.text : '', context: typeof value.context === 'string' ? value.context : '', style: typeof value.style === 'string' ? value.style : '', level: typeof value.level === 'string' ? value.level : '', needsPractice: value.needsPractice !== false }
  } catch { return null }
}

export function saveExpressionLabDraft(learnerId: string, draft: ExpressionLabDraft) {
  try { sessionStorage.setItem(`${DRAFT_STORAGE_PREFIX}${learnerId}`, JSON.stringify(draft)) } catch { /* Keep the current in-memory draft usable. */ }
}

function initialDraft(learnerId: string, profile?: LearnerProfile | null, sourceSignal?: ExpressionLabSourceSeed | null, inputType?: ExpressionInputType, text?: string): ExpressionLabDraft {
  const stored = readExpressionLabDraft(learnerId)
  return { inputType: inputType ?? sourceInputType(sourceSignal?.signalType) ?? stored?.inputType ?? 'zh_intent', text: text ?? sourceSignal?.text ?? stored?.text ?? '', context: sourceSignal ? 'group_chat' : stored?.context ?? '', style: stored?.style ?? 'natural', level: stored?.level || profile?.current_level || '', needsPractice: stored?.needsPractice ?? true }
}

const INPUT_TYPES: Array<{ id: ExpressionInputType; label: string; description: string }> = [
  { id: 'zh_intent', label: '中文表达缺口', description: '知道中文意思，但不知道英语怎么说。' },
  { id: 'en_draft', label: '英文草稿修复', description: '检查语法、语气和自然度，并给出改写。' },
  { id: 'good_sentence', label: '好句迁移', description: '拆结构、换槽位，把好句变成自己的表达。' },
  { id: 'learning_target', label: '词汇或语法点', description: '围绕一个词、搭配或规则生成学习界面。' },
]
const CONTEXT_OPTIONS = [{ value: '', label: '未指定' }, { value: 'daily_chat', label: '日常聊天' }, { value: 'group_chat', label: '群聊讨论' }, { value: 'exam_writing', label: '考试写作' }, { value: 'formal_communication', label: '正式沟通' }]
const STYLE_OPTIONS = [{ value: '', label: '由系统判断' }, { value: 'natural', label: '自然' }, { value: 'polite', label: '委婉' }, { value: 'formal', label: '正式' }, { value: 'concise', label: '简洁' }, { value: 'persuasive', label: '有说服力' }]
const LEVEL_OPTIONS = [{ value: '', label: '跟随学习画像' }, { value: 'A1', label: 'A1 入门' }, { value: 'A2', label: 'A2 基础' }, { value: 'B1', label: 'B1 中级' }, { value: 'B2', label: 'B2 中高级' }, { value: 'C1', label: 'C1 高级' }]

function sourceInputType(type?: string): ExpressionInputType | undefined { if (type === 'expression_gap') return 'zh_intent'; if (type === 'grammar_error') return 'en_draft'; if (type === 'good_sentence') return 'good_sentence'; if (type === 'desired_vocabulary' || type === 'desired_grammar') return 'learning_target'; return undefined }
function inputLabel(type: ExpressionInputType) { return type === 'zh_intent' ? '你想表达的中文意思' : type === 'en_draft' ? '需要修正的英文草稿' : type === 'good_sentence' ? '想理解并迁移的好句' : '想学习的词、搭配或语法点' }
function inputPlaceholder(type: ExpressionInputType) { return type === 'zh_intent' ? '例如：这个观点太绝对了，怎样委婉地表达？' : type === 'en_draft' ? '例如：I am agree with you.' : type === 'good_sentence' ? '例如：What matters most is not how fast you learn, but how consistently you practice.' : '例如：be supposed to / because 与 because of' }
function inputTypeLabel(type: ExpressionInputType) { return INPUT_TYPES.find((item) => item.id === type)?.label ?? type }
function signalTypeLabel(type: string) { return type === 'expression_gap' ? '表达缺口' : type === 'grammar_error' ? '语法错误' : type === 'good_sentence' ? '好句候选' : type === 'desired_vocabulary' ? '想学词汇' : type === 'desired_grammar' ? '想学语法' : '学习线索' }
function statusLabel(status: string) { return status === 'completed' ? '已完成' : status === 'generating' ? '生成中' : status === 'partial' ? '部分可用' : status === 'error' ? '生成失败' : '可继续' }
function optionLabel(options: Array<{ value: string; label: string }>, value: string) { return options.find((option) => option.value === value)?.label ?? value }
function formatDate(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) }
function errorMessage(error: unknown, fallback: string) { return error instanceof Error && error.message ? error.message : fallback }
function isAbortError(error: unknown) { return error instanceof DOMException && error.name === 'AbortError' }
export function normalizeActionState(status?: string | null) { return status === 'applied' || status === 'dismissed' || status === 'saved' ? 'saved' : status === 'applying' || status === 'saving' ? 'saving' : status === 'failed' ? 'failed' : 'candidate' }
function actionFailureMessage(result: { payload?: Record<string, unknown> }) {
  const code = typeof result.payload?.error_code === 'string' ? result.payload.error_code : ''
  if (code === 'duplicate_asset') return '这项内容已经保存过，无需重复添加。'
  if (code === 'validation_error') return '生成内容没有通过资产校验，请编辑后重试。'
  return '这项操作没有完成，页面内容仍已保留，可以检查后重试。'
}
function safeFingerprint(payload: Record<string, unknown>) {
  try { return JSON.stringify(payload).slice(0, 2_000) } catch { return 'unserializable' }
}
