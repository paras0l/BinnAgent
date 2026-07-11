import { GripHorizontal, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent } from 'react'
import { PetCharacterRenderer } from './PetCharacterRenderer'
import { nextTapMotion, pickAutonomousMotion, type PetMotionState } from './petMotionMachine'
import type { PetMessage } from './ToastProvider'
import { clampPetPosition, peekSideForPosition, positionAfterPeek, type PetPeekSide, type PetPositionValue } from './petPosition'

type PetPosition = PetPositionValue
interface PointerDirection { x: number; y: number }

const POSITION_KEY = 'binn-pet-spirit-position-v1'
function readPosition(): PetPosition {
  try {
    const saved = JSON.parse(localStorage.getItem(POSITION_KEY) ?? 'null') as PetPosition | null
    if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y)) {
      return clampPetPosition(saved, { width: window.innerWidth, height: window.innerHeight })
    }
  } catch {
    // Use the default bottom-right position.
  }
  return { x: -24, y: -20 }
}

export function PetSpirit({
  alwaysVisible,
  autonomousMotion,
  idleMotionInterval,
  message,
  onDismiss,
  queuedCount,
  reducedMotion,
  memoryPulse,
}: {
  alwaysVisible: boolean
  autonomousMotion: boolean
  idleMotionInterval: number
  message?: PetMessage
  onDismiss: (id: string) => void
  queuedCount: number
  reducedMotion: boolean
  memoryPulse: number
}) {
  const [position, setPosition] = useState<PetPosition>(readPosition)
  const [interactionMotion, setInteractionMotion] = useState<PetMotionState>('idle')
  const [pointerDirection, setPointerDirection] = useState<PointerDirection>({ x: 0, y: 0 })
  const [momentum, setMomentum] = useState<PointerDirection>({ x: 0, y: 0 })
  const [tapSequence, setTapSequence] = useState(0)
  const [clickFeedback, setClickFeedback] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [peekSide, setPeekSide] = useState<PetPeekSide | null>(() => (
    peekSideForPosition(readPosition(), { width: window.innerWidth, height: window.innerHeight })
  ))
  const [isPageVisible, setIsPageVisible] = useState(() => document.visibilityState !== 'hidden')
  const characterRef = useRef<HTMLDivElement>(null)
  const positionRef = useRef(position)
  const dragRef = useRef<{
    startX: number; startY: number; originX: number; originY: number; moved: boolean
    lastX: number; lastY: number; lastAt: number
    wasPeeking: PetPeekSide | null
  } | null>(null)
  const pointerFrameRef = useRef<number | null>(null)
  const clickTimerRef = useRef<number | null>(null)
  const proximityTimerRef = useRef<number | null>(null)

  useEffect(() => {
    if (reducedMotion) return undefined
    const onPointerMove = (event: PointerEvent) => {
      if (pointerFrameRef.current !== null) return
      pointerFrameRef.current = window.requestAnimationFrame(() => {
        pointerFrameRef.current = null
        const rect = characterRef.current?.getBoundingClientRect()
        if (!rect) return
        const distanceX = event.clientX - (rect.left + rect.width / 2)
        const distanceY = event.clientY - (rect.top + rect.height / 2)
        setPointerDirection({
          x: Math.max(-1, Math.min(1, distanceX / Math.max(180, rect.width * 1.8))),
          y: Math.max(-1, Math.min(1, distanceY / Math.max(150, rect.height * 1.5))),
        })
      })
    }
    window.addEventListener('pointermove', onPointerMove, { passive: true })
    return () => {
      window.removeEventListener('pointermove', onPointerMove)
      if (pointerFrameRef.current !== null) window.cancelAnimationFrame(pointerFrameRef.current)
    }
  }, [reducedMotion])

  useEffect(() => {
    const keepPetOnScreen = () => {
      setPosition((current) => {
        const next = clampPetPosition(current, { width: window.innerWidth, height: window.innerHeight })
        positionRef.current = next
        setPeekSide(peekSideForPosition(next, { width: window.innerWidth, height: window.innerHeight }))
        if (next.x === current.x && next.y === current.y) return current
        try {
          localStorage.setItem(POSITION_KEY, JSON.stringify(next))
        } catch {
          // Position persistence is optional.
        }
        return next
      })
    }
    window.addEventListener('resize', keepPetOnScreen, { passive: true })
    return () => window.removeEventListener('resize', keepPetOnScreen)
  }, [])

  useEffect(() => {
    const syncVisibility = () => setIsPageVisible(document.visibilityState !== 'hidden')
    document.addEventListener('visibilitychange', syncVisibility)
    return () => document.removeEventListener('visibilitychange', syncVisibility)
  }, [])

  useEffect(() => {
    if (message || isDragging || reducedMotion || !autonomousMotion) return undefined
    if (!isPageVisible) return undefined
    const safeInterval = Math.max(3, Math.min(20, idleMotionInterval))
    const idleDelay = safeInterval * 1000 * (0.82 + Math.random() * 0.36)
    let resetTimer: number | undefined
    const idleTimer = window.setTimeout(() => {
      const nextMotion = pickAutonomousMotion(Math.random(), interactionMotion)
      setInteractionMotion(nextMotion)
      const duration = nextMotion === 'sleepy' ? 3400 : nextMotion === 'stretching' ? 2500 : 2200
      resetTimer = window.setTimeout(() => setInteractionMotion('idle'), duration)
    }, idleDelay)
    return () => {
      window.clearTimeout(idleTimer)
      if (resetTimer !== undefined) window.clearTimeout(resetTimer)
    }
  }, [autonomousMotion, idleMotionInterval, interactionMotion, isDragging, isPageVisible, message, reducedMotion])

  useEffect(() => () => {
    if (clickTimerRef.current !== null) window.clearTimeout(clickTimerRef.current)
    if (proximityTimerRef.current !== null) window.clearTimeout(proximityTimerRef.current)
  }, [])

  const reactToTap = useCallback(() => {
    setInteractionMotion((current) => nextTapMotion(current))
    setTapSequence((current) => current + 1)
    setClickFeedback(true)
    if (clickTimerRef.current !== null) window.clearTimeout(clickTimerRef.current)
    clickTimerRef.current = window.setTimeout(() => {
      setClickFeedback(false)
      setInteractionMotion('idle')
    }, 1800)
  }, [])

  const exitPeek = useCallback((side: PetPeekSide) => {
    const next = positionAfterPeek(positionRef.current, { width: window.innerWidth, height: window.innerHeight }, side)
    positionRef.current = next
    setPosition(next)
    setPeekSide(null)
    setInteractionMotion('surprised')
    setClickFeedback(true)
    try {
      localStorage.setItem(POSITION_KEY, JSON.stringify(next))
    } catch {
      // Position persistence is optional.
    }
    if (clickTimerRef.current !== null) window.clearTimeout(clickTimerRef.current)
    clickTimerRef.current = window.setTimeout(() => {
      setClickFeedback(false)
      setInteractionMotion('idle')
    }, 1800)
  }, [])

  const finishDrag = useCallback(() => {
    const drag = dragRef.current
    if (!drag) return
    dragRef.current = null
    setIsDragging(false)
    try {
      localStorage.setItem(POSITION_KEY, JSON.stringify(positionRef.current))
    } catch {
      // Position persistence is optional.
    }
    if (drag.moved) {
      const nextPeekSide = peekSideForPosition(positionRef.current, { width: window.innerWidth, height: window.innerHeight })
      setPeekSide(nextPeekSide)
      if (nextPeekSide) {
        setMomentum({ x: 0, y: 0 })
        setInteractionMotion('idle')
        return
      }
      setInteractionMotion('landing')
      window.setTimeout(() => {
        setMomentum({ x: 0, y: 0 })
        setInteractionMotion('idle')
      }, 650)
      return
    }
    if (drag.wasPeeking) {
      exitPeek(drag.wasPeeking)
      return
    }
    reactToTap()
  }, [exitPeek, reactToTap])

  useEffect(() => {
    if (!isDragging) return undefined
    const releaseOutsideCharacter = () => finishDrag()
    window.addEventListener('pointerup', releaseOutsideCharacter)
    window.addEventListener('pointercancel', releaseOutsideCharacter)
    return () => {
      window.removeEventListener('pointerup', releaseOutsideCharacter)
      window.removeEventListener('pointercancel', releaseOutsideCharacter)
    }
  }, [finishDrag, isDragging])

  useEffect(() => {
    if (!message || !peekSide) return
    const next = positionAfterPeek(positionRef.current, { width: window.innerWidth, height: window.innerHeight }, peekSide)
    positionRef.current = next
    setPosition(next)
    setPeekSide(null)
    try {
      localStorage.setItem(POSITION_KEY, JSON.stringify(next))
    } catch {
      // Position persistence is optional.
    }
  }, [message, peekSide])

  if (!alwaysVisible && !message) return null

  const activeMotion: PetMotionState = isDragging ? 'dragging' : message?.motion ?? (peekSide ? 'peeking' : interactionMotion)

  const startDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    dragRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      originX: position.x,
      originY: position.y,
      moved: false,
      lastX: event.clientX,
      lastY: event.clientY,
      lastAt: event.timeStamp,
      wasPeeking: peekSide,
    }
    setIsDragging(true)
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const moveDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current
    if (!drag) return
    const dx = event.clientX - drag.startX
    const dy = event.clientY - drag.startY
    const elapsed = Math.max(8, event.timeStamp - drag.lastAt)
    const velocityX = (event.clientX - drag.lastX) / elapsed
    const velocityY = (event.clientY - drag.lastY) / elapsed
    drag.lastX = event.clientX
    drag.lastY = event.clientY
    drag.lastAt = event.timeStamp
    drag.moved ||= Math.abs(dx) + Math.abs(dy) > 5
    if (drag.moved && peekSide) setPeekSide(null)
    const nextPosition = clampPetPosition(
      { x: drag.originX + dx, y: drag.originY + dy },
      { width: window.innerWidth, height: window.innerHeight },
    )
    positionRef.current = nextPosition
    setPosition(nextPosition)
    setMomentum({
      x: Math.max(-1, Math.min(1, velocityX * 0.75)),
      y: Math.max(-1, Math.min(1, velocityY * 0.75)),
    })
  }

  const endDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    finishDrag()
  }

  const noticePointer = () => {
    if (message || isDragging || reducedMotion) return
    if (proximityTimerRef.current !== null) window.clearTimeout(proximityTimerRef.current)
    setInteractionMotion('surprised')
  }

  const settleAfterPointer = () => {
    if (message || isDragging) return
    if (proximityTimerRef.current !== null) window.clearTimeout(proximityTimerRef.current)
    proximityTimerRef.current = window.setTimeout(() => setInteractionMotion('idle'), 420)
  }

  const handleCharacterKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    if (peekSide) {
      exitPeek(peekSide)
      return
    }
    reactToTap()
  }

  return (
    <aside
      className="pet-spirit fixed bottom-0 right-0 z-[100] flex w-[min(22rem,calc(100vw-1rem))] items-end justify-end"
      data-motion={activeMotion}
      data-variant={message?.variant ?? 'idle'}
      data-reduced-motion={reducedMotion}
      data-peek-side={peekSide ?? undefined}
      style={{ transform: `translate3d(${position.x}px, ${position.y}px, 0)` }}
      aria-live="polite"
      aria-label="宠物精灵通知"
    >
      <div className="flex min-w-0 flex-1 flex-col items-end pb-20 sm:pb-24">
        {message ? (
          <div className="pet-spirit__bubble w-full max-w-[18rem]" data-variant={message.variant}>
            <div className="flex items-start gap-2">
              <div className="min-w-0 flex-1">
                <p className="text-xs font-black uppercase tracking-[0.12em] opacity-70">{message.title ?? '小冰来报'}</p>
                <p className="mt-1 text-sm font-semibold leading-5">{message.message}</p>
                {queuedCount ? <p className="mt-1 text-[11px] opacity-60">还有 {queuedCount} 条消息</p> : null}
              </div>
              <button type="button" className="rounded-full p-1 opacity-60 transition hover:bg-black/5 hover:opacity-100" onClick={() => onDismiss(message.id)} aria-label="关闭消息">
                <X className="size-4" />
              </button>
            </div>
          </div>
        ) : clickFeedback ? (
          <div className="pet-spirit__bubble max-w-48" data-variant="success">{interactionMotion === 'surprised' ? '找到我啦，我们继续一起走。' : '我在这儿，随时陪你一起看看！'}</div>
        ) : null}
      </div>
      <div
        ref={characterRef}
        className="pet-spirit__character group relative -ml-12 w-32 shrink-0 cursor-grab touch-none select-none rounded-full outline-none active:cursor-grabbing focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 sm:w-36"
        role="button"
        tabIndex={0}
        aria-label="小冰宠物精灵，按回车或空格互动，也可以拖动调整位置"
        onPointerDown={startDrag}
        onPointerMove={moveDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onPointerEnter={noticePointer}
        onPointerLeave={settleAfterPointer}
        onKeyDown={handleCharacterKeyDown}
        title="拖动我换位置，点我打招呼"
      >
        <span className="absolute -top-2 left-1/2 z-10 -translate-x-1/2 rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-bold text-slate-500 opacity-0 shadow-sm transition group-hover:opacity-100">
          <GripHorizontal className="size-3" />
        </span>
        <PetCharacterRenderer
          motion={activeMotion}
          pointerX={message ? -0.85 : pointerDirection.x}
          pointerY={message ? -0.35 : pointerDirection.y}
          momentumX={momentum.x}
          momentumY={momentum.y}
          reducedMotion={reducedMotion}
          tapSequence={tapSequence}
          memoryPulse={memoryPulse}
          peekSide={peekSide}
        />
      </div>
    </aside>
  )
}
