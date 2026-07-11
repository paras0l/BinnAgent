/* eslint-disable react-refresh/only-export-components -- Renderer contracts are exported for regression tests. */
import { Component, lazy, Suspense, useEffect, useRef, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, ChevronDown, LoaderCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type {
  ExpressionLabAttempt,
  ExpressionAttemptResult,
  ExpressionSystemAction,
  ExpressionUiBlock,
} from '@/services/expressionLabApi'
import {
  BlockTypeBadge,
  ExpressionVariantsBlock,
  GrammarFocusBlock,
  MicroPracticeBlock,
  PatternDiagramBlock,
  SentenceDiffBlock,
  ToneSpectrumBlock,
  TransferBuilderBlock,
  UsageComparisonBlock,
  VocabularyFocusBlock,
  type ExpressionBlockProps,
} from './ExpressionBlocks'
import type { SandboxTelemetryEvent } from './SandboxWidget'

const SandboxWidget = lazy(() =>
  import('./SandboxWidget').then((module) => ({ default: module.SandboxWidget })),
)

export const SUPPORTED_EXPRESSION_BLOCK_TYPES = new Set([
  'expression_variants',
  'tone_spectrum',
  'sentence_diff',
  'pattern_diagram',
  'usage_comparison',
  'vocabulary_focus',
  'grammar_focus',
  'micro_practice',
  'transfer_builder',
  'sandbox_widget',
])

export const UNKNOWN_BLOCK_MESSAGE = '这个生成模块暂不受支持，其他学习内容仍可继续使用。'

interface GeneratedUiRendererProps {
  blocks: ExpressionUiBlock[]
  attempts: ExpressionLabAttempt[]
  actions: ExpressionSystemAction[]
  actionStates: Record<string, string>
  regeneratingBlockId: string | null
  onAction: (action: ExpressionSystemAction) => void
  onCopy: (text: string, action?: ExpressionSystemAction) => void
  onAttempt: (blockId: string, questionId: string, answer: unknown) => Promise<ExpressionAttemptResult>
  onRegenerate: (blockId: string) => void
  onBlockViewed?: (block: ExpressionUiBlock, index: number) => void
  onSandboxEvent?: (blockId: string, message: SandboxTelemetryEvent) => void
  canRegenerate?: boolean
}

export function GeneratedUiRenderer({
  blocks,
  attempts,
  actions,
  actionStates,
  regeneratingBlockId,
  onAction,
  onCopy,
  onAttempt,
  onRegenerate,
  onBlockViewed,
  onSandboxEvent,
  canRegenerate = true,
}: GeneratedUiRendererProps) {
  if (blocks.length === 0) return <UnsupportedBlock message="生成结果没有可展示的模块，可以重新生成本次内容。" />
  return (
    <div className="divide-y divide-slate-100 overflow-hidden rounded-[16px] border border-slate-200 bg-white shadow-[0_6px_20px_rgba(15,23,42,0.04)]" aria-label="生成的表达学习内容">
      {blocks.map((block, index) => {
        const isRegenerating = regeneratingBlockId === block.id
        return (
          <BlockVisibilityReporter key={block.id} block={block} index={index} onVisible={onBlockViewed}>
            <BlockErrorBoundary blockId={block.id} onRetry={() => onRegenerate(block.id)}>
              <ExpressionBlockCard
                block={block}
                index={index}
                isRegenerating={isRegenerating}
                canRegenerate={canRegenerate}
                onRegenerate={() => onRegenerate(block.id)}
              >
                {isRegenerating ? (
                  <ExpressionBlockSkeleton compact />
                ) : (
                  <BlockContent
                    block={block}
                    attempts={attempts}
                    actions={actions}
                    actionStates={actionStates}
                    onAction={onAction}
                    onCopy={onCopy}
                    onAttempt={onAttempt}
                    onSandboxEvent={onSandboxEvent}
                  />
                )}
              </ExpressionBlockCard>
            </BlockErrorBoundary>
          </BlockVisibilityReporter>
        )
      })}
    </div>
  )
}

function BlockContent(props: ExpressionBlockProps & { onSandboxEvent?: (blockId: string, message: SandboxTelemetryEvent) => void }) {
  const { block } = props
  if (block.type === 'expression_variants') return <ExpressionVariantsBlock {...props} />
  if (block.type === 'tone_spectrum') return <ToneSpectrumBlock {...props} />
  if (block.type === 'sentence_diff') return <SentenceDiffBlock {...props} />
  if (block.type === 'pattern_diagram') return <PatternDiagramBlock {...props} />
  if (block.type === 'usage_comparison') return <UsageComparisonBlock {...props} />
  if (block.type === 'vocabulary_focus') return <VocabularyFocusBlock {...props} />
  if (block.type === 'grammar_focus') return <GrammarFocusBlock {...props} />
  if (block.type === 'micro_practice') return <MicroPracticeBlock {...props} />
  if (block.type === 'transfer_builder') return <TransferBuilderBlock {...props} />
  if (block.type === 'sandbox_widget') {
    return (
      <Suspense fallback={<ExpressionBlockSkeleton compact />}>
        <SandboxWidget block={block} actions={props.actions} onAction={props.onAction} onEvent={(message) => props.onSandboxEvent?.(block.id, message)} />
      </Suspense>
    )
  }
  return <UnsupportedBlock />
}

function BlockVisibilityReporter({
  block,
  index,
  onVisible,
  children,
}: {
  block: ExpressionUiBlock
  index: number
  onVisible?: (block: ExpressionUiBlock, index: number) => void
  children: ReactNode
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const reportedRef = useRef(false)

  useEffect(() => {
    const node = containerRef.current
    if (!node || reportedRef.current || !onVisible) return
    const report = () => {
      if (reportedRef.current) return
      reportedRef.current = true
      onVisible(block, index)
    }
    if (!('IntersectionObserver' in window)) {
      report()
      return
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        report()
        observer.disconnect()
      }
    }, { threshold: 0.2 })
    observer.observe(node)
    return () => observer.disconnect()
  }, [block, index, onVisible])

  return <div ref={containerRef}>{children}</div>
}

