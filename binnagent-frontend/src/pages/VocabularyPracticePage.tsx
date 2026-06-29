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
import {
  RichVocabularyEntry,
  type BilingualMeaning,
  type DictionarySense,
} from '@/components/vocabulary/RichVocabularyEntry'
import { VocabularyDetailPage } from '@/pages/VocabularyDetailPage'

export type VocabularyPracticeMode = 'new' | 'review' | 'spelling'

interface VocabularyPracticePageProps {
  learner: Learner
  initialMode: VocabularyPracticeMode
  curriculumNodeId?: string | null
  sourceLabel?: string | null
  readonlyItemId?: string | null
  readonlyBackLabel?: string
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
  phonetic_uk?: string | null
  phonetic_us?: string | null
  part_of_speech: string
  dictionary_senses: DictionarySense[]
  word_forms: Record<string, string[]>
  dictionary_tags: string[]
  meanings: BilingualMeaning[]
  examples: Array<string | Record<string, unknown>>
  mastery?: Record<string, number>
  show_answer_first?: boolean
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
  phonetic_uk?: string | null
  phonetic_us?: string | null
  part_of_speech: string
  dictionary_senses: DictionarySense[]
  word_forms: Record<string, string[]>
  dictionary_tags: string[]
  meanings: BilingualMeaning[]
  examples: Array<string | Record<string, unknown>>
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

interface VocabularyItemDetail {
  id: string
  word: string
  phonetic?: string | null
  phonetic_uk?: string | null
  phonetic_us?: string | null
  audio_url?: string | null
  audio_uk?: string | null
  audio_us?: string | null
  dictionary_senses: DictionarySense[]
  word_forms: Record<string, string[]>
  dictionary_tags: string[]
  meanings: BilingualMeaning[]
  examples: Array<string | Record<string, unknown>>
  sources: SourceTag[]
  mastery?: Record<string, number>
}

const counts = [5, 10, 15]
const ENGLISH_SPELLING_PATTERN = /^[A-Za-z' -]*$/

export function VocabularyPracticePage({
  learner,
  initialMode,
  curriculumNodeId,
  sourceLabel,
  readonlyItemId,
  readonlyBackLabel = '返回',
  onExit,
}: VocabularyPracticePageProps) {
  const [mode, setMode] = useState<VocabularyPracticeMode>(initialMode)
  const [limit, setLimit] = useState(10)
  const [isCustomLimit, setIsCustomLimit] = useState(false)
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
  const [inputWarning, setInputWarning] = useState<string | null>(null)
  const [availableTotal, setAvailableTotal] = useState<number | null>(null)
  const [detailTerm, setDetailTerm] = useState<string | null>(null)
  const [shouldRefreshAfterDetail, setShouldRefreshAfterDetail] = useState(false)
  const [readonlyDetail, setReadonlyDetail] = useState<VocabularyItemDetail | null>(null)
  const [isReviewRevealed, setIsReviewRevealed] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const startedAt = useRef(0)
  const compositionRef = useRef(false)
  const autoJudgeTimer = useRef<number | null>(null)
  const lastAutoSubmitted = useRef('')

  const api = `/api/learners/${learner.id}/vocabulary`

  const loadAvailableTotal = useCallback((signal?: AbortSignal) => {
    const url = curriculumNodeId ? `${api}/units/${curriculumNodeId}/summary` : api
    return fetch(url, { signal })
      .then((response) => response.ok ? response.json() as Promise<{ total: number } | Array<{ status: string }>> : null)
      .then((data) => {
        if (Array.isArray(data)) setAvailableTotal(data.filter((item) => item.status !== 'mastered').length)
        else setAvailableTotal(data?.total ?? null)
      })
      .catch((fetchError: unknown) => {
        if (!(fetchError instanceof DOMException && fetchError.name === 'AbortError')) setAvailableTotal(null)
      })
  }, [api, curriculumNodeId])

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
    setIsReviewRevealed(data.mode === 'new' || data.show_answer_first === true)
    setInputWarning(null)
    lastAutoSubmitted.current = ''
    startedAt.current = Date.now()
    setPhase('practice')
    window.setTimeout(() => inputRef.current?.focus(), 40)
  }, [api])

