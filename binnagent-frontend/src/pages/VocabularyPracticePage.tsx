import {
  ArrowLeft,
  BookOpen,
  Check,
  Headphones,
  Lightbulb,
  LoaderCircle,
  RotateCcw,
  Volume2,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { Learner } from '@/types'

export type VocabularyPracticeMode = 'review' | 'spelling'

interface VocabularyPracticePageProps {
  learner: Learner
  initialMode: VocabularyPracticeMode
  curriculumNodeId?: string | null
  sourceLabel?: string | null
  onExit: () => void
}

interface Pronunciation {
  accent: string
  phonetic?: string | null
  audio_url?: string | null
  kind: string
}

interface SourceTag {
  type: string
  label: string
  context: Record<string, unknown>
}

interface PracticeTask {
  completed: boolean
  session_id: string
  mode: VocabularyPracticeMode
  vocabulary_item_id: string
  current_index: number
  total: number
  answer_length: number
  phonetic?: string | null
  pronunciations: Pronunciation[]
  tts_text?: string | null
  context_with_blank?: string | null
  sources: SourceTag[]
  word?: string
  meaning?: string | null
  example?: string | null
}

interface AttemptFeedback {
  result: 'correct' | 'incorrect' | 'revealed'
  correct_answer: string
  phonetic?: string | null
  meaning?: string | null
  example?: string | null
  feedback_text: string
  letter_diff: Array<{ answer?: string | null; correct?: string | null; status: string }>
  can_retry: boolean
}

interface SessionSummary {
  total: number
  completed: number
  correct: number
  hinted: number
  revealed: number
  due_next: number
}

const counts = [5, 10, 15]

export function VocabularyPracticePage({
  learner,
  initialMode,
  curriculumNodeId,
  sourceLabel,
  onExit,
}: VocabularyPracticePageProps) {
  const [mode, setMode] = useState<VocabularyPracticeMode>(initialMode)
  const [limit, setLimit] = useState(10)
  const [accent, setAccent] = useState<'uk' | 'us' | 'auto'>('uk')
  const [phase, setPhase] = useState<'setup' | 'loading' | 'practice' | 'summary'>('setup')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [task, setTask] = useState<PracticeTask | null>(null)
  const [answer, setAnswer] = useState('')
  const [feedback, setFeedback] = useState<AttemptFeedback | null>(null)
  const [hint, setHint] = useState<string | null>(null)
  const [hintCount, setHintCount] = useState(0)
  const [replayCount, setReplayCount] = useState(0)
  const [summary, setSummary] = useState<SessionSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isBusy, setIsBusy] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isComposing, setIsComposing] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const startedAt = useRef(0)

  const api = `/api/learners/${learner.id}/vocabulary`

  const loadTask = useCallback(async (id: string) => {
    const response = await fetch(`${api}/sessions/${id}/next`)
    if (!response.ok) throw new Error('下一题暂时无法加载。')
    const data = await response.json() as PracticeTask & { summary?: SessionSummary }
    if (data.completed) {
      setSummary(data.summary ?? null)
      setPhase('summary')
      return
    }
    setTask(data)
    setAnswer('')
    setFeedback(null)
    setHint(null)
    setHintCount(0)
    setReplayCount(0)
    startedAt.current = Date.now()
    setPhase('practice')
    window.setTimeout(() => inputRef.current?.focus(), 40)
  }, [api])

  const startPractice = async () => {
    setPhase('loading')
    setError(null)
    try {
      const response = await fetch(`${api}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode,
          prompt_mode: mode === 'spelling' ? 'audio' : 'meaning',
          accent,
          curriculum_node_id: curriculumNodeId ?? null,
          limit,
        }),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => null) as { detail?: string } | null
        throw new Error(body?.detail ?? '练习暂时无法开始。')
      }
      const session = await response.json() as { session_id: string }
      setSessionId(session.session_id)
      await loadTask(session.session_id)
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : '练习暂时无法开始。')
      setPhase('setup')
    }
  }

  const playAudio = useCallback(async () => {
    if (!task) return
    setReplayCount((count) => count + 1)
    const recording = task.pronunciations.find((item) => item.audio_url)
    setIsPlaying(true)
    try {
      if (recording?.audio_url) {
        const audio = new Audio(recording.audio_url)
        audio.playbackRate = 0.9
        audio.onended = () => setIsPlaying(false)
        audio.onerror = () => setIsPlaying(false)
        await audio.play()
      } else if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel()
        const utterance = new SpeechSynthesisUtterance(task.tts_text ?? feedback?.correct_answer ?? '')
        utterance.lang = accent === 'us' ? 'en-US' : 'en-GB'
        utterance.rate = 0.86
        utterance.onend = () => setIsPlaying(false)
        window.speechSynthesis.speak(utterance)
      } else {
        setIsPlaying(false)
      }
    } catch {
      setIsPlaying(false)
      if (task.tts_text && 'speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(task.tts_text)
        utterance.lang = accent === 'us' ? 'en-US' : 'en-GB'
        window.speechSynthesis.speak(utterance)
      }
    }
  }, [accent, feedback, task])

  const submitAttempt = async (options?: { reveal?: boolean; rating?: number }) => {
    if (!task || !sessionId || isBusy) return
    if (mode === 'spelling' && !options?.reveal && !answer.trim()) {
      setError('先试着拼一下。')
      inputRef.current?.focus()
      return
    }
    setIsBusy(true)
    setError(null)
    try {
      const response = await fetch(`${api}/sessions/${sessionId}/attempts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          vocabulary_item_id: task.vocabulary_item_id,
          idempotency_key: crypto.randomUUID(),
          action: options?.reveal ? 'reveal' : 'submit',
          answer: mode === 'spelling' ? answer : null,
          rating: options?.rating ?? null,
          response_time_ms: Date.now() - startedAt.current,
          hint_count: hintCount,
          replay_count: replayCount,
        }),
      })
      if (!response.ok) throw new Error('学习记录保存失败，请重试。')
      setFeedback(await response.json() as AttemptFeedback)
    } catch (attemptError) {
      setError(attemptError instanceof Error ? attemptError.message : '提交失败。')
    } finally {
      setIsBusy(false)
    }
  }

  const advance = async () => {
    if (!task || !sessionId || isBusy) return
    setIsBusy(true)
    try {
      const response = await fetch(`${api}/sessions/${sessionId}/advance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vocabulary_item_id: task.vocabulary_item_id }),
      })
      if (!response.ok) throw new Error('进度保存失败。')
      const data = await response.json() as SessionSummary
      if (data.completed >= data.total) {
        setSummary(data)
        setPhase('summary')
      } else {
        await loadTask(sessionId)
      }
    } catch (advanceError) {
      setError(advanceError instanceof Error ? advanceError.message : '下一题暂时无法加载。')
    } finally {
      setIsBusy(false)
    }
  }

  const requestHint = async () => {
    if (!sessionId || hintCount >= 3) return
    const nextLevel = hintCount + 1
    const response = await fetch(`${api}/sessions/${sessionId}/hint?level=${nextLevel}`, { method: 'POST' })
    if (!response.ok) return
    const data = await response.json() as { hint: string }
    setHintCount(nextLevel)
    setHint(data.hint)
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (phase !== 'practice') return
      if (event.code === 'Space' && document.activeElement !== inputRef.current) {
        event.preventDefault()
        void playAudio()
      }
      if (event.key === 'Enter' && !isComposing) {
        event.preventDefault()
        if (feedback) void advance()
        else if (mode === 'spelling') void submitAttempt()
      }
      if (event.key === 'Escape') onExit()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  })

  if (phase === 'setup') {
    return (
      <div className="min-h-screen bg-[#f7f8fc] px-4 py-8 sm:py-14">
        <div className="mx-auto max-w-2xl">
          <button onClick={onExit} className="inline-flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-indigo-600"><ArrowLeft className="size-4" />返回学习中心</button>
          <section className="mt-8 rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_20px_60px_rgba(30,41,59,0.08)] sm:p-10">
            <div className="flex size-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">{mode === 'spelling' ? <Headphones className="size-7" /> : <BookOpen className="size-7" />}</div>
            <h1 className="mt-5 text-3xl font-black text-slate-950">{mode === 'spelling' ? '拼写练习' : '沉浸式背单词'}</h1>
            <p className="mt-2 text-sm leading-6 text-slate-500">每次只专注一个词，发音、回忆与反馈都在同一个安静空间里完成。</p>
            <SetupGroup label="练习方式">
              <Choice selected={mode === 'review'} onClick={() => setMode('review')}>词义复习</Choice>
              <Choice selected={mode === 'spelling'} onClick={() => setMode('spelling')}>听音拼写</Choice>
            </SetupGroup>
            <SetupGroup label="词汇来源">
              <div className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm font-bold text-indigo-700">{sourceLabel ?? (curriculumNodeId ? '当前教材单元' : '全部待学词汇')}</div>
            </SetupGroup>
            <SetupGroup label="本组数量">
              {counts.map((count) => <Choice key={count} selected={limit === count} onClick={() => setLimit(count)}>{count} 个</Choice>)}
            </SetupGroup>
            <SetupGroup label="发音偏好">
              <Choice selected={accent === 'uk'} onClick={() => setAccent('uk')}>英音</Choice>
              <Choice selected={accent === 'us'} onClick={() => setAccent('us')}>美音</Choice>
              <Choice selected={accent === 'auto'} onClick={() => setAccent('auto')}>跟随词典</Choice>
            </SetupGroup>
            {error ? <p className="mt-5 rounded-xl bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-800">{error}</p> : null}
            <button onClick={() => void startPractice()} className="mt-8 w-full rounded-xl bg-indigo-600 px-5 py-3.5 text-sm font-black text-white shadow-lg shadow-indigo-200 transition hover:bg-indigo-700">开始练习</button>
          </section>
        </div>
      </div>
    )
  }

  if (phase === 'loading') {
    return <div className="flex min-h-screen flex-col items-center justify-center bg-[#f7f8fc] text-sm font-bold text-slate-500"><LoaderCircle className="mb-4 size-7 animate-spin text-indigo-600" />正在准备词汇和发音…</div>
  }

  if (phase === 'summary' && summary) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f7f8fc] p-4">
        <section className="w-full max-w-xl rounded-[28px] border border-slate-200 bg-white p-8 text-center shadow-[0_20px_60px_rgba(30,41,59,0.08)] sm:p-12">
          <div className="mx-auto flex size-16 items-center justify-center rounded-full bg-emerald-50 text-emerald-600"><Check className="size-8" /></div>
          <h1 className="mt-6 text-3xl font-black text-slate-950">本组完成</h1>
          <p className="mt-3 text-slate-500">完成 {summary.total} 个词，独立答对 {summary.correct} 个。</p>
          <div className="mt-8 grid grid-cols-3 gap-3">
            <SummaryMetric label="答对" value={summary.correct} />
            <SummaryMetric label="用过提示" value={summary.hinted} />
            <SummaryMetric label="查看答案" value={summary.revealed} />
          </div>
          <button onClick={onExit} className="mt-8 w-full rounded-xl bg-indigo-600 px-5 py-3.5 text-sm font-black text-white">返回背单词</button>
        </section>
      </div>
    )
  }

  if (!task) return null
  const progress = ((task.current_index + 1) / task.total) * 100
  return (
    <div className="flex min-h-screen flex-col bg-[#fbfbfd] text-slate-950">
      <header className="border-b border-slate-200 bg-white px-4 py-4 sm:px-8">
        <div className="mx-auto flex max-w-5xl items-center gap-5">
          <button onClick={onExit} className="inline-flex shrink-0 items-center gap-2 text-sm font-bold text-slate-500 hover:text-indigo-600"><ArrowLeft className="size-4" />退出练习</button>
          <div className="mx-auto flex w-full max-w-xl items-center gap-3"><div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-indigo-600 transition-all" style={{ width: `${progress}%` }} /></div><span className="text-xs font-black text-slate-500">{task.current_index + 1} / {task.total}</span></div>
          <span className="hidden shrink-0 rounded-full bg-indigo-50 px-3 py-1.5 text-xs font-black text-indigo-700 sm:inline">{task.sources[0]?.label ?? sourceLabel ?? '我的词汇本'}</span>
        </div>
      </header>

      <main className="flex flex-1 items-center justify-center px-4 py-10 sm:py-14">
        <section className="w-full max-w-[820px] text-center">
          <p className="text-sm font-black uppercase tracking-[0.18em] text-indigo-600">{feedback ? (feedback.result === 'correct' ? '拼对了' : feedback.result === 'revealed' ? '先记住答案' : '差一点，再看看') : mode === 'spelling' ? '听发音，拼出这个词' : '认识这个词吗？'}</p>
          <button onClick={() => void playAudio()} aria-label="播放发音" className={`mx-auto mt-7 flex size-24 items-center justify-center rounded-full bg-indigo-600 text-white shadow-[0_14px_36px_rgba(79,70,229,0.28)] transition hover:scale-[1.03] ${isPlaying ? 'ring-8 ring-indigo-100' : ''}`}><Volume2 className="size-10" /></button>
          <p className="mt-3 text-xs font-bold text-slate-400">点击播放 · 空格键重播 · {accent === 'us' ? '美音' : '英音'}</p>

          {mode === 'review' ? (
            <div className="mt-10">
              <h1 className="text-5xl font-black tracking-tight sm:text-6xl">{task.word}</h1>
              {task.phonetic ? <p className="mt-3 text-lg text-slate-400">{task.phonetic}</p> : null}
              <div className="mx-auto mt-8 max-w-xl rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm"><p className="text-lg font-bold text-slate-800">{task.meaning ?? '暂无释义'}</p>{task.example ? <p className="mt-3 text-sm text-slate-500">{task.example}</p> : null}</div>
            </div>
          ) : feedback ? (
            <FeedbackPanel feedback={feedback} />
          ) : (
            <div className="mx-auto mt-10 max-w-2xl">
              <label className="relative block cursor-text" onClick={() => inputRef.current?.focus()}>
                <input ref={inputRef} value={answer} onChange={(event) => setAnswer(event.target.value)} onCompositionStart={() => setIsComposing(true)} onCompositionEnd={() => setIsComposing(false)} autoCapitalize="none" autoComplete="off" spellCheck={false} className="absolute inset-0 h-full w-full cursor-text opacity-0" aria-label="拼写答案" />
                <div className="flex min-h-16 flex-wrap items-end justify-center gap-2" aria-hidden="true">
                  {Array.from({ length: Math.max(task.answer_length, answer.length) }, (_, index) => <span key={index} className={`flex h-14 min-w-10 items-center justify-center border-b-2 text-3xl font-black ${answer[index] ? 'border-indigo-500 text-slate-950' : 'border-slate-300 text-transparent'}`}>{answer[index] ?? '·'}</span>)}
                </div>
              </label>
              {error ? <p className="mt-4 text-sm font-bold text-amber-700">{error}</p> : null}
              <div className="mt-8 flex flex-wrap items-center justify-center gap-4 text-sm font-bold"><button onClick={() => void requestHint()} disabled={hintCount >= 3} className="inline-flex items-center gap-2 text-indigo-600 disabled:text-slate-300"><Lightbulb className="size-4" />{hintCount ? `再给一点提示 ${hintCount}/3` : '给我一个提示'}</button><span className="text-slate-300">|</span><button onClick={() => void submitAttempt({ reveal: true })} className="text-slate-500 hover:text-slate-800">不认识，先看答案</button></div>
              {hint ? <p className="mx-auto mt-5 max-w-xl rounded-xl bg-indigo-50 px-4 py-3 text-sm font-semibold text-indigo-800">{hint}</p> : null}
              {task.context_with_blank ? <p className="mt-5 text-sm text-slate-500">{task.context_with_blank}</p> : null}
            </div>
          )}

          <p className="mt-10 text-xs font-semibold text-slate-400">来自 {task.sources[0]?.label ?? sourceLabel ?? '我的词汇本'}</p>
        </section>
      </main>

      <footer className="border-t border-slate-200 bg-white px-4 py-5 sm:px-8">
        <div className="mx-auto flex max-w-5xl flex-col-reverse items-stretch justify-between gap-3 sm:flex-row sm:items-center">
          <span className="hidden text-xs font-semibold text-slate-400 sm:block">{feedback ? 'Enter 进入下一词' : mode === 'spelling' ? 'Enter 检查拼写' : '根据回忆程度选择'}</span>
          {feedback ? (
            <div className="flex gap-3 sm:ml-auto">{feedback.can_retry ? <button onClick={() => { setFeedback(null); setAnswer(''); inputRef.current?.focus(); void playAudio() }} className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-200 px-5 py-3 text-sm font-black text-slate-700"><RotateCcw className="size-4" />再拼一次</button> : null}<button onClick={() => void advance()} disabled={isBusy} className="flex-1 rounded-xl bg-indigo-600 px-7 py-3 text-sm font-black text-white disabled:opacity-60">下一个</button></div>
          ) : mode === 'review' ? (
            <div className="grid grid-cols-4 gap-2 sm:ml-auto"><RatingButton label="忘了" onClick={() => void submitAttempt({ rating: 1 })} /><RatingButton label="模糊" onClick={() => void submitAttempt({ rating: 2 })} /><RatingButton label="记得" onClick={() => void submitAttempt({ rating: 3 })} /><RatingButton label="熟练" primary onClick={() => void submitAttempt({ rating: 4 })} /></div>
          ) : <button onClick={() => void submitAttempt()} disabled={isBusy} className="rounded-xl bg-indigo-600 px-8 py-3 text-sm font-black text-white disabled:opacity-60">{isBusy ? '正在检查…' : '检查拼写'}</button>}
        </div>
      </footer>
    </div>
  )
}

function SetupGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="mt-7"><p className="mb-3 text-sm font-black text-slate-800">{label}</p><div className="flex flex-wrap gap-2">{children}</div></div>
}

function Choice({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" onClick={onClick} className={`rounded-xl border px-4 py-2.5 text-sm font-bold transition ${selected ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-slate-200 bg-white text-slate-600 hover:border-indigo-200'}`}>{children}</button>
}

function FeedbackPanel({ feedback }: { feedback: AttemptFeedback }) {
  const success = feedback.result === 'correct'
  return <div className="mx-auto mt-9 max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><div className="flex flex-wrap justify-center gap-1 font-mono text-4xl font-black">{feedback.letter_diff.length ? feedback.letter_diff.map((letter, index) => <span key={index} className={letter.status === 'match' ? 'text-emerald-600' : 'text-orange-500'}>{letter.correct ?? letter.answer}</span>) : <span className={success ? 'text-emerald-600' : 'text-slate-950'}>{feedback.correct_answer}</span>}</div>{feedback.phonetic ? <p className="mt-3 text-slate-400">{feedback.phonetic}</p> : null}<p className={`mt-5 text-base font-black ${success ? 'text-emerald-700' : 'text-orange-700'}`}>{feedback.feedback_text}</p>{feedback.meaning ? <p className="mt-3 text-sm text-slate-600">{feedback.meaning}</p> : null}{feedback.example ? <p className="mt-2 text-sm text-slate-400">{feedback.example}</p> : null}</div>
}

function SummaryMetric({ label, value }: { label: string; value: number }) {
  return <div className="rounded-xl bg-slate-50 px-3 py-4"><strong className="text-2xl font-black text-slate-950">{value}</strong><p className="mt-1 text-xs font-bold text-slate-500">{label}</p></div>
}

function RatingButton({ label, primary, onClick }: { label: string; primary?: boolean; onClick: () => void }) {
  return <button onClick={onClick} className={`rounded-xl px-4 py-3 text-sm font-black ${primary ? 'bg-indigo-600 text-white' : 'border border-slate-200 bg-white text-slate-700 hover:border-indigo-300'}`}>{label}</button>
}
