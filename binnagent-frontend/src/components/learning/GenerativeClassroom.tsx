import {
  ArrowLeft, ArrowRight, BookOpenCheck, BookOpenText, BrainCircuit, Braces, Check, ChevronRight, CircleCheck, CircleX, Flag,
  Cloud, CloudOff, Headphones, Lightbulb, LoaderCircle, LockKeyhole, PanelLeftClose, PanelLeftOpen, Pause, Play, ScanLine, Sparkles, Target,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { IconButton } from '@/components/ui/IconButton'
import { StatusBanner } from '@/components/ui/StatusBanner'
import {
  getPhaseGate,
  isPhaseAccessible,
  NEXT_ACTION_LABELS,
  type ClassroomPhaseKind,
  type VocabularyConfidence,
} from './classroomModel'

export interface ClassroomPlan {
  schema_version: string
  classroom_id: string
  generation_mode: 'llm_generated' | 'curated_fallback'
  source: { id: string; title: string; edition: string }
  unit: { id: string; title: string; subtitle: string; ordinal: number }
  hero: { eyebrow: string; title: string; mission: string; coach_message: string }
  phases: Array<{ id: string; kind: ClassroomPhaseKind; title: string; minutes: number; icon: string }>
  language_cards: Array<{ id: string; front: string; back: string; accent: 'violet' | 'cyan' | 'amber' | 'rose' }>
  focus: { grammar: string; question: string }
  audio: { track: string; timeline_available: boolean } | null
  vocabulary?: {
    core_count: number
    primary_review_count: number
    core: Array<{ term: string; meaning_zh: string; phonetic?: string | null; part_of_speech?: string | null }>
    primary_review: Array<{ term: string; meaning_zh: string }>
  }
  teaching?: Record<string, string[]>
  grammar_lab?: {
    title: string
    can_do: string
    rule: string
    forms: string[]
    examples: Array<{ en: string; zh: string }>
    common_error: string
    checks: Array<{ id: string; prompt: string; options: string[]; answer: string; explanation: string }>
    transfer_prompt: string
  } | null
  textbook_tasks?: Array<{
    id: string
    title: string
    instruction: string
    asset: string
    printed_page: number
    pdf_page: number
    response_type: 'text'
  }>
  completion: { xp: number; memory_message: string }
  resume: {
    current_phase_id: string
    completed_phase_ids: string[]
    flipped_card_ids: string[]
    listened_cue_ids: string[]
    textbook_task_answers?: Record<string, string>
    grammar_answers?: Record<string, string>
    grammar_transfer?: string
    vocabulary_confidence?: Record<string, VocabularyConfidence>
    continuous_audio_played?: boolean
    status: 'in_progress' | 'learned'
    updated_at: string | null
  } | null
}

interface TimelineCue {
  id: string
  start_ms: number
  end_ms: number
  section: string
  activity: string
  type: string
  text_en: string
  text_zh?: string | null
  skip_intro?: boolean
}

interface LessonTask {
  episode_id?: string | null
  status: string
  answer_required: boolean
  verification_status?: string | null
  feedback?: unknown
}

interface TextbookCoachFeedback {
  diagnosis: string
  evidence: string[]
  hint: string
  next_action: 'relisten' | 'review_vocabulary' | 'review_pattern' | 'continue'
  generation_mode: 'llm_generated' | 'curated_fallback'
}

const ACCENTS = {
  violet: 'border-violet-200 bg-violet-50',
  cyan: 'border-cyan-200 bg-cyan-50',
  amber: 'border-amber-200 bg-amber-50',
  rose: 'border-rose-200 bg-rose-50',
}

type SaveStatus = 'dirty' | 'saving' | 'saved' | 'offline'

function isClassroomPhaseKind(value: string): value is ClassroomPhaseKind {
  return ['briefing', 'cards', 'grammar', 'audio', 'textbook', 'challenge', 'reflection'].includes(value)
}

export function GenerativeClassroom({
  learnerId,
  plan,
  lesson,
  prompt,
  options,
  answer,
  isSubmitting,
  feedback,
  boosterCount,
  onAnswerChange,
  onSubmit,
  onPrepareChallenge,
  isPreparingChallenge = false,
  onOpenBoosters,
  onClose,
}: {
  learnerId: string
  plan: ClassroomPlan
  lesson: LessonTask | null
  prompt: string
  options: string[]
  answer: string
  isSubmitting: boolean
  feedback: string | null
  boosterCount: number
  onAnswerChange: (value: string) => void
  onSubmit: (value: string) => void
  onPrepareChallenge?: () => void
  isPreparingChallenge?: boolean
  onOpenBoosters: () => void
  onClose: () => void
}) {
  const initialPhaseIndex = Math.max(0, plan.phases.findIndex((item) => item.id === plan.resume?.current_phase_id))
  const [phaseIndex, setPhaseIndex] = useState(initialPhaseIndex)
  const [completedPhaseIds, setCompletedPhaseIds] = useState<Set<string>>(
    () => new Set(plan.resume?.completed_phase_ids ?? []),
  )
  const [flipped, setFlipped] = useState<Set<string>>(() => new Set(plan.resume?.flipped_card_ids ?? []))
  const [listenedCueIds, setListenedCueIds] = useState<Set<string>>(
    () => new Set(plan.resume?.listened_cue_ids ?? []),
  )
  const [textbookTaskAnswers, setTextbookTaskAnswers] = useState<Record<string, string>>(
    () => plan.resume?.textbook_task_answers ?? {},
  )
  const [grammarAnswers, setGrammarAnswers] = useState<Record<string, string>>(
    () => plan.resume?.grammar_answers ?? {},
  )
  const [grammarTransfer, setGrammarTransfer] = useState(() => plan.resume?.grammar_transfer ?? '')
  const [vocabularyConfidence, setVocabularyConfidence] = useState<Record<string, VocabularyConfidence>>(
    () => plan.resume?.vocabulary_confidence ?? {},
  )
  const [continuousAudioPlayed, setContinuousAudioPlayed] = useState(
    () => plan.resume?.continuous_audio_played ?? false,
  )
  const [activeTextbookTaskIndex, setActiveTextbookTaskIndex] = useState(0)
  const [textbookCoachFeedback, setTextbookCoachFeedback] = useState<TextbookCoachFeedback | null>(null)
  const [isCoachingTextbookTask, setIsCoachingTextbookTask] = useState(false)
  const [timeline, setTimeline] = useState<TimelineCue[]>([])
  const [activeGroup, setActiveGroup] = useState('')
  const [activeCueId, setActiveCueId] = useState<string | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [audioError, setAudioError] = useState<string | null>(null)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>(plan.resume?.updated_at ? 'saved' : 'dirty')
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(
    () => plan.resume?.updated_at ? new Date(plan.resume.updated_at) : null,
  )
  const [showExitPrompt, setShowExitPrompt] = useState(false)
  const [exitAfterSave, setExitAfterSave] = useState(false)
  const [isRouteCollapsed, setIsRouteCollapsed] = useState(false)
  const audioRef = useRef<HTMLAudioElement>(null)
  const phase = plan.phases[phaseIndex]
  const teachingGoals = (plan.teaching?.['学习目标'] ?? plan.teaching?.['单元学习目标'] ?? [])
    .filter((item) => !item.endsWith('能够：'))
    .slice(0, 3)
  const isCompleted = lesson?.status === 'completed' || Boolean(lesson?.verification_status)
  const isChallengeReady = Boolean(lesson?.episode_id && lesson.answer_required)
  const completed = isCompleted && phase.kind === 'reflection'
  const progress = Math.min(100, Math.round((Math.max(completedPhaseIds.size, phaseIndex) + (completed ? 1 : 0)) / plan.phases.length * 100))
  const grammarChecks = plan.grammar_lab?.checks ?? []
  const grammarCorrectCount = grammarChecks.filter((check) => grammarAnswers[check.id] === check.answer).length
  const grammarAnsweredCount = grammarChecks.filter((check) => Boolean(grammarAnswers[check.id])).length
  const classifiedVocabularyCount = Object.values(vocabularyConfidence).filter(Boolean).length
  const vocabularyRequired = Math.min(4, Math.max(1, plan.language_cards.length))
  const textbookAnswerCount = Object.values(textbookTaskAnswers).filter((value) => value.trim()).length
  const phaseKind = isClassroomPhaseKind(phase.kind) ? phase.kind : null
  const phaseGate = phaseKind ? getPhaseGate(phaseKind, {
    vocabularyClassified: classifiedVocabularyCount,
    vocabularyRequired,
    grammarAnswered: grammarAnsweredCount,
    grammarRequired: grammarChecks.length,
    grammarTransferLength: grammarTransfer.trim().length,
    continuousAudioPlayed,
    listenedCueCount: listenedCueIds.size,
    textbookAnswerCount,
    challengeCompleted: isCompleted,
  }) : { canContinue: false, evidence: '阶段无法识别', requirement: '返回学习中心后重新进入课堂' }

  const requestClose = useCallback(() => {
    if (saveStatus === 'dirty' || saveStatus === 'saving' || saveStatus === 'offline' || isCoachingTextbookTask) {
      setShowExitPrompt(true)
      return
    }
    onClose()
  }, [isCoachingTextbookTask, onClose, saveStatus])

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') requestClose()
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [requestClose])

  useEffect(() => {
    if (!plan.audio?.timeline_available) return
    const controller = new AbortController()
    fetch(`/api/learners/${learnerId}/daily-lessons/classroom/timeline/${encodeURIComponent(plan.audio.track)}`, { signal: controller.signal })
      .then((response) => response.ok ? response.json() : null)
      .then((payload) => setTimeline(Array.isArray(payload?.cues) ? payload.cues.filter((cue: TimelineCue) => !cue.skip_intro) : []))
      .catch(() => undefined)
    return () => controller.abort()
  }, [learnerId, plan.audio])

  useEffect(() => {
    const controller = new AbortController()
    const dirtyTimer = window.setTimeout(() => setSaveStatus('dirty'), 0)
    const timer = window.setTimeout(() => {
      setSaveStatus('saving')
      fetch(`/api/learners/${learnerId}/daily-lessons/classroom/progress`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          curriculum_node_id: plan.unit.id,
          classroom_id: plan.classroom_id,
          current_phase_id: phase.id,
          completed_phase_ids: [...completedPhaseIds],
          flipped_card_ids: [...flipped],
          listened_cue_ids: [...listenedCueIds],
          textbook_task_answers: textbookTaskAnswers,
          grammar_answers: grammarAnswers,
          grammar_transfer: grammarTransfer,
          vocabulary_confidence: vocabularyConfidence,
          continuous_audio_played: continuousAudioPlayed,
          completed,
        }),
      })
        .then((response) => {
          if (!response.ok) throw new Error('progress save failed')
          setSaveStatus('saved')
          setLastSavedAt(new Date())
        })
        .catch((error: unknown) => {
          if (!(error instanceof DOMException && error.name === 'AbortError')) setSaveStatus('offline')
        })
    }, 450)
    return () => {
      window.clearTimeout(dirtyTimer)
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [completed, completedPhaseIds, continuousAudioPlayed, flipped, grammarAnswers, grammarTransfer, learnerId, listenedCueIds, phase.id, plan.classroom_id, plan.unit.id, textbookTaskAnswers, vocabularyConfidence])

  useEffect(() => {
    if (exitAfterSave && saveStatus === 'saved') onClose()
  }, [exitAfterSave, onClose, saveStatus])

  useEffect(() => {
    const audio = audioRef.current
    if (!audio || !activeCueId) return
    const cue = timeline.find((item) => item.id === activeCueId)
    if (!cue) return
    const stopAtCueEnd = () => {
      if (audio.currentTime * 1000 >= cue.end_ms) {
        audio.pause()
        setIsPlaying(false)
      }
    }
    audio.addEventListener('timeupdate', stopAtCueEnd)
    return () => audio.removeEventListener('timeupdate', stopAtCueEnd)
  }, [activeCueId, timeline])

  const groupedCues = useMemo(() => {
    const groups = new Map<string, TimelineCue[]>()
    for (const cue of timeline) {
      const key = `${cue.section} · ${cue.activity}`
      groups.set(key, [...(groups.get(key) ?? []), cue])
    }
    return [...groups.entries()]
  }, [timeline])

  const selectedCueGroup = groupedCues.find(([group]) => group === activeGroup) ?? groupedCues[0]

  const playCue = (cue: TimelineCue) => {
    const audio = audioRef.current
    if (!audio) return
    if (activeCueId === cue.id && isPlaying) {
      audio.pause()
      setIsPlaying(false)
      return
    }
    audio.currentTime = cue.start_ms / 1000
    setActiveCueId(cue.id)
    setListenedCueIds((current) => new Set(current).add(cue.id))
    setAudioError(null)
    void audio.play().then(() => setIsPlaying(true)).catch(() => {
      setIsPlaying(false)
      setAudioError('浏览器阻止了自动播放，请再点一次播放按钮。')
    })
  }

  const playContinuousAudio = () => {
    const audio = audioRef.current
    if (!audio) return
    setActiveCueId(null)
    setAudioError(null)
    if (isPlaying) {
      audio.pause()
      return
    }
    void audio.play().then(() => {
      setContinuousAudioPlayed(true)
      setIsPlaying(true)
    }).catch(() => setAudioError('浏览器阻止了自动播放，请再点一次播放按钮。'))
  }

  const navigateToPhase = (nextIndex: number) => {
    const clampedIndex = Math.max(0, Math.min(nextIndex, plan.phases.length - 1))
    const target = plan.phases[clampedIndex]
    if (!target || !isPhaseAccessible(clampedIndex, phaseIndex, phaseGate.canContinue)) return
    setPhaseIndex(clampedIndex)
  }

  const completeAndContinue = () => {
    if (!phaseGate.canContinue || phaseIndex >= plan.phases.length - 1) return
    setCompletedPhaseIds((current) => new Set(current).add(phase.id))
    setPhaseIndex((current) => Math.min(current + 1, plan.phases.length - 1))
  }

  const goPrevious = () => navigateToPhase(phaseIndex - 1)

  const followCoachAction = (action: TextbookCoachFeedback['next_action']) => {
    const kindToIndex: Partial<Record<TextbookCoachFeedback['next_action'], number>> = {
      relisten: plan.phases.findIndex((item) => item.kind === 'audio'),
      review_vocabulary: plan.phases.findIndex((item) => item.kind === 'cards'),
      review_pattern: plan.phases.findIndex((item) => item.kind === 'grammar'),
    }
    const targetIndex = kindToIndex[action]
    if (typeof targetIndex === 'number' && targetIndex >= 0) {
      navigateToPhase(targetIndex)
      return
    }
    if (activeTextbookTaskIndex < (plan.textbook_tasks?.length ?? 0) - 1) {
      setTextbookCoachFeedback(null)
      setActiveTextbookTaskIndex((current) => current + 1)
    } else {
      completeAndContinue()
    }
  }

  const requestTextbookCoaching = async (taskId: string, taskAnswer: string) => {
    setIsCoachingTextbookTask(true)
    setTextbookCoachFeedback(null)
    try {
      const response = await fetch(`/api/learners/${learnerId}/daily-lessons/classroom/coach`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          curriculum_node_id: plan.unit.id,
          task_id: taskId,
          answer: taskAnswer,
        }),
      })
      if (!response.ok) throw new Error('AI 教练暂时无法分析这份答案。')
      setTextbookCoachFeedback(await response.json() as TextbookCoachFeedback)
    } catch (error) {
      setTextbookCoachFeedback({
        diagnosis: error instanceof Error ? error.message : 'AI 教练暂时无法分析这份答案。',
        evidence: ['你的答案已经保存在课堂进度中。'],
        hint: '先按题号检查是否漏题，再继续下一页。',
        next_action: 'continue',
        generation_mode: 'curated_fallback',
      })
    } finally {
      setIsCoachingTextbookTask(false)
    }
  }

  return (
    <div role="dialog" aria-modal="true" aria-label={`${plan.unit.title} 教材课堂`} className="fixed inset-0 z-[120] overflow-hidden bg-[#ece9e1] text-slate-950">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(115deg,rgba(255,255,255,0.72),transparent_44%),radial-gradient(circle_at_92%_6%,rgba(99,102,241,0.09),transparent_28%)]" />
      <div className="relative flex h-full flex-col">
        <header className="relative flex min-h-18 shrink-0 items-center gap-4 border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur-xl sm:px-7">
          <IconButton label="退出课堂" onClick={requestClose} className="border-slate-200 bg-white text-slate-700 hover:bg-slate-100">
            <ArrowLeft className="size-4" />
          </IconButton>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-[10px] font-black tracking-[0.18em] text-indigo-600">
              <BookOpenText className="size-3" />
              今日教材课
            </div>
            <p className="truncate text-sm font-black text-slate-950 sm:text-base">{plan.unit.title} · {plan.unit.subtitle}</p>
          </div>
          <div className="hidden w-56 sm:block">
            <div className="mb-1.5 flex justify-between text-[11px] font-bold text-slate-500"><span>今天的进度</span><span>{phaseIndex + 1}/{plan.phases.length}</span></div>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-indigo-600 transition-all" style={{ width: `${progress}%` }} /></div>
          </div>
          <div className="hidden items-center gap-1.5 text-[11px] font-bold text-slate-500 md:flex" aria-live="polite">
            {saveStatus === 'offline' ? <CloudOff className="size-3.5 text-amber-600" /> : <Cloud className="size-3.5 text-emerald-600" />}
            {saveStatus === 'saving' || saveStatus === 'dirty'
              ? '正在保存…'
              : saveStatus === 'offline'
                ? '保存失败，将自动重试'
                : `已保存${lastSavedAt ? ` ${lastSavedAt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}` : ''}`}
          </div>
          {showExitPrompt ? <div className="absolute right-4 top-[calc(100%+8px)] z-20 w-[min(22rem,calc(100vw-2rem))] rounded-2xl border border-amber-200 bg-white p-4 shadow-xl"><p className="text-sm font-black text-slate-950">内容还在保存，要退出吗？</p><p className="mt-1 text-xs font-semibold leading-5 text-slate-500">退出不会结束今日课程，下次会回到当前步骤。</p><div className="mt-3 flex justify-end gap-2"><Button variant="secondary" onClick={() => setShowExitPrompt(false)}>继续学习</Button><Button onClick={() => { if (saveStatus === 'offline') onClose(); else setExitAfterSave(true); setShowExitPrompt(false) }}>{saveStatus === 'offline' ? '仍然退出' : '保存后退出'}</Button></div></div> : null}
        </header>

        <div className={`grid min-h-0 flex-1 transition-[grid-template-columns] duration-200 ${isRouteCollapsed ? 'lg:grid-cols-[76px_minmax(0,1fr)]' : 'lg:grid-cols-[280px_minmax(0,1fr)]'}`}>
          <aside className={`hidden min-h-0 overflow-y-auto border-r border-slate-200 bg-[#f7f5ef] lg:block ${isRouteCollapsed ? 'px-3 py-4' : 'p-5'}`}>
            <div className={`mb-4 flex items-center ${isRouteCollapsed ? 'justify-center' : 'justify-between gap-3'}`}>
              {!isRouteCollapsed ? <div><p className="text-xs font-black tracking-[0.18em] text-indigo-600">今天的课</p><p className="mt-1 text-xs font-semibold leading-5 text-slate-500">一次只完成当前任务，达标后再进入下一步。</p></div> : null}
              <IconButton label={isRouteCollapsed ? '展开课堂路径' : '收起课堂路径'} onClick={() => setIsRouteCollapsed((current) => !current)} className="shrink-0 border-slate-200 bg-white text-slate-600 hover:text-indigo-700">
                {isRouteCollapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
              </IconButton>
            </div>
            <ol className="space-y-2">
              {plan.phases.map((item, index) => {
                const accessible = isPhaseAccessible(index, phaseIndex, phaseGate.canContinue)
                return <li key={item.id}>
                  <button type="button" aria-label={isRouteCollapsed ? `${item.title}，约 ${item.minutes} 分钟` : undefined} title={isRouteCollapsed ? item.title : undefined} disabled={!accessible} onClick={() => navigateToPhase(index)} className={`group flex w-full items-center rounded-2xl border py-3 text-left transition ${isRouteCollapsed ? 'justify-center px-2' : 'gap-3 px-3'} ${index === phaseIndex ? 'border-indigo-200 bg-white shadow-sm' : accessible ? 'border-transparent hover:bg-white' : 'cursor-not-allowed border-transparent opacity-45'}`}>
                    <span className={`flex size-9 shrink-0 items-center justify-center rounded-xl ${completedPhaseIds.has(item.id) ? 'bg-emerald-100 text-emerald-700' : index === phaseIndex ? 'bg-indigo-600 text-white shadow-md shadow-indigo-200' : 'bg-slate-200 text-slate-500'}`}>
                      {completedPhaseIds.has(item.id) || (isCompleted && index === plan.phases.length - 1) ? <Check className="size-4" /> : !accessible ? <LockKeyhole className="size-3.5" /> : <span className="text-xs font-black">{index + 1}</span>}
                    </span>
                    <span className={isRouteCollapsed ? 'sr-only' : 'min-w-0'}><span className={`block truncate text-sm font-black ${index === phaseIndex ? 'text-slate-950' : 'text-slate-600'}`}>{item.title}</span><span className="text-[11px] text-slate-400">约 {item.minutes} 分钟</span></span>
                  </button>
                </li>
              } )}
            </ol>
          </aside>

          <main className="min-h-0 scroll-pb-24 overflow-y-auto px-4 pb-28 pt-6 sm:px-8 lg:px-12 lg:pb-20 lg:pt-9">
            <div className="mx-auto max-w-5xl">
              <div className="mb-5 flex flex-wrap items-center gap-3 text-sm font-black text-indigo-700">
                <span className="flex size-9 items-center justify-center rounded-xl bg-indigo-100">{phaseIndex + 1}</span>
                {phase.title}<span className="text-slate-400">· 约 {phase.minutes} 分钟</span>
                <span className={`ml-auto rounded-full px-3 py-1 text-xs ${phaseGate.canContinue ? 'bg-emerald-100 text-emerald-700' : 'bg-white text-slate-600 shadow-sm'}`}>{phaseGate.evidence}</span>
              </div>

              {phase.kind === 'briefing' ? (
                <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white p-6 shadow-[0_22px_60px_rgba(51,65,85,0.10)] sm:p-10">
                  <p className="text-xs font-black tracking-[0.18em] text-indigo-600">今天先做到这一件事</p>
                  <h1 className="mt-3 max-w-3xl text-3xl font-black tracking-tight text-slate-950 sm:text-5xl">{plan.hero.title}</h1>
                  <div className="mt-8 grid gap-4 sm:grid-cols-3">
                    <div className="rounded-3xl bg-indigo-600 p-6 text-white"><p className="text-xs font-black tracking-wider text-indigo-100">今天的目标</p><p className="mt-3 text-lg font-black leading-8">{plan.hero.mission}</p></div>
                    <div className="rounded-3xl border border-slate-200 bg-[#faf9f6] p-6"><p className="flex items-center gap-2 text-xs font-black text-indigo-700"><Target className="size-4" /> 今天会练</p><p className="mt-3 text-base font-black leading-7 text-slate-900">{plan.focus.question}</p></div>
                    <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-6"><p className="flex items-center gap-2 text-xs font-black text-emerald-700"><Check className="size-4" /> 完成标准</p><p className="mt-3 text-base font-black leading-7 text-slate-900">完成词汇判断、语法迁移、原声听辨和一页教材作答。</p></div>
                  </div>
                  {plan.grammar_lab ? <div className="mt-5 flex items-start gap-3 rounded-3xl border border-indigo-100 bg-indigo-50 p-5"><Braces className="mt-0.5 size-5 shrink-0 text-indigo-600" /><div><p className="text-xs font-black text-indigo-600">今天要真正掌握的句型</p><p className="mt-1 text-base font-black text-slate-950">{plan.grammar_lab.title}</p><p className="mt-1 text-sm font-semibold leading-6 text-slate-600">{plan.grammar_lab.can_do}</p></div></div> : null}
                  {teachingGoals.length ? <div className="mt-5 rounded-3xl border border-slate-200 bg-[#faf9f6] p-5"><p className="text-xs font-black text-slate-500">学完后你会留下这些证据</p><ul className="mt-3 grid gap-2 text-sm font-bold leading-6 text-slate-700 sm:grid-cols-3">{teachingGoals.map((goal) => <li key={goal} className="rounded-2xl bg-white p-3"><Check className="mr-2 inline size-4 text-emerald-600" />{goal}</li>)}</ul></div> : null}
                  <Button onClick={completeAndContinue} className="mt-8">开始第一个任务 <ArrowRight className="size-4" /></Button>
                </section>
              ) : null}

              {phase.kind === 'cards' ? (
                <section>
                  <div className="mb-6">
                    <p className="text-xs font-black tracking-[0.18em] text-indigo-600">词汇诊断 · 先判断，再学习</p>
                    <h2 className="mt-2 text-2xl font-black sm:text-3xl">先区分“要学会”和“要唤醒”</h2>
                    <p className="mt-2 text-sm font-semibold text-slate-600">翻面只是查看释义。每个词都要明确标成“会、模糊或不会”，系统才知道后面该怎么教。</p>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    {plan.language_cards.map((card) => {
                      const isFlipped = flipped.has(card.id)
                      const confidence = vocabularyConfidence[card.id]
                      return <article key={card.id} className={`rounded-3xl border p-4 shadow-sm ${ACCENTS[card.accent]}`}>
                        <button type="button" aria-pressed={isFlipped} onClick={() => setFlipped((current) => { const next = new Set(current); if (next.has(card.id)) next.delete(card.id); else next.add(card.id); return next })} className="min-h-28 w-full rounded-2xl bg-white/75 p-4 text-left text-slate-950 transition hover:bg-white">
                          <ScanLine className="size-5 text-indigo-500" /><p className="mt-5 text-xl font-black">{isFlipped ? card.back : card.front}</p><p className="mt-2 text-xs font-bold text-slate-500">{isFlipped ? '点击返回单词' : '点击查看释义'}</p>
                        </button>
                        <div className="mt-3 grid grid-cols-3 gap-1.5" aria-label={`${card.front} 掌握情况`}>
                          {([['known', '会'], ['fuzzy', '模糊'], ['unknown', '不会']] as const).map(([value, label]) => <button key={value} type="button" aria-pressed={confidence === value} onClick={() => setVocabularyConfidence((current) => ({ ...current, [card.id]: value }))} className={`rounded-xl px-2 py-2 text-xs font-black transition ${confidence === value ? value === 'known' ? 'bg-emerald-600 text-white' : value === 'fuzzy' ? 'bg-amber-500 text-white' : 'bg-rose-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-100'}`}>{label}</button>)}
                        </div>
                      </article>
                    })}
                  </div>
                  {plan.vocabulary?.primary_review.length ? <div className="mt-5 rounded-3xl border border-emerald-200 bg-emerald-50 p-5"><p className="text-xs font-black text-emerald-700">小学词汇快速唤醒</p><div className="mt-3 flex flex-wrap gap-2">{plan.vocabulary.primary_review.slice(0, 18).map((item) => <button key={item.term} type="button" className="rounded-full border border-emerald-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700" title={`${item.term}：${item.meaning_zh}`}>{item.term}<span className="ml-1 text-slate-400">· {item.meaning_zh}</span></button>)}</div><p className="mt-3 text-xs text-slate-500">这些是快速复现词，不会冒充新词计入本课负担。</p></div> : null}
                  <div className="mt-7 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm font-black text-slate-800">{phaseGate.evidence}</p><p className="mt-1 text-xs font-semibold text-slate-500">{phaseGate.requirement}</p></div><Button disabled={!phaseGate.canContinue} onClick={completeAndContinue}>完成词汇诊断 <ChevronRight className="size-4" /></Button></div>
                </section>
              ) : null}

              {phase.kind === 'grammar' && plan.grammar_lab ? (
                <GrammarLabPanel
                  lab={plan.grammar_lab}
                  answers={grammarAnswers}
                  transfer={grammarTransfer}
                  onAnswer={(checkId, value) => setGrammarAnswers((current) => ({ ...current, [checkId]: value }))}
                  onTransfer={setGrammarTransfer}
                  onContinue={completeAndContinue}
                />
              ) : null}

              {phase.kind === 'audio' ? (
                <section>
                  <audio
                    ref={audioRef}
                    preload="metadata"
                    src={plan.audio ? `/api/learners/${learnerId}/daily-lessons/classroom/audio/${encodeURIComponent(plan.audio.track)}` : undefined}
                    onPause={() => setIsPlaying(false)}
                    onPlay={() => setIsPlaying(true)}
                    onEnded={() => setIsPlaying(false)}
                    onError={() => setAudioError('教材音频暂时无法加载，请稍后重试。')}
                  />
                  <div className="rounded-[2rem] border border-indigo-100 bg-white p-6 shadow-sm sm:p-8">
                    <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between"><div><p className="flex items-center gap-2 text-xs font-black tracking-wider text-indigo-600"><Headphones className="size-4" /> 教材原声 · 先整段听，再定位</p><h2 className="mt-3 text-2xl font-black text-slate-950">先听懂关键信息，再回到教材做题</h2><p className="mt-2 text-sm font-semibold text-slate-600">先不看文本完整听一遍；遇到没听清的地方，再用句子按钮定位核对。</p></div><button type="button" onClick={playContinuousAudio} className="flex size-20 shrink-0 items-center justify-center rounded-full border border-indigo-200 bg-indigo-600 text-white shadow-lg shadow-indigo-200 transition hover:scale-105 hover:bg-indigo-700" aria-label={isPlaying && !activeCueId ? '暂停教材原声' : '连续播放教材原声'}>{isPlaying && !activeCueId ? <Pause className="size-8" /> : <Play className="ml-1 size-8" />}</button></div>
                  </div>
                  {audioError ? <div className="mt-4"><StatusBanner tone="warning" title="播放提示">{audioError}</StatusBanner></div> : null}
                  {groupedCues.length && selectedCueGroup ? <div className="mt-5"><div className="flex gap-2 overflow-x-auto pb-3" aria-label="音频章节">{groupedCues.map(([group, cues]) => <button key={group} type="button" onClick={() => setActiveGroup(group)} className={`shrink-0 rounded-full border px-3 py-2 text-xs font-black transition ${(activeGroup || groupedCues[0]?.[0]) === group ? 'border-indigo-200 bg-indigo-100 text-indigo-800' : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'}`}>{group} · {cues.length}</button>)}</div><p className="mb-2 mt-2 text-xs font-black tracking-wider text-slate-500">{selectedCueGroup[0]}</p><div className="grid max-h-[42vh] gap-2 overflow-y-auto pr-1 sm:grid-cols-2">{selectedCueGroup[1].map((cue) => <button key={cue.id} type="button" onClick={() => playCue(cue)} className={`flex items-center gap-3 rounded-2xl border p-3.5 text-left transition [content-visibility:auto] ${activeCueId === cue.id ? 'border-indigo-300 bg-indigo-50' : 'border-slate-200 bg-white hover:bg-slate-50'}`}><span className={`flex size-9 shrink-0 items-center justify-center rounded-xl ${listenedCueIds.has(cue.id) ? 'bg-emerald-100 text-emerald-700' : 'bg-indigo-100 text-indigo-700'}`}>{activeCueId === cue.id && isPlaying ? <Pause className="size-4" /> : listenedCueIds.has(cue.id) ? <Check className="size-4" /> : <Play className="size-4" />}</span><span className="text-sm font-black leading-5 text-slate-800">{cue.text_en}</span></button>)}</div><p className="mt-3 text-xs font-bold text-slate-500">已精听 {listenedCueIds.size} 句，记录会自动同步。</p></div> : <div className="mt-4"><StatusBanner tone="info" title="连续听辨模式">该单元精细时间轴正在校对。点击上方播放按钮即可连续播放教材原声，仍可完成教材页听力题。</StatusBanner></div>}
                  <div className="mt-6 flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-sm font-black text-slate-800">{phaseGate.evidence}</p><p className="mt-1 text-xs font-semibold text-slate-500">{phaseGate.requirement}</p></div><Button disabled={!phaseGate.canContinue} onClick={completeAndContinue}>去做教材原题 <ChevronRight className="size-4" /></Button></div>
                </section>
              ) : null}

              {phase.kind === 'textbook' ? (() => {
                const tasks = plan.textbook_tasks ?? []
                const task = tasks[Math.min(activeTextbookTaskIndex, Math.max(0, tasks.length - 1))]
                if (!task) return <StatusBanner tone="info" title="教材任务准备中">本单元教材题图正在整理，可以先完成 AI 挑战。</StatusBanner>
                const answerValue = textbookTaskAnswers[task.id] ?? ''
                return <section className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,.65fr)]">
                  <div className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm"><div className="flex items-center justify-between border-b border-slate-200 px-5 py-4"><div><p className="flex items-center gap-2 text-xs font-black text-indigo-600"><BookOpenCheck className="size-4" /> 教材原题 · 第 {task.printed_page} 页</p><h2 className="mt-1 text-lg font-black text-slate-950">{task.title}</h2></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-500">{activeTextbookTaskIndex + 1}/{tasks.length}</span></div><div className="max-h-[64vh] overflow-auto bg-[#f7f5ef] p-3 sm:p-5"><img src={`/api/learners/${learnerId}/daily-lessons/classroom/textbook-task/${encodeURIComponent(task.asset)}`} alt={`${task.title}，教材第 ${task.printed_page} 页原题`} className="mx-auto h-auto w-full max-w-3xl rounded-xl shadow-sm" /></div></div>
                  <aside className="space-y-4"><div className="rounded-3xl border border-indigo-100 bg-indigo-50 p-5"><p className="flex items-center gap-2 text-xs font-black text-indigo-700"><BrainCircuit className="size-4" /> 做题提示</p><p className="mt-3 text-sm font-bold leading-6 text-slate-800">{task.instruction}</p><p className="mt-3 flex items-start gap-2 text-xs leading-5 text-slate-600"><Lightbulb className="mt-0.5 size-3.5 shrink-0 text-amber-600" />先独立完成。需要时再让课堂助手判断你卡在词汇、听辨还是句型。</p></div><div className="rounded-3xl border border-slate-200 bg-white p-5"><label htmlFor={`task-${task.id}`} className="text-xs font-black text-slate-700">按题号记录答案</label><textarea id={`task-${task.id}`} value={answerValue} onChange={(event) => { setTextbookCoachFeedback(null); setTextbookTaskAnswers((current) => ({ ...current, [task.id]: event.target.value })) }} className="mt-3 min-h-36 w-full resize-y rounded-2xl border border-slate-200 bg-[#faf9f6] p-4 text-sm font-semibold text-slate-950 outline-none focus:border-indigo-500" placeholder={'1a  我的答案…\n1b  我的答案…'} /><Button disabled={!answerValue.trim() || isCoachingTextbookTask} onClick={() => void requestTextbookCoaching(task.id, answerValue)} className="mt-3 w-full">{isCoachingTextbookTask ? <LoaderCircle className="size-4 animate-spin" /> : <BrainCircuit className="size-4" />}{isCoachingTextbookTask ? '正在对照教材分析…' : '检查我的作答'}</Button></div>{textbookCoachFeedback ? <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-5"><p className="text-xs font-black text-emerald-700">作答诊断</p><p className="mt-3 text-sm font-black leading-6 text-slate-950">{textbookCoachFeedback.diagnosis}</p><ul className="mt-3 space-y-1 text-xs leading-5 text-slate-600">{textbookCoachFeedback.evidence.map((item) => <li key={item}>· {item}</li>)}</ul><p className="mt-3 rounded-2xl bg-white p-3 text-xs font-bold leading-5 text-indigo-700">提示：{textbookCoachFeedback.hint}</p><Button variant="secondary" className="mt-3 w-full" onClick={() => followCoachAction(textbookCoachFeedback.next_action)}>{NEXT_ACTION_LABELS[textbookCoachFeedback.next_action]} <ArrowRight className="size-4" /></Button></div> : null}<div className="flex gap-2"><Button variant="secondary" disabled={activeTextbookTaskIndex === 0} onClick={() => { setTextbookCoachFeedback(null); setActiveTextbookTaskIndex((value) => Math.max(0, value - 1)) }}>上一页</Button>{activeTextbookTaskIndex < tasks.length - 1 ? <Button onClick={() => { setTextbookCoachFeedback(null); setActiveTextbookTaskIndex((value) => Math.min(tasks.length - 1, value + 1)) }}>下一页题目 <ArrowRight className="size-4" /></Button> : <Button disabled={!phaseGate.canContinue} onClick={completeAndContinue}>完成教材作答 <ArrowRight className="size-4" /></Button>}</div></aside>
                </section>
              })() : null}

              {phase.kind === 'challenge' ? (
                <section className="grid gap-5 lg:grid-cols-[1.2fr_.8fr]">
                  <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm sm:p-8"><p className="flex items-center gap-2 text-xs font-black text-indigo-600"><Target className="size-4" /> 课堂挑战 · 用一次证明掌握</p><h2 className="mt-4 text-xl font-black leading-8 text-slate-950">{prompt || plan.focus.question}</h2>{options.length ? <div className="mt-5 grid gap-2 sm:grid-cols-2">{options.map((option) => <button key={option} type="button" disabled={!isChallengeReady || isCompleted} onClick={() => onAnswerChange(option)} className={`rounded-2xl border px-4 py-3 text-left text-sm font-black transition disabled:cursor-not-allowed disabled:opacity-55 ${answer === option ? 'border-indigo-500 bg-indigo-600 text-white' : 'border-slate-200 bg-[#faf9f6] text-slate-700 hover:border-indigo-200 hover:bg-indigo-50'}`}>{option}</button>)}</div> : null}<textarea value={answer} onChange={(event) => onAnswerChange(event.target.value)} disabled={!isChallengeReady || isCompleted} className="mt-4 min-h-32 w-full resize-y rounded-2xl border border-slate-200 bg-[#faf9f6] p-4 text-sm font-semibold text-slate-950 outline-none transition focus:border-indigo-500 disabled:cursor-not-allowed disabled:opacity-60" placeholder="在这里输入你的答案…" />{isCompleted ? <StatusBanner tone="success" title="挑战完成">{feedback ?? '答案已完成评分，并同步到你的学习记录。'}</StatusBanner> : isChallengeReady ? <Button onClick={() => onSubmit(answer)} disabled={!answer.trim() || isSubmitting} className="mt-4">{isSubmitting ? <LoaderCircle className="size-4 animate-spin" /> : <Target className="size-4" />}{isSubmitting ? '正在评阅…' : '提交并查看反馈'}</Button> : <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4"><p className="text-sm font-black text-amber-900">评分挑战还没准备好</p><p className="mt-1 text-xs font-semibold leading-5 text-amber-800">教材学习进度已经保留。重新准备评分题后即可继续，不需要重做前面的步骤。</p><Button onClick={onPrepareChallenge} disabled={!onPrepareChallenge || isPreparingChallenge} className="mt-3">{isPreparingChallenge ? <LoaderCircle className="size-4 animate-spin" /> : <Target className="size-4" />}{isPreparingChallenge ? '正在准备…' : '重新准备挑战'}</Button></div>}</div>
                  <aside className="space-y-4"><div className="rounded-3xl border border-indigo-100 bg-indigo-50 p-5"><p className="flex items-center gap-2 text-xs font-black text-indigo-700"><BookOpenText className="size-4" /> 作答时记住</p><p className="mt-3 text-sm font-bold leading-6 text-slate-800">{plan.focus.grammar}</p></div><div className="rounded-3xl border border-slate-200 bg-white p-5"><p className="text-xs font-black text-slate-500">完成后会自动联动</p><ul className="mt-3 space-y-2 text-sm font-bold text-slate-700"><li className="flex items-center gap-2"><Check className="size-4 text-emerald-600" />教材进度</li><li className="flex items-center gap-2"><Check className="size-4 text-emerald-600" />语法掌握度</li><li className="flex items-center gap-2"><Check className="size-4 text-emerald-600" />记忆与复习计划</li></ul></div></aside>
                  {isCompleted ? <div className="lg:col-span-2 flex justify-end"><Button onClick={completeAndContinue}>查看课堂总结 <ArrowRight className="size-4" /></Button></div> : null}
                </section>
              ) : null}

              {phase.kind === 'reflection' ? (
                <section className="mx-auto max-w-4xl text-center"><div className="mx-auto flex size-20 items-center justify-center rounded-full bg-emerald-600 text-white shadow-xl shadow-emerald-200"><Flag className="size-8" /></div><p className="mt-6 text-xs font-black tracking-[0.2em] text-emerald-700">本课完成</p><h2 className="mt-3 text-3xl font-black sm:text-5xl">这些是你今天真正掌握的</h2><p className="mx-auto mt-4 max-w-xl text-sm font-semibold leading-7 text-slate-600">{plan.completion.memory_message}</p>{plan.grammar_lab ? <div className="mt-7 rounded-[2rem] border border-indigo-100 bg-white p-6 text-left shadow-sm"><div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><p className="flex items-center gap-2 text-xs font-black text-indigo-600"><Braces className="size-4" />语法掌握证据</p><h3 className="mt-2 text-xl font-black text-slate-950">{plan.grammar_lab.title}</h3><p className="mt-2 text-sm font-semibold leading-6 text-slate-600">{plan.grammar_lab.can_do}</p></div><span className={`shrink-0 rounded-full px-4 py-2 text-sm font-black ${grammarCorrectCount === grammarChecks.length ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-800'}`}>{grammarCorrectCount}/{grammarChecks.length} 题正确</span></div><div className="mt-4 rounded-2xl bg-[#f7f5ef] p-4"><p className="text-xs font-black text-slate-500">我的迁移表达</p><p className="mt-2 whitespace-pre-wrap text-sm font-bold leading-6 text-slate-900">{grammarTransfer || '尚未完成迁移表达，建议回到语法环节补写。'}</p></div>{grammarCorrectCount < grammarChecks.length ? <p className="mt-4 text-sm font-bold text-amber-700">还需复习：{grammarChecks.filter((check) => grammarAnswers[check.id] !== check.answer).map((check) => check.explanation).join('；')}</p> : <p className="mt-4 flex items-center gap-2 text-sm font-bold text-emerald-700"><CircleCheck className="size-4" />规则辨析已通过，并留下了自己的表达。</p>}</div> : null}<div className="mt-8 grid gap-3 sm:grid-cols-4"><SummaryStat label="课堂经验" value={`+${plan.completion.xp} XP`} /><SummaryStat label="语法检查" value={`${grammarCorrectCount}/${grammarChecks.length}`} /><SummaryStat label="已判断词汇" value={`${classifiedVocabularyCount}/${plan.language_cards.length}`} /><SummaryStat label="教材作答" value={`${textbookAnswerCount} 页`} /></div><div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">{boosterCount ? <Button onClick={onOpenBoosters}><Sparkles className="size-4" />查看能力加练</Button> : null}<Button variant="secondary" onClick={requestClose}>返回学习中心</Button></div></section>
              ) : null}

              {!phaseKind ? <StatusBanner tone="warning" title="这一阶段暂时无法显示">课堂数据包含未识别的阶段“{phase.kind}”。进度没有丢失，请返回学习中心后重新进入。</StatusBanner> : null}
            </div>
          </main>
        </div>
        <nav className="flex shrink-0 items-center gap-3 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur-xl lg:hidden" aria-label="课堂阶段导航">
          <IconButton label="上一环节" disabled={phaseIndex === 0} onClick={goPrevious} className="border-slate-200 bg-white text-slate-700 disabled:opacity-30"><ArrowLeft className="size-4" /></IconButton>
          <div className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-[#faf9f6] px-3 py-2 text-left"><span className="block truncate text-xs font-black text-slate-900">{phaseIndex + 1}/{plan.phases.length} · {phase.title}</span><span className="mt-1 block truncate text-[10px] font-semibold text-slate-500">{phaseGate.evidence}</span></div>
          <IconButton label="下一环节" disabled={phaseIndex === plan.phases.length - 1 || !phaseGate.canContinue} onClick={completeAndContinue} className="border-indigo-200 bg-indigo-600 text-white disabled:opacity-30"><ArrowRight className="size-4" /></IconButton>
        </nav>
      </div>
    </div>
  )
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return <div className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-xs font-bold text-slate-500">{label}</p><p className="mt-1 text-xl font-black text-slate-950">{value}</p></div>
}