  useEffect(() => {
    if (readonlyItemId) return
    const controller = new AbortController()
    void loadAvailableTotal(controller.signal)
    return () => controller.abort()
  }, [loadAvailableTotal, readonlyItemId])

  useEffect(() => {
    if (!readonlyItemId) return
    const controller = new AbortController()
    fetch(`${api}/${readonlyItemId}`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('词条暂时无法加载。')
        return response.json() as Promise<VocabularyItemDetail>
      })
      .then((detail) => setReadonlyDetail(detail))
      .catch((fetchError: unknown) => {
        if (!(fetchError instanceof DOMException && fetchError.name === 'AbortError')) {
          setError(fetchError instanceof Error ? fetchError.message : '词条暂时无法加载。')
        }
      })
    return () => controller.abort()
  }, [api, readonlyItemId])

  useEffect(() => () => {
    if (autoJudgeTimer.current !== null) window.clearTimeout(autoJudgeTimer.current)
  }, [])

  const startPractice = async () => {
    setPhase('loading')
    setError(null)
    try {
      const response = await fetch(`${api}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode,
          prompt_mode: mode === 'spelling' ? 'audio' : mode === 'new' ? 'context' : 'meaning',
          accent,
          curriculum_node_id: curriculumNodeId ?? null,
          limit: availableTotal ? Math.min(limit, availableTotal) : limit,
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

  const playAudio = useCallback(async (accentOverride?: 'uk' | 'us') => {
    if (!task) return
    const requestedAccent = accentOverride ?? (accent === 'auto' ? 'uk' : accent)
    if (accentOverride) setAccent(accentOverride)
    setReplayCount((count) => count + 1)
    const recording = task.pronunciations.find((item) => (
      item.audio_url && item.accent.toLowerCase().includes(requestedAccent)
    )) ?? task.pronunciations.find((item) => item.audio_url)
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
        utterance.lang = requestedAccent === 'us' ? 'en-US' : 'en-GB'
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
        utterance.lang = requestedAccent === 'us' ? 'en-US' : 'en-GB'
        window.speechSynthesis.speak(utterance)
      }
    }
  }, [accent, feedback, task])

  const submitAttempt = async (options?: { reveal?: boolean; rating?: number; answerOverride?: string }) => {
    if (!task || !sessionId || isBusy) return null
    const submittedAnswer = options?.answerOverride ?? answer
    if (mode === 'spelling' && !options?.reveal && !submittedAnswer.trim()) {
      setError('先试着拼一下。')
      inputRef.current?.focus()
      return null
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
          answer: mode === 'spelling' ? submittedAnswer : null,
          rating: options?.rating ?? null,
          response_time_ms: Date.now() - startedAt.current,
          hint_count: hintCount,
          replay_count: replayCount,
        }),
      })
      if (!response.ok) throw new Error('学习记录保存失败，请重试。')
      const nextFeedback = await response.json() as AttemptFeedback
      setFeedback(nextFeedback)
      return nextFeedback
    } catch (attemptError) {
      setError(attemptError instanceof Error ? attemptError.message : '提交失败。')
      return null
    } finally {
      setIsBusy(false)
    }
  }

  const handleAnswerChange = (value: string) => {
    setAnswer(value)
    setError(null)
    if (autoJudgeTimer.current !== null) window.clearTimeout(autoJudgeTimer.current)
    if (!ENGLISH_SPELLING_PATTERN.test(value)) {
      setInputWarning('检测到非英文字符，请切换到英文输入法后继续。')
      return
    }
    setInputWarning(null)
    if (
      !compositionRef.current &&
      !feedback &&
      !isBusy &&
      task &&
      value.length === task.answer_length &&
      value !== lastAutoSubmitted.current
    ) {
      autoJudgeTimer.current = window.setTimeout(() => {
        lastAutoSubmitted.current = value
        void submitAttempt({ answerOverride: value })
      }, 260)
    }
  }

  const retrySpelling = () => {
    setFeedback(null)
    setAnswer('')
    setError(null)
    setInputWarning(null)
    lastAutoSubmitted.current = ''
    window.setTimeout(() => inputRef.current?.focus(), 40)
    void playAudio()
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

  const rateAndAdvance = async (rating: 1 | 2 | 3 | 4) => {
    const attempt = await submitAttempt({ rating })
    if (attempt) await advance()
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
      if (detailTerm) return
      if (readonlyItemId) {
        if (event.key === 'Escape') onExit()
        return
      }
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
      if ((mode === 'review' || mode === 'new') && isReviewRevealed && !feedback && ['1', '2', '3', '4'].includes(event.key)) {
        event.preventDefault()
        void rateAndAdvance(Number(event.key) as 1 | 2 | 3 | 4)
      }
      if (event.key === 'Escape') onExit()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  })

  if (readonlyItemId) {
    return (
      <ReadonlyVocabularyDetail
        detail={readonlyDetail}
        error={error}
        isLoading={readonlyDetail?.id !== readonlyItemId && !error}
        sourceLabel={sourceLabel ?? '我的词汇本'}
        backLabel={readonlyBackLabel}
        onBack={onExit}
      />
    )
  }

  if (detailTerm) {
    return (
      <VocabularyDetailPage
        learner={learner}
        term={detailTerm}
        onBack={() => {
          setDetailTerm(null)
          if (!shouldRefreshAfterDetail) return
          setShouldRefreshAfterDetail(false)
          void loadAvailableTotal()
          if (sessionId) void loadTask(sessionId)
        }}
        onVocabularyChanged={() => setShouldRefreshAfterDetail(true)}
      />
    )
  }

  if (phase === 'setup') {
    return (
      <div className="min-h-screen bg-[#f7f8fc] px-4 py-8 sm:py-14">
        <div className="mx-auto max-w-2xl">
          <button onClick={onExit} className="inline-flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-indigo-600"><ArrowLeft className="size-4" />返回学习中心</button>
          <section className="mt-8 rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_20px_60px_rgba(30,41,59,0.08)] sm:p-10">
            <div className="flex size-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">{mode === 'spelling' ? <Headphones className="size-7" /> : <BookOpen className="size-7" />}</div>
            <h1 className="mt-5 text-3xl font-black text-slate-950">{mode === 'new' ? '认识新词' : mode === 'spelling' ? '拼写练习' : '今日复习'}</h1>
            <p className="mt-2 text-sm leading-6 text-slate-500">{mode === 'new' ? '先建立理解和第一印象，允许看提示和答案。' : mode === 'review' ? '默认隐藏答案，先主动回忆，再按真实熟悉度安排复习。' : '听音主动拼写，获得字母级反馈。'}</p>
            <SetupGroup label="练习方式">
              <Choice selected={mode === 'new'} onClick={() => setMode('new')}>认识新词</Choice>
              <Choice selected={mode === 'review'} onClick={() => setMode('review')}>今日复习</Choice>
              <Choice selected={mode === 'spelling'} onClick={() => setMode('spelling')}>听音拼写</Choice>
            </SetupGroup>
            <SetupGroup label="词汇来源">
              <div className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm font-bold text-indigo-700">{sourceLabel ?? (curriculumNodeId ? '当前教材单元' : '全部待学词汇')}{availableTotal !== null ? <span className="ml-2 text-indigo-500">共 {availableTotal} 词</span> : null}</div>
            </SetupGroup>
            <SetupGroup label="本组数量">
              {counts.filter((count) => availableTotal === null || count <= availableTotal).map((count) => <Choice key={count} selected={!isCustomLimit && limit === count} onClick={() => { setLimit(count); setIsCustomLimit(false) }}>{count} 个</Choice>)}
              <Choice selected={isCustomLimit} onClick={() => { setLimit((current) => Math.min(current, availableTotal ?? current)); setIsCustomLimit(true) }}>自定义</Choice>
              {isCustomLimit ? <label className="inline-flex items-center gap-2 rounded-xl border border-indigo-300 bg-white px-3 py-1.5 text-sm font-bold text-slate-600"><input type="number" min={1} max={availableTotal ?? undefined} value={limit} onChange={(event) => setLimit(Math.max(1, Math.min(availableTotal ?? Number.MAX_SAFE_INTEGER, Number(event.target.value) || 1)))} className="w-14 bg-transparent text-center text-slate-950 outline-none" aria-label="自定义本组数量" />个{availableTotal !== null ? <span className="text-xs text-slate-400">（1–{availableTotal}）</span> : null}</label> : null}
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
  const learnMoreTerm = mode === 'review' || mode === 'new' ? task.word : feedback?.correct_answer
  const progress = ((task.current_index + 1) / task.total) * 100
  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-[#fbfbfd] text-slate-950">
      <header className="shrink-0 border-b border-slate-200 bg-white px-4 py-3 sm:px-8">
        <div className="mx-auto flex max-w-[1420px] items-center gap-5">
          <button onClick={onExit} className="inline-flex shrink-0 items-center gap-2 text-sm font-bold text-slate-500 hover:text-indigo-600"><ArrowLeft className="size-4" />退出练习</button>
          <div className="mx-auto flex w-full max-w-xl items-center gap-3"><div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-indigo-600 transition-all" style={{ width: `${progress}%` }} /></div><span className="text-xs font-black text-slate-500">{task.current_index + 1} / {task.total}</span></div>
          <span className="hidden shrink-0 text-sm font-bold text-slate-600 sm:inline">
            {mode === 'new' ? '新词学习' : mode === 'review' ? '今日复习' : '拼写练习'} · {task.sources[0]?.label ?? sourceLabel ?? '我的词汇本'}
          </span>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-hidden px-4 py-3 sm:px-6 sm:py-4">
        <section className="mx-auto grid h-full w-full max-w-[1420px] grid-rows-[minmax(0,1fr)_auto] gap-3 lg:grid-cols-[minmax(0,1fr)_320px] lg:grid-rows-1">
          <section className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="shrink-0 border-b border-slate-100 px-4 py-3 sm:px-5">
              <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-600">当前任务</p>
            </div>
            <div className={`min-h-0 flex-1 overflow-y-auto p-4 sm:p-5 ${mode === 'review' && isReviewRevealed ? '' : 'flex items-center justify-center text-center'}`}>
              <div className="w-full">
                {mode === 'spelling' ? <><p className="text-sm font-black uppercase tracking-[0.18em] text-indigo-600">{feedback ? (feedback.result === 'correct' ? '拼对了' : feedback.result === 'revealed' ? '先记住答案' : '差一点，再看看') : '听发音，拼出这个词'}</p><button onClick={() => void playAudio()} aria-label="播放发音" className={`mx-auto mt-5 flex size-20 items-center justify-center rounded-full bg-indigo-600 text-white shadow-[0_14px_36px_rgba(79,70,229,0.28)] transition hover:scale-[1.03] sm:size-24 ${isPlaying ? 'ring-8 ring-indigo-100' : ''}`}><Volume2 className="size-9 sm:size-10" /></button><p className="mt-3 text-xs font-bold text-slate-400">点击播放 · 空格键重播 · {accent === 'us' ? '美音' : '英音'}</p></> : null}

                {(mode === 'review' || mode === 'new') && isReviewRevealed ? (
                  <RichVocabularyEntry
                    word={task.word ?? ''}
                    phonetic={task.phonetic}
                    phoneticUk={task.phonetic_uk}
                    phoneticUs={task.phonetic_us}
                    senses={task.dictionary_senses}
                    meanings={task.meanings}
                    examples={task.examples}
                    wordForms={task.word_forms}
                    tags={task.dictionary_tags}
                    activeAccent={accent}
                    onPlayAccent={(nextAccent) => void playAudio(nextAccent)}
                  />
                ) : mode === 'review' ? (
                  <div className="mx-auto max-w-2xl">
                    <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-600">先主动回忆</p>
                    <h1 className="mt-4 text-4xl font-black text-slate-950 sm:text-5xl">{task.word}</h1>
                    {task.phonetic ? <p className="mt-3 text-lg font-semibold text-slate-400">{task.phonetic}</p> : null}
                    <div className="mt-6 flex flex-wrap justify-center gap-3">
                      <button type="button" onClick={() => void playAudio()} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-black text-slate-700 hover:border-indigo-200"><Volume2 className="size-4" />播放发音</button>
                      <button type="button" onClick={() => setIsReviewRevealed(true)} className="rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-black text-white hover:bg-indigo-700">显示答案</button>
                    </div>
                    {hint ? <p className="mx-auto mt-5 max-w-xl rounded-xl bg-indigo-50 px-4 py-3 text-sm font-semibold text-indigo-800">{hint}</p> : null}
                  </div>
                ) : feedback ? (
                  <FeedbackPanel feedback={feedback} />
                ) : (
                  <div className="mx-auto max-w-2xl">
                    <label className="relative block cursor-text" onClick={() => inputRef.current?.focus()}>
                      <input ref={inputRef} value={answer} onChange={(event) => handleAnswerChange(event.target.value)} onCompositionStart={() => { compositionRef.current = true; setIsComposing(true); setInputWarning('正在使用输入法，请切换到英文输入后再提交。') }} onCompositionEnd={(event) => { compositionRef.current = false; setIsComposing(false); handleAnswerChange(event.currentTarget.value) }} lang="en" inputMode="text" autoCapitalize="none" autoCorrect="off" autoComplete="off" spellCheck={false} className="absolute inset-0 h-full w-full cursor-text opacity-0" aria-label="拼写答案" />
                      <div className="flex min-h-16 flex-wrap items-end justify-center gap-2" aria-hidden="true">
                        {Array.from({ length: Math.max(task.answer_length, answer.length) }, (_, index) => <span key={index} className={`flex h-14 min-w-10 items-center justify-center border-b-2 text-3xl font-black ${answer[index] ? 'border-indigo-500 text-slate-950' : 'border-slate-300 text-transparent'}`}>{answer[index] ?? '·'}</span>)}
                      </div>
                    </label>
                    {error ? <p className="mt-4 text-sm font-bold text-amber-700">{error}</p> : null}
                    <p className={`mt-4 text-xs font-bold ${inputWarning ? 'text-orange-600' : 'text-slate-400'}`}>{inputWarning ?? '请使用英文键盘输入；填满字母后会自动检查。'}</p>
                    {hint ? <p className="mx-auto mt-5 max-w-xl rounded-xl bg-indigo-50 px-4 py-3 text-sm font-semibold text-indigo-800">{hint}</p> : null}
                  </div>
                )}
              </div>
            </div>
          </section>

          <TaskSupportPanel
            feedback={feedback}
            hintCount={hintCount}
            isReviewRevealed={isReviewRevealed}
            learnMoreTerm={learnMoreTerm}
            mode={mode}
            sourceLabel={task.sources[0]?.label ?? sourceLabel ?? '我的词汇本'}
            onEditTerm={() => learnMoreTerm && setDetailTerm(learnMoreTerm)}
            onHint={() => void requestHint()}
            onReveal={() => {
              if (mode === 'review' && !isReviewRevealed) setIsReviewRevealed(true)
              else void submitAttempt({ reveal: true })
            }}
          />
        </section>
      </main>

      <footer className="shrink-0 border-t border-slate-200 bg-white px-4 py-3 shadow-[0_-10px_30px_rgba(15,23,42,0.04)] sm:px-8">
        <div className="mx-auto flex max-w-[1420px] flex-col-reverse items-stretch justify-between gap-3 sm:flex-row sm:items-center">
          <span className={`text-xs font-semibold ${error ? 'block text-rose-600' : 'hidden text-slate-400 sm:block'}`}>{error ?? (feedback ? (feedback.result === 'revealed' ? '可以隐藏答案再拼一次' : 'Enter 进入下一词') : mode === 'spelling' ? '填满后自动检查，也可按 Enter' : mode === 'review' && !isReviewRevealed ? '先回忆，再显示答案评分' : '评分后自动进入下一词')}</span>
          {feedback ? (
            <div className="flex gap-3 sm:ml-auto">{mode === 'spelling' && (feedback.can_retry || feedback.result === 'revealed') ? <button onClick={retrySpelling} className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-200 px-5 py-3 text-sm font-black text-slate-700"><RotateCcw className="size-4" />{feedback.result === 'revealed' ? '隐藏答案，继续拼写' : '再拼一次'}</button> : null}<button onClick={() => void advance()} disabled={isBusy} className="flex-1 rounded-xl bg-indigo-600 px-7 py-3 text-sm font-black text-white disabled:opacity-60">下一个</button></div>
          ) : mode === 'review' || mode === 'new' ? (
            isReviewRevealed ? (
            <div className="grid grid-cols-2 gap-2 sm:ml-auto sm:grid-cols-4"><RatingButton shortcut="1" label="忘记了" disabled={isBusy} onClick={() => void rateAndAdvance(1)} /><RatingButton shortcut="2" label="有点模糊" disabled={isBusy} onClick={() => void rateAndAdvance(2)} /><RatingButton shortcut="3" label="认识" primary disabled={isBusy} onClick={() => void rateAndAdvance(3)} /><RatingButton shortcut="4" label="很熟" disabled={isBusy} onClick={() => void rateAndAdvance(4)} /></div>
            ) : (
              <button onClick={() => setIsReviewRevealed(true)} disabled={isBusy} className="rounded-xl bg-indigo-600 px-7 py-3 text-sm font-black text-white disabled:opacity-60">显示答案</button>
            )
          ) : <button onClick={() => void submitAttempt()} disabled={isBusy} className="rounded-xl bg-indigo-600 px-8 py-3 text-sm font-black text-white disabled:opacity-60">{isBusy ? '正在检查…' : '检查拼写'}</button>}
        </div>
      </footer>
    </div>
  )
}

function SetupGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="mt-7"><p className="mb-3 text-sm font-black text-slate-800">{label}</p><div className="flex flex-wrap gap-2">{children}</div></div>
}

function ReadonlyVocabularyDetail({
  backLabel,
  detail,
  error,
  isLoading,
  onBack,
  sourceLabel,
}: {
  backLabel: string
  detail: VocabularyItemDetail | null
  error: string | null
  isLoading: boolean
  onBack: () => void
  sourceLabel: string
}) {
  const [accent, setAccent] = useState<'uk' | 'us' | 'auto'>('uk')
  const [isPlaying, setIsPlaying] = useState(false)

  const playDetailAudio = async (nextAccent: 'uk' | 'us') => {
    if (!detail) return
    setAccent(nextAccent)
    const audioUrl = nextAccent === 'uk'
      ? detail.audio_uk ?? detail.audio_url
      : detail.audio_us ?? detail.audio_url
    setIsPlaying(true)
    try {
      if (audioUrl) {
        const audio = new Audio(audioUrl)
        audio.playbackRate = 0.9
        audio.onended = () => setIsPlaying(false)
        audio.onerror = () => setIsPlaying(false)
        await audio.play()
      } else if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel()
        const utterance = new SpeechSynthesisUtterance(detail.word)
        utterance.lang = nextAccent === 'us' ? 'en-US' : 'en-GB'
        utterance.rate = 0.86
        utterance.onend = () => setIsPlaying(false)
        window.speechSynthesis.speak(utterance)
      } else {
        setIsPlaying(false)
      }
    } catch {
      setIsPlaying(false)
    }
  }

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-[#fbfbfd] text-slate-950">
      <header className="shrink-0 border-b border-slate-200 bg-white px-4 py-3 sm:px-8">
        <div className="mx-auto flex max-w-[1420px] items-center justify-between gap-4">
          <button onClick={onBack} className="inline-flex shrink-0 items-center gap-2 text-sm font-bold text-slate-500 hover:text-indigo-600">
            <ArrowLeft className="size-4" />{backLabel}
          </button>
          <span className="truncate text-sm font-bold text-slate-600">
            单词详情 · {detail?.sources[0]?.label ?? sourceLabel}
          </span>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-6">
        <section className="mx-auto grid w-full max-w-[1420px] gap-3 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="min-w-0">
            {isLoading ? (
              <div className="flex min-h-[420px] items-center justify-center rounded-2xl border border-slate-200 bg-white text-sm font-bold text-slate-500 shadow-sm">
                <LoaderCircle className="mr-2 size-5 animate-spin text-indigo-600" />正在加载单词详情…
              </div>
            ) : detail ? (
              <RichVocabularyEntry
                word={detail.word}
                phonetic={detail.phonetic}
                phoneticUk={detail.phonetic_uk}
                phoneticUs={detail.phonetic_us}
                senses={detail.dictionary_senses}
                meanings={detail.meanings}
                examples={detail.examples}
                wordForms={detail.word_forms}
                tags={detail.dictionary_tags}
                activeAccent={accent}
                onPlayAccent={(nextAccent) => void playDetailAudio(nextAccent)}
              />
            ) : (
              <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-sm font-semibold text-amber-800">
                {error ?? '词条暂时无法加载。'}
              </div>
            )}
          </div>

          <aside className="flex min-h-0 flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-600">词汇本</p>
              <h2 className="mt-2 text-lg font-black text-slate-950">单词详情</h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                查看释义、例句、词形和发音；这里不会记录练习进度，也不会改变熟练度。
              </p>
            </div>
            <div className="rounded-xl bg-slate-50 p-3">
              <p className="text-xs font-bold text-slate-500">词汇来源</p>
              <p className="mt-1 text-sm font-black text-slate-800">{detail?.sources[0]?.label ?? sourceLabel}</p>
            </div>
            {detail?.mastery ? (
              <div className="rounded-xl bg-slate-50 p-3">
                <p className="text-xs font-bold text-slate-500">掌握度</p>
                <p className="mt-1 text-sm font-black text-slate-800">{Math.round((detail.mastery.overall ?? 0) * 100)}%</p>
              </div>
            ) : null}
            {detail ? (
              <button
                type="button"
                onClick={() => void playDetailAudio(accent === 'us' ? 'us' : 'uk')}
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-2.5 text-sm font-black text-indigo-700 transition hover:border-indigo-300"
              >
                {isPlaying ? <LoaderCircle className="size-4 animate-spin" /> : <Volume2 className="size-4" />}
                播放发音
              </button>
            ) : null}
          </aside>
        </section>
      </main>
    </div>
  )
}

function Choice({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" onClick={onClick} className={`rounded-xl border px-4 py-2.5 text-sm font-bold transition ${selected ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-slate-200 bg-white text-slate-600 hover:border-indigo-200'}`}>{children}</button>
}

function TaskSupportPanel({
  feedback,
  hintCount,
  isReviewRevealed,
  learnMoreTerm,
  mode,
  sourceLabel,
  onEditTerm,
  onHint,
  onReveal,
}: {
  feedback: AttemptFeedback | null
  hintCount: number
  isReviewRevealed: boolean
  learnMoreTerm?: string | null
  mode: VocabularyPracticeMode
  sourceLabel: string
  onEditTerm: () => void
  onHint: () => void
  onReveal: () => void
}) {
  const modeLabel = mode === 'new' ? '新词学习' : mode === 'review' ? '今日复习' : '拼写练习'
  const guidance = feedback
    ? feedback.result === 'correct'
      ? '看完反馈后，直接进入下一词。'
      : '先看差异和例句，再决定重试或进入下一词。'
    : mode === 'spelling'
      ? '听音后输入拼写。填满字母会自动检查，也可以用底部按钮提交。'
      : isReviewRevealed
        ? '根据真实熟悉度评分，系统会据此安排下次复习。'
        : '先主动回忆，再显示答案评分。'
  const canRevealAnswer = !feedback && (mode === 'spelling' || !isReviewRevealed)

  return (
    <aside className="flex min-h-0 flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div>
        <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-600">学习提示</p>
        <h2 className="mt-2 text-lg font-black text-slate-950">{modeLabel}</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">{guidance}</p>
      </div>

      <div className="rounded-xl bg-slate-50 p-3">
        <p className="text-xs font-bold text-slate-500">词汇来源</p>
        <p className="mt-1 text-sm font-black text-slate-800">{sourceLabel}</p>
      </div>

      <div className="grid gap-2">
        {!feedback && (
          <button
            type="button"
            onClick={onHint}
            disabled={hintCount >= 3}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-2.5 text-sm font-black text-indigo-700 transition hover:border-indigo-300 disabled:border-slate-200 disabled:bg-slate-50 disabled:text-slate-300"
          >
            <Lightbulb className="size-4" />
            {hintCount ? `再给一点提示 ${hintCount}/3` : '给我一个提示'}
          </button>
        )}
        {canRevealAnswer && (
          <button
            type="button"
            onClick={onReveal}
            className="rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-black text-slate-600 transition hover:bg-slate-50 hover:text-slate-900"
          >
            {mode === 'spelling' ? '不认识，先看答案' : '显示答案'}
          </button>
        )}
        {learnMoreTerm && (
          <button
            type="button"
            onClick={onEditTerm}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-indigo-200 bg-white px-4 py-2.5 text-sm font-black text-indigo-700 transition hover:border-indigo-400"
          >
            编辑词卡 <BookOpen className="size-4" />
          </button>
        )}
      </div>

    </aside>
  )
}

function FeedbackPanel({ feedback }: { feedback: AttemptFeedback }) {
  const success = feedback.result === 'correct'
  return <div className="relative mx-auto max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">{success ? <Celebration /> : null}<div className="flex flex-wrap justify-center gap-1 font-mono text-4xl font-black">{feedback.letter_diff.length ? feedback.letter_diff.map((letter, index) => <span key={index} className={letter.status === 'match' ? 'text-emerald-600' : 'text-orange-500'}>{letter.correct ?? letter.answer}</span>) : <span className={success ? 'text-emerald-600' : 'text-slate-950'}>{feedback.correct_answer}</span>}</div>{feedback.phonetic ? <p className="mt-3 text-slate-400">{feedback.phonetic}</p> : null}<p className={`mt-5 text-base font-black ${success ? 'text-emerald-700' : 'text-orange-700'}`}>{feedback.feedback_text}</p><div className="mt-4"><span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-black text-slate-500">{feedback.part_of_speech}</span>{feedback.meaning ? <span className="ml-2 text-sm text-slate-600">{feedback.meaning}</span> : null}</div>{feedback.example ? <p className="mt-2 text-sm text-slate-400">{feedback.example}</p> : null}</div>
}

function Celebration() {
  return <div className="pointer-events-none absolute inset-x-1/2 top-8" aria-hidden="true">{Array.from({ length: 8 }, (_, index) => <i key={index} className="vocab-confetti absolute block size-2 rounded-sm" style={{ '--confetti-index': index, '--confetti-x': `${(index - 3.5) * 18}px`, '--confetti-y': `${-38 - (index % 3) * 9}px`, '--confetti-hue': `${42 + index * 32}` } as React.CSSProperties} />)}</div>
}

function SummaryMetric({ label, value }: { label: string; value: number }) {
  return <div className="rounded-xl bg-slate-50 px-3 py-4"><strong className="text-2xl font-black text-slate-950">{value}</strong><p className="mt-1 text-xs font-bold text-slate-500">{label}</p></div>
}

function RatingButton({ label, shortcut, primary, disabled, onClick }: { label: string; shortcut: string; primary?: boolean; disabled?: boolean; onClick: () => void }) {
  return <button type="button" onClick={onClick} disabled={disabled} className={`min-w-28 rounded-xl border px-4 py-2.5 text-sm font-black transition disabled:cursor-wait disabled:opacity-60 ${primary ? 'border-amber-500 bg-amber-50 text-amber-800' : 'border-slate-200 bg-white text-slate-700 hover:border-indigo-300'}`}><span className="block">{label}</span><span className="mt-0.5 block text-[10px] font-semibold opacity-55">{shortcut} 键</span></button>
}
