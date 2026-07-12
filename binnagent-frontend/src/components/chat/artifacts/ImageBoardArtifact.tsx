import { memo, useCallback, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { Check, ChevronLeft, ChevronRight, Maximize2, MessageSquarePlus, Send, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { IconButton } from '@/components/ui/IconButton'
import type { ImageBoardArtifact as ImageBoardArtifactData, ImageBoardItem } from './chatArtifacts'

interface ImageBoardArtifactProps {
  artifact: ImageBoardArtifactData
  disabled?: boolean
  onAction: (prompt: string) => void
}

interface AnnotationPoint {
  x: number
  y: number
  clientX: number
  clientY: number
}

export const ImageBoardArtifact = memo(function ImageBoardArtifact({
  artifact,
  disabled = false,
  onAction,
}: ImageBoardArtifactProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const [viewerIndex, setViewerIndex] = useState<number | null>(null)

  const selectedItems = useMemo(
    () => artifact.items.filter((item) => selectedIds.has(item.id)),
    [artifact.items, selectedIds],
  )

  const toggleSelected = (itemId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(itemId)) next.delete(itemId)
      else next.add(itemId)
      return next
    })
  }

  const attachSelected = () => {
    if (selectedItems.length === 0) return
    onAction(selectedImagesPrompt(artifact, selectedItems))
  }

  return (
    <section className="mt-3 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <header className="flex items-center justify-between gap-3 border-b border-slate-100 px-3 py-2.5">
        <div className="min-w-0">
          <p className="truncate text-xs font-bold text-slate-800">{artifact.title}</p>
          <p className="text-[11px] text-slate-500">
            {selectedItems.length > 0 ? `已选择 ${selectedItems.length} 张` : '点击选择，打开后可标注局部位置'}
          </p>
        </div>
        <Button
          variant="secondary"
          className="shrink-0 px-2.5 py-1.5 text-xs"
          disabled={disabled || selectedItems.length === 0}
          onClick={attachSelected}
        >
          <MessageSquarePlus className="size-3.5" />
          带入对话
        </Button>
      </header>

      <div className="grid grid-cols-2 gap-1.5 bg-slate-100 p-1.5 sm:grid-cols-3">
        {artifact.items.map((item, index) => {
          const isSelected = selectedIds.has(item.id)
          return (
            <article
              key={item.id}
              className={`group relative overflow-hidden rounded-xl bg-slate-900 ${isSelected ? 'ring-2 ring-indigo-500 ring-offset-1' : ''}`}
            >
              <button
                type="button"
                className="block aspect-[4/3] w-full overflow-hidden text-left"
                aria-label={`打开${item.title}`}
                onClick={() => setViewerIndex(index)}
              >
                <img
                  src={item.imageUrl}
                  alt={item.title}
                  loading="lazy"
                  className="size-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
                />
              </button>
              <button
                type="button"
                className={`absolute left-2 top-2 grid size-7 place-items-center rounded-full border backdrop-blur transition-colors ${
                  isSelected
                    ? 'border-indigo-400 bg-indigo-500 text-white'
                    : 'border-white/50 bg-slate-950/45 text-white hover:bg-slate-950/70'
                }`}
                aria-label={isSelected ? `取消选择${item.title}` : `选择${item.title}`}
                aria-pressed={isSelected}
                onClick={() => toggleSelected(item.id)}
              >
                {isSelected ? <Check className="size-4" /> : <span className="size-2 rounded-full bg-current" />}
              </button>
              <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end justify-between bg-gradient-to-t from-slate-950/80 to-transparent px-2.5 pb-2 pt-8 text-white">
                <span className="truncate text-[11px] font-semibold">{item.title}</span>
                <Maximize2 className="size-3.5 opacity-75" />
              </div>
            </article>
          )
        })}
      </div>

      {viewerIndex !== null
        ? createPortal(
            <ImageBoardViewer
              artifact={artifact}
              initialIndex={viewerIndex}
              disabled={disabled}
              onClose={() => setViewerIndex(null)}
              onAction={onAction}
            />,
            document.body,
          )
        : null}
    </section>
  )
})