function GrammarLabPanel({
  lab,
  answers,
  transfer,
  onAnswer,
  onTransfer,
  onContinue,
}: {
  lab: NonNullable<ClassroomPlan['grammar_lab']>
  answers: Record<string, string>
  transfer: string
  onAnswer: (checkId: string, value: string) => void
  onTransfer: (value: string) => void
  onContinue: () => void
}) {
  const answeredCount = lab.checks.filter((check) => Boolean(answers[check.id])).length
  const correctCount = lab.checks.filter((check) => answers[check.id] === check.answer).length
  const ready = answeredCount === lab.checks.length && transfer.trim().length >= 8

  return (
    <section className="space-y-5">
      <div className="overflow-hidden rounded-[2rem] border border-indigo-100 bg-white p-6 shadow-sm sm:p-8">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-3xl"><p className="flex items-center gap-2 text-xs font-black tracking-wider text-indigo-600"><Braces className="size-4" /> 当前句型 · 学完要能自己用</p><h2 className="mt-3 text-2xl font-black text-slate-950 sm:text-4xl">{lab.title}</h2><p className="mt-3 text-sm font-bold leading-7 text-slate-600">掌握证据：{lab.can_do}</p></div>
          <span className={`shrink-0 rounded-full px-4 py-2 text-sm font-black ${correctCount === lab.checks.length ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>{correctCount}/{lab.checks.length} 题正确</span>
        </div>
        <div className="mt-6 rounded-3xl border border-indigo-100 bg-indigo-50 p-5"><p className="text-xs font-black text-indigo-600">1 · 先抓住规则</p><p className="mt-2 text-base font-black leading-7 text-slate-950">{lab.rule}</p><div className="mt-4 flex flex-wrap gap-2">{lab.forms.map((form) => <span key={form} className="rounded-xl border border-indigo-100 bg-white px-3 py-2 text-xs font-bold text-slate-700">{form}</span>)}</div></div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">{lab.examples.map((example) => <div key={example.en} className="rounded-2xl border border-slate-200 bg-[#faf9f6] p-4"><p className="text-sm font-black text-slate-950">{example.en}</p><p className="mt-1 text-xs font-semibold text-slate-500">{example.zh}</p></div>)}</div>
        <div className="mt-4 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4"><Lightbulb className="mt-0.5 size-4 shrink-0 text-amber-600" /><div><p className="text-xs font-black text-amber-700">最容易错</p><p className="mt-1 text-sm font-bold leading-6 text-slate-700">{lab.common_error}</p></div></div>
      </div>

      <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="flex items-end justify-between gap-4"><div><p className="text-xs font-black text-indigo-600">2 · 立即辨析</p><h3 className="mt-2 text-xl font-black text-slate-950">不是“看懂”，要连续选对</h3></div><span className="text-xs font-bold text-slate-500">已答 {answeredCount}/{lab.checks.length}</span></div>
        <div className="mt-5 space-y-4">{lab.checks.map((check, index) => {
          const selected = answers[check.id]
          const isCorrect = selected === check.answer
          return <article key={check.id} className="rounded-3xl border border-slate-200 bg-[#faf9f6] p-5 [content-visibility:auto]"><p className="text-sm font-black leading-6 text-slate-950">{index + 1}. {check.prompt}</p><div className="mt-3 grid gap-2 sm:grid-cols-3">{check.options.map((option) => { const optionSelected = selected === option; const optionCorrect = option === check.answer; return <button key={option} type="button" onClick={() => onAnswer(check.id, option)} className={`rounded-2xl border px-4 py-3 text-left text-sm font-bold transition ${optionSelected && optionCorrect ? 'border-emerald-300 bg-emerald-100 text-emerald-800' : optionSelected ? 'border-rose-300 bg-rose-100 text-rose-800' : 'border-slate-200 bg-white text-slate-700 hover:border-indigo-200 hover:bg-indigo-50'}`}>{option}</button> })}</div>{selected ? <div className={`mt-3 flex items-start gap-2 rounded-2xl p-3 text-xs font-bold leading-5 ${isCorrect ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'}`}>{isCorrect ? <CircleCheck className="mt-0.5 size-4 shrink-0" /> : <CircleX className="mt-0.5 size-4 shrink-0" />}<span>{isCorrect ? '选对了。' : `再想一下，正确结构是“${check.answer}”。`}{check.explanation}</span></div> : null}</article>
        })}</div>
      </div>

      <div className="rounded-[2rem] border border-indigo-100 bg-indigo-50 p-6 sm:p-8"><p className="text-xs font-black text-indigo-600">3 · 自己用出来</p><h3 className="mt-2 text-xl font-black text-slate-950">{lab.transfer_prompt}</h3><textarea value={transfer} onChange={(event) => onTransfer(event.target.value)} className="mt-4 min-h-28 w-full resize-y rounded-2xl border border-indigo-100 bg-white p-4 text-sm font-semibold text-slate-950 outline-none transition focus:border-indigo-500" placeholder="不要照抄例句，换成你自己的真实信息…" /><div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><p className="text-xs font-bold text-slate-600">{ready ? '语法证据已形成：规则辨析完成，并留下了自己的表达。' : '完成全部辨析题，并至少写 8 个字符的迁移表达。'}</p><Button disabled={!ready} onClick={onContinue}>保存掌握证据，继续课堂 <ArrowRight className="size-4" /></Button></div></div>
    </section>
  )
}
