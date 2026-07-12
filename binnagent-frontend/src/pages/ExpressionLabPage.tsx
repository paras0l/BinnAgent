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
import { XiaobingAvatar } from '@/components/ui/XiaobingAvatar'
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
  const { beginPetActivity, completePetActivity, showToast } = useToast()
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
  const previousGenerationActiveRef = useRef(false)

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
  const isExpressionGenerationActive = isCreating || session?.status === 'generating'

  useEffect(() => {
    let activityId: string | null = null
    if (isExpressionGenerationActive) {
      const timer = window.setTimeout(() => {
        activityId = beginPetActivity(
          '我正在先挑出一句真正能用的表达，再把理由和练习整理清楚。',
          '小冰正在陪你整理',
        )
      }, 450)
      return () => {
        window.clearTimeout(timer)
        if (activityId) completePetActivity(activityId)
      }
    }
    return undefined
  }, [beginPetActivity, completePetActivity, isExpressionGenerationActive])

  useEffect(() => {
    const previous = previousGenerationActiveRef.current
    previousGenerationActiveRef.current = isExpressionGenerationActive
    if (previous && !isExpressionGenerationActive && session && session.status !== 'error') {
      showToast('整理好了，先看我放在最前面的首选表达。', {
        title: '表达学习界面已准备好',
        variant: 'success',
        motion: 'celebrating',
      })
    }
  }, [isExpressionGenerationActive, session, showToast])

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
      <PageShell variant="full" className="binn-viewport-height overflow-hidden" contentClassName="h-full min-h-0 max-w-[1400px] gap-3 py-3 sm:py-4">
        <GeneratingHeader inputText={session?.input_text ?? draft.text} onBack={onBack} />
        <main data-header-scroll-surface className="min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1">
          <ExpressionLabGeneratingState inputText={session?.input_text ?? draft.text} />
        </main>
        <div className="shrink-0 border-t border-slate-200 bg-white px-3 py-3"><Button variant="secondary" onClick={onBack}><ArrowLeft className="size-4" />退出，稍后从最近会话继续</Button></div>
      </PageShell>
    )
  }

  return (
    <PageShell variant="full" className="binn-viewport-height overflow-hidden" contentClassName="h-full min-h-0 max-w-[1400px] gap-2 py-2.5 sm:py-3">
      <SessionInputSummary session={session} onBack={onBack} onDelete={() => setIsDeleteOpen(true)} onEdit={editAsNew} />
      {session.status === 'partial' ? <StatusBanner compact tone="warning" title="部分模块已安全降级">已保留可用模块，可单独重新生成。</StatusBanner> : null}
      {session.status === 'completed' ? <StatusBanner compact tone="success" title="本次表达学习已完成">已保存 {savedCount} 项学习资产。</StatusBanner> : null}
      {actionError ? <StatusBanner compact tone="warning" title="操作没有完成" action={<Button variant="ghost" className="px-3 py-1.5 text-xs" onClick={() => setActionError(null)}>关闭</Button>}>{actionError}</StatusBanner> : null}
      <div className="grid min-h-0 flex-1 overflow-hidden 2xl:grid-cols-[minmax(0,1fr)_320px]">
        <main data-header-scroll-surface className="min-h-0 overflow-y-auto overscroll-contain pb-3 pr-1 2xl:pr-4" aria-label="表达学习内容">
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
      <FeatureHero eyebrow="Expression Lab" title="英语表达实验室" description="先给你一句当前场景能直接使用的英语，再解释选择理由，并用一个新场景练会它。" stats={[{ label: '最近会话', value: recentSessions.length }, { label: '待继续', value: pendingCount, tone: pendingCount > 0 ? 'warning' : 'success' }, { label: '先解决', value: '怎么说', tone: 'primary' }, { label: '再确认', value: '会不会用', tone: 'success' }]} actions={<Button variant="secondary" onClick={onBack}><ArrowLeft className="size-4" />返回</Button>} />
      {sourceSignal ? <StatusBanner title="来自群聊学习线索">已带入“{sourceSignal.label || signalTypeLabel(sourceSignal.signalType)}”的来源消息；打开实验室不会自动接受或写入资产。</StatusBanner> : null}
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_330px]">
        <SurfaceCard>
          <div className="flex items-center gap-2"><Beaker className="size-5 text-primary" /><h2 className="text-lg font-black text-slate-950">{learnerName}，这次想解决什么表达？</h2></div>
          <p className="mt-1 text-sm leading-6 text-slate-500">尽量补充“要对谁说、在什么场景说”。系统会优先给首选表达，不再堆叠重复模块。</p>
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
          <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4"><input type="checkbox" checked={draft.needsPractice} onChange={(event) => onDraftChange({ ...draft, needsPractice: event.target.checked })} className="mt-1 size-4 accent-indigo-600" /><span><span className="block text-sm font-black text-slate-900">生成 1–2 道小练习</span><span className="mt-1 block text-xs leading-5 text-slate-500">用翻译、改写、填空或情景选择检查是否真正会用。</span></span></label>
          <Button className="mt-6 w-full py-3" onClick={onCreate} disabled={isCreating || !draft.text.trim()}>{isCreating ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4" />}{isCreating ? '正在整理首选表达…' : '给我可直接使用的表达'}</Button>
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

const GENERATION_STAGES = [
  { title: '理解你真正想表达的意思', detail: '结合使用场景和目标语气，避免只做逐字翻译。' },
  { title: '筛选自然、能直接使用的表达', detail: '比较措辞差异，把当前场景首选放到最前面。' },
  { title: '整理理由、例句和迁移练习', detail: '让结果不只是答案，还能真正学会和复用。' },
]

function ExpressionLabGeneratingState({ inputText }: { inputText: string }) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0)

  useEffect(() => {
    const startedAt = Date.now()
    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000))
    }, 1_000)
    return () => window.clearInterval(timer)
  }, [])

  const activeStage = Math.min(GENERATION_STAGES.length - 1, Math.floor(elapsedSeconds / 6))

  return (
    <div className="expression-lab-generating mx-auto flex min-h-full w-full max-w-4xl flex-col justify-center gap-5 py-4 sm:py-8">
      <section className="relative overflow-hidden rounded-[20px] border border-indigo-100 bg-gradient-to-br from-indigo-50/90 via-white to-sky-50/80 p-5 shadow-[0_16px_48px_rgba(79,70,229,0.10)] sm:p-8">
        <div className="pointer-events-none absolute -right-20 -top-24 size-64 rounded-full bg-violet-200/30 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-28 -left-20 size-64 rounded-full bg-sky-200/35 blur-3xl" />
        <div className="relative grid items-center gap-6 md:grid-cols-[180px_minmax(0,1fr)]">
          <div className="relative mx-auto flex size-40 items-center justify-center">
            <div className="absolute inset-0 animate-spin rounded-full border border-dashed border-indigo-300/80 [animation-duration:9s]" />
            <div className="absolute inset-4 animate-spin rounded-full border border-dotted border-sky-300/80 [animation-direction:reverse] [animation-duration:6s]" />
            <div className="absolute inset-7 rounded-full bg-white/85 shadow-[0_8px_28px_rgba(14,165,233,0.14)]" />
            <XiaobingAvatar className="relative size-24 animate-[pulse_2.4s_ease-in-out_infinite] border-4 border-white bg-sky-50 shadow-lg" />
            <span className="absolute bottom-1 right-2 flex size-9 items-center justify-center rounded-full bg-indigo-600 text-white shadow-lg">
              <Sparkles className="size-4 animate-pulse" />
            </span>
          </div>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-indigo-100/80 px-2.5 py-1 text-[11px] font-black text-indigo-800 ring-1 ring-inset ring-indigo-200/80">小冰正在工作</span>
              <span className="text-xs font-bold tabular-nums text-slate-500">已等待 {elapsedSeconds} 秒</span>
            </div>
            <h1 className="mt-3 text-xl font-black tracking-tight text-slate-950 sm:text-2xl">正在生成你的表达学习界面<span className="ml-1 inline-flex w-6 justify-start"><span className="animate-pulse">···</span></span></h1>
            <p className="mt-2 line-clamp-2 text-sm font-bold leading-6 text-slate-600">“{inputText}”</p>
            <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-indigo-100">
              <div className="expression-lab-loading-bar h-full w-2/5 rounded-full bg-gradient-to-r from-indigo-500 via-violet-400 to-sky-400" />
            </div>
            <p className="mt-3 text-xs leading-5 text-slate-500">复杂表达需要多比较一会儿。你可以离开这个页面，生成会继续进行。</p>
          </div>
        </div>

        <ol className="relative mt-7 grid gap-3 md:grid-cols-3" aria-label="生成过程中正在处理的内容">
          {GENERATION_STAGES.map((stage, index) => {
            const visited = index < activeStage
            const active = index === activeStage
            return (
              <li key={stage.title} className={`rounded-xl border p-4 transition-all duration-500 ${active ? 'border-indigo-200 bg-white shadow-[0_8px_24px_rgba(79,70,229,0.08)]' : visited ? 'border-sky-100 bg-sky-50/70' : 'border-slate-200/80 bg-white/55'}`}>
                <div className="flex items-center gap-2">
                  <span className={`flex size-4 items-center justify-center rounded-full border ${active ? 'border-indigo-500 bg-indigo-500 shadow-[0_0_0_4px_rgba(99,102,241,0.12)]' : visited ? 'border-sky-300 bg-sky-100' : 'border-slate-300 bg-white'}`}>{active ? <span className="size-1.5 animate-pulse rounded-full bg-white" /> : visited ? <span className="size-1.5 rounded-full bg-sky-500" /> : null}</span>
                  <span className={`text-[11px] font-black ${active ? 'text-indigo-700' : visited ? 'text-sky-700' : 'text-slate-400'}`}>{active ? '正在重点处理' : visited ? '仍在持续校验' : '随后处理'}</span>
                </div>
                <p className="mt-3 text-sm font-black leading-6 text-slate-900">{stage.title}</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">{stage.detail}</p>
              </li>
            )
          })}
        </ol>
      </section>

      <div className="space-y-3 opacity-70" aria-hidden="true">
        <ExpressionBlockSkeleton compact />
      </div>
    </div>
  )
}