function ImageBoardViewer({
  artifact,
  initialIndex,
  disabled,
  onClose,
  onAction,
}: {
  artifact: ImageBoardArtifactData
  initialIndex: number
  disabled: boolean
  onClose: () => void
  onAction: (prompt: string) => void
}) {
  const [index, setIndex] = useState(initialIndex)
  const [annotationPoint, setAnnotationPoint] = useState<AnnotationPoint | null>(null)
  const [note, setNote] = useState('')
  const item = artifact.items[index]

  const navigate = useCallback((delta: number) => {
    setIndex((current) => wrapIndex(current + delta, artifact.items.length))
    setAnnotationPoint(null)
    setNote('')
  }, [artifact.items.length])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
      if (event.key === 'ArrowLeft') navigate(-1)
      if (event.key === 'ArrowRight') navigate(1)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [navigate, onClose])

  const handleImageClick = (event: React.MouseEvent<HTMLImageElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return
    setAnnotationPoint({
      x: clamp01((event.clientX - rect.left) / rect.width),
      y: clamp01((event.clientY - rect.top) / rect.height),
      clientX: event.clientX,
      clientY: event.clientY,
    })
  }

  const submitAnnotation = (event: React.FormEvent) => {
    event.preventDefault()
    const annotation = note.trim()
    if (!annotation || !annotationPoint || disabled) return
    onAction(annotationPrompt(artifact, item, annotation, annotationPoint))
    setAnnotationPoint(null)
    setNote('')
    onClose()
  }

  return (
    <div
      className="fixed inset-0 z-[80] grid place-items-center bg-slate-950/90 p-3 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={`${artifact.title}图片查看器`}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <IconButton
        label="关闭图片查看器"
        onClick={onClose}
        className="absolute right-4 top-4 z-20 border-white/20 bg-slate-950/65 text-white hover:bg-slate-800"
      >
        <X className="size-5" />
      </IconButton>

      {artifact.items.length > 1 ? (
        <>
          <IconButton
            label="上一张图片"
            onClick={() => navigate(-1)}
            className="absolute left-4 top-1/2 z-20 -translate-y-1/2 border-white/20 bg-slate-950/65 text-white hover:bg-slate-800"
          >
            <ChevronLeft className="size-5" />
          </IconButton>
          <IconButton
            label="下一张图片"
            onClick={() => navigate(1)}
            className="absolute right-4 top-1/2 z-20 -translate-y-1/2 border-white/20 bg-slate-950/65 text-white hover:bg-slate-800"
          >
            <ChevronRight className="size-5" />
          </IconButton>
        </>
      ) : null}

      <div className="relative flex max-h-[92vh] max-w-[92vw] flex-col items-center gap-2">
        <img
          src={item.imageUrl}
          alt={item.title}
          className="max-h-[84vh] max-w-full cursor-crosshair select-none rounded-xl object-contain shadow-2xl"
          onClick={handleImageClick}
        />
        <p className="rounded-full bg-slate-950/65 px-3 py-1 text-xs text-white/80">
          {item.title} · 点击画面添加局部标注
        </p>
      </div>

      {annotationPoint ? (
        <form
          className="fixed z-[90] flex w-[min(420px,calc(100vw-32px))] -translate-y-1/2 items-center"
          style={annotationComposerPosition(annotationPoint)}
          onSubmit={submitAnnotation}
          onClick={(event) => event.stopPropagation()}
        >
          <span className="z-10 -mr-2 size-5 shrink-0 rounded-full border-2 border-white bg-indigo-500 shadow" />
          <div className="flex h-12 min-w-0 flex-1 items-center gap-1 rounded-full border border-white/60 bg-white/94 py-1 pl-4 pr-1 shadow-2xl backdrop-blur-xl">
            <input
              autoFocus
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="描述这里要如何修改…"
              className="min-w-0 flex-1 border-0 bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
            />
            <IconButton
              type="button"
              label="取消标注"
              onClick={() => setAnnotationPoint(null)}
              className="border-transparent text-slate-500 hover:bg-slate-100"
            >
              <X className="size-4" />
            </IconButton>
            <IconButton
              type="submit"
              label="将标注带入对话"
              disabled={disabled || note.trim().length === 0}
              className="border-slate-900 bg-slate-900 text-white hover:bg-slate-700"
            >
              <Send className="size-4" />
            </IconButton>
          </div>
        </form>
      ) : null}
    </div>
  )
}

function selectedImagesPrompt(artifact: ImageBoardArtifactData, items: ImageBoardItem[]): string {
  const references = items.map((item, index) => {
    const source = compactSource(item.imageUrl)
    return `${index + 1}. ${item.title}（ID: ${item.id}${source ? `，来源: ${source}` : ''}）`
  })
  return [
    `我从「${artifact.title}」中选择了以下图片，请把它们作为本轮对话的视觉上下文：`,
    ...references,
    '请先说明你对这些选择的理解，再根据当前任务继续；涉及保存或生成新内容时先让我确认。',
  ].join('\n')
}

function annotationPrompt(
  artifact: ImageBoardArtifactData,
  item: ImageBoardItem,
  annotation: string,
  point: AnnotationPoint,
): string {
  const source = compactSource(item.imageUrl)
  return [
    `我在「${artifact.title}」的图片「${item.title}」上添加了局部标注。`,
    `图片 ID: ${item.id}`,
    source ? `图片来源: ${source}` : '',
    `标注位置: x=${point.x.toFixed(4)}, y=${point.y.toFixed(4)}（以图片左上角为原点的归一化坐标）`,
    `修改要求: ${annotation}`,
    '请把这视为针对原图该区域的修改要求；默认保留其余构图、尺寸和风格。',
  ].filter(Boolean).join('\n')
}

function annotationComposerPosition(point: AnnotationPoint): React.CSSProperties {
  const width = Math.min(420, window.innerWidth - 32)
  const left = Math.min(Math.max(point.clientX, 16), window.innerWidth - width - 16)
  const top = Math.min(Math.max(point.clientY, 28), window.innerHeight - 28)
  return { left, top }
}

function compactSource(imageUrl: string): string {
  if (imageUrl.startsWith('data:') || imageUrl.length > 500) return ''
  return imageUrl
}

function clamp01(value: number): number {
  return Math.min(Math.max(value, 0), 1)
}

function wrapIndex(index: number, length: number): number {
  return (index + length) % length
}
