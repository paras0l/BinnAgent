import {
  ArrowLeft, ArrowRight, BookOpenCheck, BookOpenText, BrainCircuit, Braces, Check, ChevronRight, CircleCheck, CircleX, Flag,
  Cloud, CloudOff, Headphones, Lightbulb, LoaderCircle, Pause, Play, ScanLine, Sparkles, Target, X,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { IconButton } from '@/components/ui/IconButton'
import { StatusBanner } from '@/components/ui/StatusBanner'

export interface ClassroomPlan {
  schema_version: string
  classroom_id: string
  generation_mode: 'llm_generated' | 'curated_fallback'
  source: { id: string; title: string; edition: string }
  unit: { id: string; title: string; subtitle: string; ordinal: number }
  hero: { eyebrow: string; title: string; mission: string; coach_message: string }
  phases: Array<{ id: string; kind: string; title: string; minutes: number; icon: string }>
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
  violet: 'from-violet-500 to-indigo-600 shadow-violet-200',
  cyan: 'from-cyan-500 to-blue-600 shadow-cyan-200',
  amber: 'from-amber-400 to-orange-500 shadow-amber-200',
  rose: 'from-rose-500 to-pink-600 shadow-rose-200',
}

type SaveStatus = 'idle' | 'saving' | 'saved' | 'offline'

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
  const [activeTextbookTaskIndex, setActiveTextbookTaskIndex] = useState(0)
  const [textbookCoachFeedback, setTextbookCoachFeedback] = useState<TextbookCoachFeedback | null>(null)
  const [isCoachingTextbookTask, setIsCoachingTextbookTask] = useState(false)
  const [timeline, setTimeline] = useState<TimelineCue[]>([])
  const [activeGroup, setActiveGroup] = useState('')
  const [activeCueId, setActiveCueId] = useState<string | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [audioError, setAudioError] = useState<string | null>(null)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const audioRef = useRef<HTMLAudioElement>(null)
  const phase = plan.phases[phaseIndex]
  const teachingGoals = (plan.teaching?.['学习目标'] ?? plan.teaching?.['单元学习目标'] ?? [])
    .filter((item) => !item.endsWith('能够：'))
    .slice(0, 3)
  const isCompleted = lesson?.status === 'completed' || Boolean(lesson?.verification_status)
  const completed = isCompleted && phase.kind === 'reflection'
  const progress = Math.min(100, Math.round((Math.max(completedPhaseIds.size, phaseIndex) + (completed ? 1 : 0)) / plan.phases.length * 100))
  const grammarChecks = plan.grammar_lab?.checks ?? []
  const grammarCorrectCount = grammarChecks.filter((check) => grammarAnswers[check.id] === check.answer).length

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [onClose])

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
          completed,
        }),
      })
        .then((response) => {
          if (!response.ok) throw new Error('progress save failed')
          setSaveStatus('saved')
        })
        .catch((error: unknown) => {
          if (!(error instanceof DOMException && error.name === 'AbortError')) setSaveStatus('offline')
        })
    }, 450)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [completed, completedPhaseIds, flipped, grammarAnswers, grammarTransfer, learnerId, listenedCueIds, phase.id, plan.classroom_id, plan.unit.id, textbookTaskAnswers])

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
    void audio.play().catch(() => setAudioError('浏览器阻止了自动播放，请再点一次播放按钮。'))
  }

  const moveToPhase = (nextIndex: number) => {
    setCompletedPhaseIds((current) => new Set(current).add(phase.id))
    setPhaseIndex(Math.max(0, Math.min(nextIndex, plan.phases.length - 1)))
  }

  const goNext = () => moveToPhase(phaseIndex + 1)
  const goPrevious = () => moveToPhase(phaseIndex - 1)

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
    <div role="dialog" aria-modal="true" aria-label={`${plan.unit.title} AI 课堂`} className="fixed inset-0 z-[120] overflow-hidden bg-[#07101f] text-white">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_16%_12%,rgba(124,58,237,0.32),transparent_28%),radial-gradient(circle_at_82%_20%,rgba(6,182,212,0.22),transparent_25%),linear-gradient(145deg,#07101f_0%,#0f172a_54%,#111827_100%)]" />
      <div className="relative flex h-full flex-col">
        <header className="flex h-18 shrink-0 items-center gap-4 border-b border-white/10 bg-slate-950/45 px-4 backdrop-blur-xl sm:px-7">
          <IconButton label="退出课堂" onClick={onClose} className="border-white/10 bg-white/5 text-white hover:bg-white/10">
            <ArrowLeft className="size-4" />
          </IconButton>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-[10px] font-black tracking-[0.22em] text-cyan-300">
              <Sparkles className="size-3" />
              {plan.generation_mode === 'llm_generated' ? 'AI 实时编排' : '智能课堂模板'}
            </div>
            <p className="truncate text-sm font-black text-white sm:text-base">{plan.unit.title} · {plan.unit.subtitle}</p>
          </div>
          <div className="hidden w-56 sm:block">
            <div className="mb-1.5 flex justify-between text-[11px] font-bold text-slate-400"><span>课堂进度</span><span>{progress}%</span></div>
            <div className="h-1.5 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-400 transition-all" style={{ width: `${progress}%` }} /></div>
          </div>
          <div className="hidden items-center gap-1.5 text-[11px] font-bold text-slate-400 md:flex" aria-live="polite">
            {saveStatus === 'offline' ? <CloudOff className="size-3.5 text-amber-300" /> : <Cloud className="size-3.5 text-emerald-300" />}
            {saveStatus === 'saving' ? '保存中' : saveStatus === 'offline' ? '稍后重试' : '进度已同步'}
          </div>
          <IconButton label="关闭" onClick={onClose} className="border-transparent text-slate-400 hover:bg-white/10 hover:text-white"><X className="size-5" /></IconButton>
        </header>

        <div className="grid min-h-0 flex-1 lg:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="hidden border-r border-white/10 bg-slate-950/35 p-5 lg:block">
            <p className="mb-4 text-xs font-black uppercase tracking-[0.18em] text-slate-500">Today's route</p>
            <ol className="space-y-2">
              {plan.phases.map((item, index) => (
                <li key={item.id}>
                  <button type="button" onClick={() => moveToPhase(index)} className={`group flex w-full items-center gap-3 rounded-2xl border px-3 py-3 text-left transition ${index === phaseIndex ? 'border-violet-400/40 bg-violet-500/15' : 'border-transparent hover:bg-white/5'}`}>
                    <span className={`flex size-9 shrink-0 items-center justify-center rounded-xl ${completedPhaseIds.has(item.id) ? 'bg-emerald-400 text-slate-950' : index === phaseIndex ? 'bg-violet-500 text-white shadow-lg shadow-violet-500/30' : 'bg-white/5 text-slate-500'}`}>
                      {completedPhaseIds.has(item.id) || (isCompleted && index === plan.phases.length - 1) ? <Check className="size-4" /> : <span className="text-xs font-black">{index + 1}</span>}
                    </span>
                    <span className="min-w-0"><span className={`block truncate text-sm font-black ${index === phaseIndex ? 'text-white' : 'text-slate-400'}`}>{item.title}</span><span className="text-[11px] text-slate-600">约 {item.minutes} 分钟</span></span>
                  </button>
                </li>
              ))}
            </ol>
            <div className="mt-6 rounded-2xl border border-cyan-300/15 bg-cyan-400/5 p-4">
              <p className="flex items-center gap-2 text-xs font-black text-cyan-300"><Sparkles className="size-3.5" />AI COACH</p>
              <p className="mt-2 text-xs font-semibold leading-5 text-slate-300">{plan.hero.coach_message}</p>
            </div>
          </aside>

          <main className="min-h-0 overflow-y-auto px-4 py-6 sm:px-8 lg:px-12 lg:py-9">
            <div className="mx-auto max-w-5xl">
              <div className="mb-7 flex items-center gap-3 text-sm font-black text-violet-300">
                <span className="flex size-9 items-center justify-center rounded-xl bg-violet-500/15">{phaseIndex + 1}</span>
                {phase.title}<span className="text-slate-600">· {phase.minutes} MIN</span>
              </div>

              {phase.kind === 'briefing' ? (
                <section className="overflow-hidden rounded-[2rem] border border-white/10 bg-white/[0.06] p-6 shadow-2xl backdrop-blur-xl sm:p-10">
                  <p className="text-xs font-black tracking-[0.22em] text-cyan-300">{plan.hero.eyebrow}</p>
                  <h1 className="mt-4 max-w-3xl text-3xl font-black tracking-tight sm:text-5xl">{plan.hero.title}</h1>
                  <div className="mt-8 grid gap-4 sm:grid-cols-[1.3fr_1fr]">
                    <div className="rounded-3xl bg-gradient-to-br from-violet-500 to-indigo-700 p-6 shadow-xl shadow-violet-950/40"><p className="text-xs font-black uppercase tracking-wider text-violet-100">本课任务</p><p className="mt-3 text-lg font-black leading-8">{plan.hero.mission}</p></div>
                    <div className="rounded-3xl border border-white/10 bg-slate-950/35 p-6"><p className="flex items-center gap-2 text-xs font-black text-amber-300"><Target className="size-4" /> BIG QUESTION</p><p className="mt-3 text-lg font-black leading-7">{plan.focus.question}</p></div>
                  </div>
                  {plan.grammar_lab ? <div className="mt-5 flex items-start gap-3 rounded-3xl border border-fuchsia-300/20 bg-fuchsia-400/[0.07] p-5"><Braces className="mt-0.5 size-5 shrink-0 text-fuchsia-300" /><div><p className="text-xs font-black text-fuchsia-300">今天必须掌握的语法</p><p className="mt-1 text-base font-black text-white">{plan.grammar_lab.title}</p><p className="mt-1 text-sm font-semibold leading-6 text-slate-300">{plan.grammar_lab.can_do}</p></div></div> : null}
                  {teachingGoals.length ? <div className="mt-5 rounded-3xl border border-white/10 bg-slate-950/30 p-5"><p className="text-xs font-black text-cyan-300">本课可观察学习证据</p><ul className="mt-3 grid gap-2 text-sm font-bold leading-6 text-slate-200 sm:grid-cols-3">{teachingGoals.map((goal) => <li key={goal} className="rounded-2xl bg-white/5 p-3"><Check className="mr-2 inline size-4 text-emerald-300" />{goal}</li>)}</ul></div> : null}
                  <Button onClick={goNext} className="mt-8 bg-white text-slate-950 hover:bg-slate-100">进入课堂 <ArrowRight className="size-4" /></Button>
                </section>
              ) : null}

              {phase.kind === 'cards' ? (
                <section>
                  <div className="mb-6">
                    <p className="text-xs font-black tracking-[0.18em] text-cyan-300">本册新词 {plan.vocabulary?.core_count ?? plan.language_cards.length} · 小学复现 {plan.vocabulary?.primary_review_count ?? 0}</p>
                    <h2 className="mt-2 text-2xl font-black sm:text-3xl">先区分“要学会”和“要唤醒”</h2>
                    <p className="mt-2 text-sm font-semibold text-slate-400">新词进入本单元学习计划；小学词汇用于快速唤醒，不把已经学过的内容伪装成新词。</p>
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    {plan.language_cards.map((card) => {
                      const isFlipped = flipped.has(card.id)
                      return <button key={card.id} type="button" aria-pressed={isFlipped} onClick={() => setFlipped((current) => { const next = new Set(current); if (next.has(card.id)) next.delete(card.id); else next.add(card.id); return next })} className={`min-h-44 rounded-3xl bg-gradient-to-br p-5 text-left shadow-xl transition duration-300 hover:-translate-y-1 ${ACCENTS[card.accent]} ${isFlipped ? 'ring-2 ring-white/70' : ''}`}><ScanLine className="size-5 opacity-75" /><p className="mt-8 text-xl font-black">{isFlipped ? card.back : card.front}</p><p className="mt-3 text-xs font-bold text-white/70">{isFlipped ? '再点一次返回' : '点击翻转'}</p></button>
                    })}
                  </div>
                  {plan.vocabulary?.primary_review.length ? <div className="mt-5 rounded-3xl border border-emerald-300/15 bg-emerald-400/[0.06] p-5"><p className="text-xs font-black text-emerald-300">小学词汇快速唤醒</p><div className="mt-3 flex flex-wrap gap-2">{plan.vocabulary.primary_review.slice(0, 18).map((item) => <span key={item.term} title={item.meaning_zh} className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-bold text-slate-200">{item.term}</span>)}</div><p className="mt-3 text-xs text-slate-500">悬停可查看释义；AI 会根据后续做题表现决定哪些词需要重新进入复习。</p></div> : null}
                  <div className="mt-7 flex items-center justify-between"><p className="text-sm font-bold text-slate-400">已点亮 {flipped.size} / {plan.language_cards.length}</p><Button onClick={goNext}>下一环节 <ChevronRight className="size-4" /></Button></div>
                </section>
              ) : null}

              {phase.kind === 'grammar' && plan.grammar_lab ? (
                <GrammarLabPanel
                  lab={plan.grammar_lab}
                  answers={grammarAnswers}
                  transfer={grammarTransfer}
                  onAnswer={(checkId, value) => setGrammarAnswers((current) => ({ ...current, [checkId]: value }))}
                  onTransfer={setGrammarTransfer}
                  onContinue={goNext}
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
                  <div className="rounded-[2rem] border border-cyan-300/15 bg-gradient-to-br from-cyan-400/10 to-blue-500/5 p-6 sm:p-8">
                    <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between"><div><p className="flex items-center gap-2 text-xs font-black tracking-wider text-cyan-300"><Headphones className="size-4" /> 教材原声 · 听感训练</p><h2 className="mt-3 text-2xl font-black">先听懂关键信息，再回到教材做题</h2><p className="mt-2 text-sm font-semibold text-slate-400">按句播放用于定位信息，不要求机械跟读。先不看文本听一遍，再点开难句核对。</p></div><button type="button" onClick={playContinuousAudio} className="flex size-20 shrink-0 items-center justify-center rounded-full border border-cyan-300/30 bg-cyan-300/10 text-cyan-300 transition hover:scale-105 hover:bg-cyan-300/20" aria-label={isPlaying && !activeCueId ? '暂停教材原声' : '连续播放教材原声'}>{isPlaying && !activeCueId ? <Pause className="size-8" /> : <Play className="ml-1 size-8" />}</button></div>
                  </div>
                  {audioError ? <div className="mt-4"><StatusBanner tone="warning" title="播放提示">{audioError}</StatusBanner></div> : null}
                  {groupedCues.length && selectedCueGroup ? <div className="mt-5"><div className="flex gap-2 overflow-x-auto pb-3" aria-label="音频章节">{groupedCues.map(([group, cues]) => <button key={group} type="button" onClick={() => setActiveGroup(group)} className={`shrink-0 rounded-full border px-3 py-2 text-xs font-black transition ${(activeGroup || groupedCues[0]?.[0]) === group ? 'border-cyan-300/50 bg-cyan-300/15 text-cyan-200' : 'border-white/10 bg-white/[0.04] text-slate-400 hover:bg-white/[0.08]'}`}>{group} · {cues.length}</button>)}</div><p className="mb-2 mt-2 text-xs font-black uppercase tracking-wider text-slate-500">{selectedCueGroup[0]}</p><div className="grid max-h-[42vh] gap-2 overflow-y-auto pr-1 sm:grid-cols-2">{selectedCueGroup[1].map((cue) => <button key={cue.id} type="button" onClick={() => playCue(cue)} className={`flex items-center gap-3 rounded-2xl border p-3.5 text-left transition [content-visibility:auto] ${activeCueId === cue.id ? 'border-cyan-300/50 bg-cyan-300/10' : 'border-white/10 bg-white/[0.04] hover:bg-white/[0.08]'}`}><span className={`flex size-9 shrink-0 items-center justify-center rounded-xl ${listenedCueIds.has(cue.id) ? 'bg-emerald-400 text-slate-950' : 'bg-white/10 text-cyan-300'}`}>{activeCueId === cue.id && isPlaying ? <Pause className="size-4" /> : listenedCueIds.has(cue.id) ? <Check className="size-4" /> : <Play className="size-4" />}</span><span className="text-sm font-black leading-5 text-slate-100">{cue.text_en}</span></button>)}</div><p className="mt-3 text-xs font-bold text-slate-500">已精听 {listenedCueIds.size} 句，记录会自动同步。</p></div> : <div className="mt-4"><StatusBanner tone="info" title="连续听辨模式">该单元精细时间轴正在校对。点击上方播放按钮即可连续播放教材原声，仍可完成教材页听力题。</StatusBanner></div>}
                  <div className="mt-6 flex justify-end"><Button onClick={goNext}>去做教材原题 <ChevronRight className="size-4" /></Button></div>
                </section>
              ) : null}

              {phase.kind === 'textbook' ? (() => {
                const tasks = plan.textbook_tasks ?? []
                const task = tasks[Math.min(activeTextbookTaskIndex, Math.max(0, tasks.length - 1))]
                if (!task) return <StatusBanner tone="info" title="教材任务准备中">本单元教材题图正在整理，可以先完成 AI 挑战。</StatusBanner>
                const answerValue = textbookTaskAnswers[task.id] ?? ''
                return <section className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,.65fr)]">
                  <div className="overflow-hidden rounded-[2rem] border border-white/10 bg-white/[0.06]"><div className="flex items-center justify-between border-b border-white/10 px-5 py-4"><div><p className="flex items-center gap-2 text-xs font-black text-cyan-300"><BookOpenCheck className="size-4" /> 教材原题 · 第 {task.printed_page} 页</p><h2 className="mt-1 text-lg font-black">{task.title}</h2></div><span className="rounded-full bg-white/5 px-3 py-1 text-xs font-bold text-slate-400">{activeTextbookTaskIndex + 1}/{tasks.length}</span></div><div className="max-h-[64vh] overflow-auto bg-white p-3 sm:p-5"><img src={`/api/learners/${learnerId}/daily-lessons/classroom/textbook-task/${encodeURIComponent(task.asset)}`} alt={`${task.title}，教材第 ${task.printed_page} 页原题`} className="mx-auto h-auto w-full max-w-3xl rounded-xl" /></div></div>
                  <aside className="space-y-4"><div className="rounded-3xl border border-violet-300/15 bg-violet-500/10 p-5"><p className="flex items-center gap-2 text-xs font-black text-violet-300"><BrainCircuit className="size-4" /> AI 做题教练</p><p className="mt-3 text-sm font-bold leading-6 text-slate-200">{task.instruction}</p><p className="mt-3 flex items-start gap-2 text-xs leading-5 text-slate-400"><Lightbulb className="mt-0.5 size-3.5 shrink-0 text-amber-300" />先独立完成。AI 不直接报答案，会根据你的作答判断是词汇、听辨还是句型问题。</p></div><div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5"><label htmlFor={`task-${task.id}`} className="text-xs font-black text-slate-300">把教材答案写在这里</label><textarea id={`task-${task.id}`} value={answerValue} onChange={(event) => { setTextbookCoachFeedback(null); setTextbookTaskAnswers((current) => ({ ...current, [task.id]: event.target.value })) }} className="mt-3 min-h-36 w-full resize-y rounded-2xl border border-white/10 bg-slate-950/45 p-4 text-sm font-semibold text-white outline-none focus:border-violet-400" placeholder="按题号填写，例如：1a: ...；1b: ..." /><Button disabled={!answerValue.trim() || isCoachingTextbookTask} onClick={() => void requestTextbookCoaching(task.id, answerValue)} className="mt-3 w-full">{isCoachingTextbookTask ? <LoaderCircle className="size-4 animate-spin" /> : <BrainCircuit className="size-4" />}{isCoachingTextbookTask ? 'AI 正在对照教材分析…' : '交给 AI 诊断'}</Button></div>{textbookCoachFeedback ? <div className="rounded-3xl border border-emerald-300/15 bg-emerald-400/[0.07] p-5"><div className="flex items-center justify-between gap-2"><p className="text-xs font-black text-emerald-300">{textbookCoachFeedback.generation_mode === 'llm_generated' ? 'AI 实时诊断' : '离线诊断建议'}</p><span className="rounded-full bg-white/5 px-2 py-1 text-[10px] font-bold text-slate-400">{textbookCoachFeedback.next_action}</span></div><p className="mt-3 text-sm font-black leading-6 text-white">{textbookCoachFeedback.diagnosis}</p><ul className="mt-3 space-y-1 text-xs leading-5 text-slate-400">{textbookCoachFeedback.evidence.map((item) => <li key={item}>· {item}</li>)}</ul><p className="mt-3 rounded-2xl bg-slate-950/35 p-3 text-xs font-bold leading-5 text-cyan-200">提示：{textbookCoachFeedback.hint}</p></div> : null}<div className="flex gap-2"><Button variant="secondary" disabled={activeTextbookTaskIndex === 0} onClick={() => { setTextbookCoachFeedback(null); setActiveTextbookTaskIndex((value) => Math.max(0, value - 1)) }}>上一页</Button>{activeTextbookTaskIndex < tasks.length - 1 ? <Button onClick={() => { setTextbookCoachFeedback(null); setActiveTextbookTaskIndex((value) => Math.min(tasks.length - 1, value + 1)) }}>下一页题目 <ArrowRight className="size-4" /></Button> : <Button onClick={goNext}>进入 AI 诊断 <ArrowRight className="size-4" /></Button>}</div></aside>
                </section>
              })() : null}

              {phase.kind === 'challenge' ? (
                <section className="grid gap-5 lg:grid-cols-[1.2fr_.8fr]">
                  <div className="rounded-[2rem] border border-white/10 bg-white/[0.06] p-6 sm:p-8"><p className="flex items-center gap-2 text-xs font-black text-amber-300"><Target className="size-4" /> AI CHECKPOINT</p><h2 className="mt-4 text-xl font-black leading-8">{prompt || plan.focus.question}</h2>{options.length ? <div className="mt-5 grid gap-2 sm:grid-cols-2">{options.map((option) => <button key={option} type="button" onClick={() => onAnswerChange(option)} className={`rounded-2xl border px-4 py-3 text-left text-sm font-black transition ${answer === option ? 'border-violet-400 bg-violet-500/20 text-white' : 'border-white/10 bg-white/5 text-slate-300 hover:bg-white/10'}`}>{option}</button>)}</div> : null}<textarea value={answer} onChange={(event) => onAnswerChange(event.target.value)} disabled={isCompleted} className="mt-4 min-h-32 w-full resize-y rounded-2xl border border-white/10 bg-slate-950/45 p-4 text-sm font-semibold text-white outline-none transition focus:border-violet-400" placeholder="在这里输入你的答案…" />{isCompleted ? <StatusBanner tone="success" title="挑战完成">{feedback ?? '答案已完成评分，并同步到你的学习记录。'}</StatusBanner> : <Button onClick={() => onSubmit(answer)} disabled={!answer.trim() || isSubmitting || !lesson} className="mt-4">{isSubmitting ? <LoaderCircle className="size-4 animate-spin" /> : <Target className="size-4" />}{isSubmitting ? 'AI 正在评阅…' : '提交并生成反馈'}</Button>}</div>
                  <aside className="space-y-4"><div className="rounded-3xl border border-violet-300/15 bg-violet-500/10 p-5"><p className="flex items-center gap-2 text-xs font-black text-violet-300"><BookOpenText className="size-4" /> 语言焦点</p><p className="mt-3 text-sm font-bold leading-6 text-slate-200">{plan.focus.grammar}</p></div><div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5"><p className="text-xs font-black text-slate-400">联动状态</p><ul className="mt-3 space-y-2 text-sm font-bold text-slate-300"><li className="flex items-center gap-2"><Check className="size-4 text-emerald-400" />教材进度已关联</li><li className="flex items-center gap-2"><Check className="size-4 text-emerald-400" />评分与掌握度引擎</li><li className="flex items-center gap-2"><Check className="size-4 text-emerald-400" />Memory 与复习计划</li></ul></div></aside>
                  {isCompleted ? <div className="lg:col-span-2 flex justify-end"><Button onClick={goNext}>查看课堂总结 <ArrowRight className="size-4" /></Button></div> : null}
                </section>
              ) : null}

              {phase.kind === 'reflection' ? (
                <section className="mx-auto max-w-4xl text-center"><div className="mx-auto flex size-20 items-center justify-center rounded-full bg-gradient-to-br from-emerald-400 to-cyan-500 shadow-2xl shadow-emerald-500/25"><Flag className="size-8" /></div><p className="mt-6 text-xs font-black tracking-[0.2em] text-emerald-300">CLASS COMPLETE</p><h2 className="mt-3 text-3xl font-black sm:text-5xl">今天学会了什么</h2><p className="mx-auto mt-4 max-w-xl text-sm font-semibold leading-7 text-slate-400">{plan.completion.memory_message}</p>{plan.grammar_lab ? <div className="mt-7 rounded-[2rem] border border-fuchsia-300/20 bg-fuchsia-400/[0.07] p-6 text-left"><div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><p className="flex items-center gap-2 text-xs font-black text-fuchsia-300"><Braces className="size-4" />本节语法掌握证据</p><h3 className="mt-2 text-xl font-black text-white">{plan.grammar_lab.title}</h3><p className="mt-2 text-sm font-semibold leading-6 text-slate-300">{plan.grammar_lab.can_do}</p></div><span className={`shrink-0 rounded-full px-4 py-2 text-sm font-black ${grammarCorrectCount === grammarChecks.length ? 'bg-emerald-400 text-slate-950' : 'bg-amber-300 text-slate-950'}`}>{grammarCorrectCount}/{grammarChecks.length} 题正确</span></div><div className="mt-4 rounded-2xl bg-slate-950/35 p-4"><p className="text-xs font-black text-slate-500">我的迁移句</p><p className="mt-2 whitespace-pre-wrap text-sm font-bold leading-6 text-cyan-100">{grammarTransfer || '尚未完成迁移表达，建议回到语法环节补写。'}</p></div>{grammarCorrectCount < grammarChecks.length ? <p className="mt-4 text-sm font-bold text-amber-200">还需复习：{grammarChecks.filter((check) => grammarAnswers[check.id] !== check.answer).map((check) => check.explanation).join('；')}</p> : <p className="mt-4 flex items-center gap-2 text-sm font-bold text-emerald-300"><CircleCheck className="size-4" />规则辨析已通过，可以在教材和真实表达中继续使用。</p>}</div> : null}<div className="mt-8 grid gap-3 sm:grid-cols-4"><SummaryStat label="课堂经验" value={`+${plan.completion.xp} XP`} /><SummaryStat label="语法检查" value={`${grammarCorrectCount}/${grammarChecks.length}`} /><SummaryStat label="语言卡片" value={`${flipped.size}/${plan.language_cards.length}`} /><SummaryStat label="能力加练" value={`${boosterCount} 个`} /></div><div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">{boosterCount ? <Button onClick={onOpenBoosters}><Sparkles className="size-4" />查看能力加练</Button> : null}<Button variant="secondary" onClick={onClose}>返回学习中心</Button></div></section>
              ) : null}
            </div>
          </main>
        </div>
        <nav className="flex shrink-0 items-center gap-3 border-t border-white/10 bg-slate-950/80 px-4 py-3 backdrop-blur-xl lg:hidden" aria-label="课堂阶段导航">
          <IconButton label="上一环节" disabled={phaseIndex === 0} onClick={goPrevious} className="border-white/10 bg-white/5 text-white disabled:opacity-30"><ArrowLeft className="size-4" /></IconButton>
          <button type="button" onClick={goNext} disabled={phaseIndex === plan.phases.length - 1} className="min-w-0 flex-1 rounded-xl border border-violet-400/30 bg-violet-500/15 px-3 py-2 text-left disabled:opacity-50"><span className="block truncate text-xs font-black text-white">{phaseIndex + 1}/{plan.phases.length} · {phase.title}</span><span className="mt-1 block h-1 overflow-hidden rounded-full bg-white/10"><span className="block h-full bg-gradient-to-r from-violet-500 to-cyan-400" style={{ width: `${progress}%` }} /></span></button>
          <IconButton label="下一环节" disabled={phaseIndex === plan.phases.length - 1} onClick={goNext} className="border-white/10 bg-white/5 text-white disabled:opacity-30"><ArrowRight className="size-4" /></IconButton>
        </nav>
      </div>
    </div>
  )
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return <div className="rounded-2xl border border-white/10 bg-white/[0.05] p-4"><p className="text-xs font-bold text-slate-500">{label}</p><p className="mt-1 text-xl font-black text-white">{value}</p></div>
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
      <div className="overflow-hidden rounded-[2rem] border border-fuchsia-300/20 bg-gradient-to-br from-fuchsia-500/15 via-violet-500/10 to-cyan-500/5 p-6 sm:p-8">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-3xl"><p className="flex items-center gap-2 text-xs font-black tracking-wider text-fuchsia-300"><Braces className="size-4" /> GRAMMAR LAB · 今天只攻下一条结构</p><h2 className="mt-3 text-2xl font-black sm:text-4xl">{lab.title}</h2><p className="mt-3 text-sm font-bold leading-7 text-cyan-100">学完证据：{lab.can_do}</p></div>
          <span className={`shrink-0 rounded-full px-4 py-2 text-sm font-black ${correctCount === lab.checks.length ? 'bg-emerald-400 text-slate-950' : 'bg-white/10 text-white'}`}>{correctCount}/{lab.checks.length} 已掌握</span>
        </div>
        <div className="mt-6 rounded-3xl border border-white/10 bg-slate-950/35 p-5"><p className="text-xs font-black text-fuchsia-300">先归纳规则</p><p className="mt-2 text-base font-black leading-7 text-white">{lab.rule}</p><div className="mt-4 flex flex-wrap gap-2">{lab.forms.map((form) => <span key={form} className="rounded-xl border border-white/10 bg-white/[0.06] px-3 py-2 text-xs font-bold text-slate-200">{form}</span>)}</div></div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">{lab.examples.map((example) => <div key={example.en} className="rounded-2xl border border-white/10 bg-white/[0.05] p-4"><p className="text-sm font-black text-white">{example.en}</p><p className="mt-1 text-xs font-semibold text-slate-400">{example.zh}</p></div>)}</div>
        <div className="mt-4 flex items-start gap-3 rounded-2xl border border-amber-300/20 bg-amber-300/[0.07] p-4"><Lightbulb className="mt-0.5 size-4 shrink-0 text-amber-300" /><div><p className="text-xs font-black text-amber-300">最容易错</p><p className="mt-1 text-sm font-bold leading-6 text-slate-200">{lab.common_error}</p></div></div>
      </div>

      <div className="rounded-[2rem] border border-white/10 bg-white/[0.05] p-6 sm:p-8">
        <div className="flex items-end justify-between gap-4"><div><p className="text-xs font-black text-cyan-300">STEP 2 · 立即辨析</p><h3 className="mt-2 text-xl font-black">不是“看懂”，要连续选对</h3></div><span className="text-xs font-bold text-slate-500">已答 {answeredCount}/{lab.checks.length}</span></div>
        <div className="mt-5 space-y-4">{lab.checks.map((check, index) => {
          const selected = answers[check.id]
          const isCorrect = selected === check.answer
          return <article key={check.id} className="rounded-3xl border border-white/10 bg-slate-950/30 p-5 [content-visibility:auto]"><p className="text-sm font-black leading-6 text-white">{index + 1}. {check.prompt}</p><div className="mt-3 grid gap-2 sm:grid-cols-3">{check.options.map((option) => { const optionSelected = selected === option; const optionCorrect = option === check.answer; return <button key={option} type="button" onClick={() => onAnswer(check.id, option)} className={`rounded-2xl border px-4 py-3 text-left text-sm font-bold transition ${optionSelected && optionCorrect ? 'border-emerald-300/60 bg-emerald-400/15 text-emerald-100' : optionSelected ? 'border-rose-300/60 bg-rose-400/15 text-rose-100' : 'border-white/10 bg-white/[0.04] text-slate-300 hover:bg-white/[0.09]'}`}>{option}</button> })}</div>{selected ? <div className={`mt-3 flex items-start gap-2 rounded-2xl p-3 text-xs font-bold leading-5 ${isCorrect ? 'bg-emerald-400/10 text-emerald-200' : 'bg-rose-400/10 text-rose-200'}`}>{isCorrect ? <CircleCheck className="mt-0.5 size-4 shrink-0" /> : <CircleX className="mt-0.5 size-4 shrink-0" />}<span>{isCorrect ? '选对了。' : `再想一下，正确结构是“${check.answer}”。`}{check.explanation}</span></div> : null}</article>
        })}</div>
      </div>

      <div className="rounded-[2rem] border border-cyan-300/20 bg-cyan-400/[0.06] p-6 sm:p-8"><p className="text-xs font-black text-cyan-300">STEP 3 · 自己用出来</p><h3 className="mt-2 text-xl font-black">{lab.transfer_prompt}</h3><textarea value={transfer} onChange={(event) => onTransfer(event.target.value)} className="mt-4 min-h-28 w-full resize-y rounded-2xl border border-white/10 bg-slate-950/45 p-4 text-sm font-semibold text-white outline-none transition focus:border-cyan-300" placeholder="不要照抄例句，换成你自己的真实信息…" /><div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><p className="text-xs font-bold text-slate-400">{ready ? '语法证据已形成：规则辨析完成，并留下了自己的表达。' : '完成全部辨析题，并至少写 8 个字符的迁移表达。'}</p><Button disabled={!ready} onClick={onContinue}>保存掌握证据，继续课堂 <ArrowRight className="size-4" /></Button></div></div>
    </section>
  )
}