function SessionInputSummary({ session, onBack, onDelete, onEdit }: { session: ExpressionLabSessionDetail; onBack: () => void; onDelete: () => void; onEdit: () => void }) {
  return (
    <section className="shrink-0 border-b border-slate-200 px-1 pb-2.5 pt-1">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-indigo-100/80 px-2.5 py-1 text-[11px] font-black text-indigo-800 ring-1 ring-inset ring-indigo-200/80">{inputTypeLabel(session.input_type)}</span>{session.context ? <span className="rounded-full bg-sky-100/80 px-2.5 py-1 text-[11px] font-black text-sky-800 ring-1 ring-inset ring-sky-200/80">{optionLabel(CONTEXT_OPTIONS, session.context)}</span> : null}{session.style_goal ? <span className="rounded-full bg-violet-100/80 px-2.5 py-1 text-[11px] font-black text-violet-800 ring-1 ring-inset ring-violet-200/80">{optionLabel(STYLE_OPTIONS, session.style_goal)}</span> : null}</div><p className="mt-2 truncate text-base font-black text-slate-950">{session.input_text}</p></div>
        <div className="flex shrink-0 flex-wrap gap-2"><Button variant="ghost" className="px-3 py-2 text-xs" onClick={onBack}><ArrowLeft className="size-4" />返回</Button><Button variant="secondary" className="px-3 py-2 text-xs" onClick={onEdit}><PenLine className="size-4" />调整输入</Button><Button variant="ghost" className="px-3 py-2 text-xs text-rose-600" onClick={onDelete}><Trash2 className="size-4" />删除</Button></div>
      </div>
    </section>
  )
}

function LabeledSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: Array<{ value: string; label: string }> }) {
  return <label className="text-sm font-bold text-slate-700"><span>{label}</span><Select name={`expression_lab_${label}`} value={value} onChange={(event) => onChange(event.target.value)} wrapperClassName="mt-1.5" className="font-normal">{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</Select></label>
}

function SessionStatusBadge({ status }: { status: string }) {
  const className = status === 'completed' ? 'bg-emerald-100/75 text-emerald-800 ring-emerald-200/80' : status === 'generating' ? 'bg-sky-100/80 text-sky-800 ring-sky-200/80' : status === 'error' ? 'bg-rose-100/75 text-rose-800 ring-rose-200/80' : status === 'partial' ? 'bg-amber-100/75 text-amber-800 ring-amber-200/80' : 'bg-indigo-100/80 text-indigo-800 ring-indigo-200/80'
  return <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-black leading-4 ring-1 ring-inset ${className}`}>{statusLabel(status)}</span>
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
  { id: 'learning_target', label: '词汇项或语法知识点', description: '围绕一个词、搭配或规则生成学习界面。' },
]
const CONTEXT_OPTIONS = [{ value: '', label: '未指定' }, { value: 'daily_chat', label: '日常聊天' }, { value: 'group_chat', label: '群聊讨论' }, { value: 'exam_writing', label: '考试写作' }, { value: 'formal_communication', label: '正式沟通' }]
const STYLE_OPTIONS = [{ value: '', label: '由系统判断' }, { value: 'natural', label: '自然' }, { value: 'polite', label: '委婉' }, { value: 'formal', label: '正式' }, { value: 'concise', label: '简洁' }, { value: 'persuasive', label: '有说服力' }]
const LEVEL_OPTIONS = [{ value: '', label: '跟随学习画像' }, { value: 'A1', label: 'A1 入门' }, { value: 'A2', label: 'A2 基础' }, { value: 'B1', label: 'B1 中级' }, { value: 'B2', label: 'B2 中高级' }, { value: 'C1', label: 'C1 高级' }]

function sourceInputType(type?: string): ExpressionInputType | undefined { if (type === 'expression_gap') return 'zh_intent'; if (type === 'grammar_error') return 'en_draft'; if (type === 'good_sentence') return 'good_sentence'; if (type === 'desired_vocabulary' || type === 'desired_grammar') return 'learning_target'; return undefined }
function inputLabel(type: ExpressionInputType) { return type === 'zh_intent' ? '你想表达的中文意思' : type === 'en_draft' ? '需要修正的英文草稿' : type === 'good_sentence' ? '想理解并迁移的好句' : '想学习的词汇项或语法知识点' }
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