function ExpressionBlockCard({
  block,
  children,
  index,
  isRegenerating,
  canRegenerate,
  onRegenerate,
}: {
  block: ExpressionUiBlock
  children: ReactNode
  index: number
  isRegenerating: boolean
  canRegenerate: boolean
  onRegenerate: () => void
}) {
  const content = (
    <>
      <header className="flex flex-col gap-3 px-4 pb-2 pt-5 sm:flex-row sm:items-start sm:justify-between sm:px-5">
        <div className="min-w-0">
          <BlockTypeBadge type={block.type} />
          <h2 className="mt-2 break-words text-lg font-black text-slate-950 [overflow-wrap:anywhere]">{block.title || `学习模块 ${index + 1}`}</h2>
          {block.description ? <p className="mt-1 text-sm leading-6 text-slate-500">{block.description}</p> : null}
        </div>
        {canRegenerate ? (
          <Button variant="ghost" className="shrink-0 px-3 py-2 text-xs" onClick={onRegenerate} disabled={isRegenerating}>
            {isRegenerating ? <LoaderCircle className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
            {isRegenerating ? '重新生成中' : '换一种'}
          </Button>
        ) : null}
      </header>
      <div className="px-4 pb-5 pt-2 sm:px-5 sm:pb-6">{children}</div>
    </>
  )

  if (block.ui?.collapsible) {
    return (
      <details className="expression-block-enter bg-white" open>
        <summary className="sr-only">{block.title}<ChevronDown className="size-4" /></summary>
        {content}
      </details>
    )
  }
  return <section className={`expression-block-enter bg-white ${block.ui?.emphasis === 'primary' ? 'bg-gradient-to-b from-indigo-50/25 to-white' : ''}`}>{content}</section>
}

export function ExpressionBlockSkeleton({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`animate-pulse space-y-3 ${compact ? 'py-1' : 'rounded-[13px] border border-slate-200 bg-white p-5'}`} aria-label="正在生成学习模块">
      <div className="h-4 w-28 rounded bg-slate-200" />
      <div className="h-6 w-2/3 rounded bg-slate-200" />
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="h-28 rounded-xl bg-slate-100" />
        <div className="h-28 rounded-xl bg-slate-100" />
      </div>
    </div>
  )
}

export function UnsupportedBlock({ message = UNKNOWN_BLOCK_MESSAGE }: { message?: string }) {
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-amber-900">
      <div className="flex items-center gap-2 text-sm font-black"><AlertTriangle className="size-4" />模块已安全跳过</div>
      <p className="mt-1 text-sm leading-6">{message}</p>
    </div>
  )
}

interface BlockErrorBoundaryProps {
  blockId: string
  children: ReactNode
  onRetry: () => void
}

interface BlockErrorBoundaryState { hasError: boolean }

class BlockErrorBoundary extends Component<BlockErrorBoundaryProps, BlockErrorBoundaryState> {
  state: BlockErrorBoundaryState = { hasError: false }

  static getDerivedStateFromError(): BlockErrorBoundaryState { return { hasError: true } }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`Expression block ${this.props.blockId} render failed`, error, info)
  }

  componentDidUpdate(previousProps: BlockErrorBoundaryProps) {
    if (previousProps.blockId !== this.props.blockId && this.state.hasError) this.setState({ hasError: false })
  }

  render() {
    if (!this.state.hasError) return this.props.children
    return (
      <section className="rounded-[13px] border border-amber-200 bg-white p-5 shadow-sm">
        <UnsupportedBlock message="这个模块渲染失败，但不会影响其他学习内容。" />
        <Button variant="secondary" className="mt-3" onClick={() => { this.setState({ hasError: false }); this.props.onRetry() }}><RefreshCw className="size-4" />重新生成模块</Button>
      </section>
    )
  }
}
