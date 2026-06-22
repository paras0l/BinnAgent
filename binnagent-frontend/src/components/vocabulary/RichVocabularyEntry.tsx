import { BookOpen, ChevronDown, Sparkles, Volume2 } from 'lucide-react'

export interface DictionarySense {
  part_of_speech: string
  meanings_zh: string[]
}

export interface BilingualMeaning {
  part_of_speech?: string
  definition?: string
  definition_zh?: string
}

interface RichVocabularyEntryProps {
  word: string
  phonetic?: string | null
  phoneticUk?: string | null
  phoneticUs?: string | null
  senses?: DictionarySense[]
  meanings?: BilingualMeaning[]
  examples?: Array<string | Record<string, unknown>>
  wordForms?: Record<string, string[]>
  tags?: string[]
  activeAccent?: 'uk' | 'us' | 'auto'
  onPlayAccent?: (accent: 'uk' | 'us') => void
  compact?: boolean
}

const FORM_LABELS: Record<string, string> = {
  word_pl: '复数',
  word_third: '第三人称单数',
  word_ing: '现在进行时',
  word_past: '过去式',
  word_done: '过去分词',
  word_er: '比较级',
  word_est: '最高级',
}

export function RichVocabularyEntry({
  word,
  phonetic,
  phoneticUk,
  phoneticUs,
  senses = [],
  meanings = [],
  examples = [],
  wordForms = {},
  tags = [],
  activeAccent = 'uk',
  onPlayAccent,
  compact = false,
}: RichVocabularyEntryProps) {
  const resolvedSenses = senses.length > 0
    ? senses
    : fallbackSenses(meanings)
  const formRows = Object.entries(wordForms).filter(([, values]) => values.length > 0)
  const example = firstExample(examples)

  return (
    <div className={`grid min-w-0 gap-3 ${compact ? '' : 'lg:grid-cols-[minmax(0,1fr)_300px]'}`}>
      <article className="min-w-0 rounded-2xl border border-slate-200 bg-white px-5 py-6 shadow-[0_12px_38px_rgba(15,23,42,0.06)] sm:px-8 sm:py-7">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <h1 className="font-serif text-6xl font-semibold tracking-[-0.055em] text-[#102044] sm:text-7xl">
              {word}
            </h1>
            {tags.length > 0 ? (
              <p className="mt-2 text-xs font-semibold tracking-wide text-slate-400">
                {tags.join(' · ')}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            <PronunciationButton
              accent="uk"
              label="英"
              phonetic={phoneticUk ?? phonetic}
              selected={activeAccent === 'uk'}
              onPlay={onPlayAccent}
            />
            <PronunciationButton
              accent="us"
              label="美"
              phonetic={phoneticUs ?? phonetic}
              selected={activeAccent === 'us'}
              onPlay={onPlayAccent}
            />
          </div>
        </div>

        <section className="divide-y divide-dashed divide-slate-200">
          {resolvedSenses.map((sense, index) => (
            <div key={`${sense.part_of_speech}-${index}`} className="py-5">
              <div className="flex items-center gap-2 text-[#173f9f]">
                <strong className="text-lg font-black">{sense.part_of_speech}</strong>
                <span className="text-sm font-semibold text-slate-500">{partLabel(sense.part_of_speech)}</span>
                <ChevronDown className="size-4" aria-hidden="true" />
              </div>
              <p className="mt-3 text-[15px] font-medium leading-7 text-slate-700">
                {sense.meanings_zh.join('；')}
              </p>
            </div>
          ))}
        </section>

        {meanings.length > 0 ? (
          <section className="border-t border-slate-200 pt-5">
            <div className="mb-3 flex items-center gap-2 text-slate-800">
              <BookOpen className="size-5 text-[#173f9f]" />
              <h2 className="text-base font-black">英英释义</h2>
            </div>
            <div className="overflow-hidden rounded-xl border border-slate-200">
              {meanings.slice(0, 4).map((meaning, index) => (
                <div
                  key={`${meaning.definition}-${index}`}
                  className="grid gap-1 border-b border-slate-200 px-4 py-3 last:border-b-0 sm:grid-cols-[74px_minmax(0,1.3fr)_minmax(0,0.9fr)] sm:gap-4"
                >
                  <span className="text-sm font-bold text-slate-500">{meaning.part_of_speech ?? 'word'}</span>
                  <p className="text-sm leading-6 text-slate-700">{meaning.definition || '—'}</p>
                  <p className="text-sm font-semibold leading-6 text-slate-600">{meaning.definition_zh || '—'}</p>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {example ? (
          <section className="mt-5 border-t border-slate-200 pt-5">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-700">
                <Sparkles className="size-4" />
              </span>
              <div>
                <h2 className="text-sm font-black text-slate-800">例句</h2>
                <p className="mt-1 text-[15px] leading-7 text-slate-700">{example}</p>
              </div>
            </div>
          </section>
        ) : null}
      </article>

      {!compact ? (
        <aside className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_12px_38px_rgba(15,23,42,0.05)]">
          <div className="flex items-center gap-2 border-b border-slate-200 pb-4">
            <BookOpen className="size-5 text-[#173f9f]" />
            <h2 className="text-base font-black text-slate-900">词形变化</h2>
          </div>
          {formRows.length > 0 ? (
            <dl className="divide-y divide-slate-100">
              {formRows.map(([key, values]) => (
                <div key={key} className="flex items-center justify-between gap-4 py-4">
                  <dt className="text-sm font-semibold text-slate-500">{FORM_LABELS[key] ?? key}</dt>
                  <dd className="text-right text-[15px] font-bold text-[#1747b2]">{values.join(', ')}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="py-5 text-sm leading-6 text-slate-400">该词暂时没有可展示的词形变化。</p>
          )}
          <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50/70 p-4">
            <p className="text-sm font-black text-amber-900">记忆小贴士</p>
            <p className="mt-2 text-sm leading-6 text-amber-900/75">
              先区分不同词性，再用一个自己的句子把最常用义项固定下来。
            </p>
          </div>
        </aside>
      ) : null}
    </div>
  )
}

function PronunciationButton({
  accent,
  label,
  phonetic,
  selected,
  onPlay,
}: {
  accent: 'uk' | 'us'
  label: string
  phonetic?: string | null
  selected: boolean
  onPlay?: (accent: 'uk' | 'us') => void
}) {
  return (
    <button
      type="button"
      onClick={() => onPlay?.(accent)}
      className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-left transition ${selected ? 'border-indigo-300 bg-indigo-50 text-indigo-800' : 'border-slate-200 bg-white text-slate-600 hover:border-indigo-200'}`}
      aria-label={`播放${label}音`}
    >
      <span className="text-sm font-black">{label}</span>
      <span className="font-mono text-sm">/{stripSlashes(phonetic) || '—'}/</span>
      <Volume2 className="size-4" />
    </button>
  )
}

function fallbackSenses(meanings: BilingualMeaning[]): DictionarySense[] {
  const grouped = new Map<string, string[]>()
  for (const meaning of meanings) {
    if (!meaning.definition_zh) continue
    const part = meaning.part_of_speech ?? 'word'
    grouped.set(part, [...(grouped.get(part) ?? []), meaning.definition_zh])
  }
  if (grouped.size === 0) return [{ part_of_speech: 'word', meanings_zh: ['暂无中文释义'] }]
  return Array.from(grouped, ([part_of_speech, meanings_zh]) => ({ part_of_speech, meanings_zh }))
}

function firstExample(examples: Array<string | Record<string, unknown>>) {
  const first = examples[0]
  if (typeof first === 'string') return first
  if (!first) return null
  for (const key of ['text', 'example', 'content']) {
    const value = first[key]
    if (typeof value === 'string') return value
  }
  return null
}

function partLabel(part: string) {
  const normalized = part.toLowerCase()
  if (normalized.includes('n')) return '名词'
  if (normalized.includes('v')) return '动词'
  if (normalized.includes('adj')) return '形容词'
  if (normalized.includes('adv')) return '副词'
  if (normalized.includes('prep')) return '介词'
  if (normalized.includes('pron')) return '代词'
  return '词义'
}

function stripSlashes(value?: string | null) {
  return value?.replace(/^\/+|\/+$/g, '') ?? ''
}
