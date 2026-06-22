import { ArrowLeft, LoaderCircle, Search } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import {
  RichVocabularyEntry,
  type BilingualMeaning,
  type DictionarySense,
} from '@/components/vocabulary/RichVocabularyEntry'
import type { Learner } from '@/types'

interface VocabularyDetailPageProps {
  learner: Learner
  term: string
  onBack: () => void
  backLabel?: string
}

interface VocabularyDetail {
  id: string
  word: string
  phonetic?: string | null
  phonetic_uk?: string | null
  phonetic_us?: string | null
  entry_kind: string
  meanings: BilingualMeaning[]
  dictionary_senses: DictionarySense[]
  word_forms: Record<string, string[]>
  dictionary_tags: string[]
  examples: Array<string | Record<string, unknown>>
  dictionary_provider?: string | null
  sources: Array<{ type: string; label: string; context: Record<string, unknown> }>
}

export function VocabularyDetailPage({
  learner,
  term,
  onBack,
  backLabel = '返回词汇练习',
}: VocabularyDetailPageProps) {
  const [query, setQuery] = useState(term.trim())
  const [activeTerm, setActiveTerm] = useState(term.trim())
  const [detail, setDetail] = useState<VocabularyDetail | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [accent, setAccent] = useState<'uk' | 'us'>('uk')

  const loadDetail = useCallback(async (nextTerm: string, signal?: AbortSignal) => {
    if (!nextTerm) {
      setDetail(null)
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const response = await fetch(
        `/api/learners/${learner.id}/vocabulary/detail?term=${encodeURIComponent(nextTerm)}`,
        { signal },
      )
      if (!response.ok) {
        throw new Error(response.status === 404 ? '这个词还不在当前词汇本中。' : '词典数据暂时无法加载。')
      }
      setDetail(await response.json() as VocabularyDetail)
    } catch (loadError) {
      if (loadError instanceof DOMException && loadError.name === 'AbortError') return
      setDetail(null)
      setError(loadError instanceof Error ? loadError.message : '词典数据暂时无法加载。')
    } finally {
      setIsLoading(false)
    }
  }, [learner.id])

  useEffect(() => {
    if (!activeTerm) return
    const controller = new AbortController()
    void loadDetail(activeTerm, controller.signal)
    return () => controller.abort()
  }, [activeTerm, loadDetail])

  const playAccent = (nextAccent: 'uk' | 'us') => {
    setAccent(nextAccent)
    if (!detail || !('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(detail.word)
    utterance.lang = nextAccent === 'us' ? 'en-US' : 'en-GB'
    utterance.rate = 0.86
    window.speechSynthesis.speak(utterance)
  }

  return (
    <div className="min-h-screen bg-[#f7f8fb] px-4 py-6 sm:px-6">
      <div className="mx-auto max-w-[1420px]">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <button type="button" onClick={onBack} className="inline-flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-indigo-700">
            <ArrowLeft className="size-4" />{backLabel}
          </button>
          <form
            className="flex w-full max-w-lg gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              const nextTerm = query.trim()
              if (nextTerm) setActiveTerm(nextTerm)
            }}
          >
            <label className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm font-semibold text-slate-900 outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100"
                placeholder="搜索词汇本中的单词或词组"
                aria-label="搜索词汇"
              />
            </label>
            <button type="submit" className="rounded-xl bg-[#173f9f] px-5 py-2.5 text-sm font-black text-white hover:bg-[#123586]">
              查询
            </button>
          </form>
        </div>

        <div className="mt-5">
          {isLoading ? (
            <div className="flex min-h-[520px] items-center justify-center text-sm font-bold text-slate-500">
              <LoaderCircle className="mr-2 size-5 animate-spin text-indigo-600" />正在加载词典数据…
            </div>
          ) : detail ? (
            <>
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
                onPlayAccent={playAccent}
              />
              <p className="mt-3 text-right text-xs font-semibold text-slate-400">
                {detail.sources[0]?.label ? `来源：${detail.sources[0].label} · ` : ''}
                数据：{providerLabel(detail.dictionary_provider)}
              </p>
            </>
          ) : (
            <div className="flex min-h-[520px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white px-6 text-center">
              <Search className="size-9 text-slate-300" />
              <h1 className="mt-4 text-xl font-black text-slate-800">{error ?? '搜索一个词汇'}</h1>
              <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">这里直接读取数据库中的百度词典数据，不再需要复制 Prompt 或粘贴 HTML。</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function providerLabel(provider?: string | null) {
  if (provider?.includes('baidu_dictionary_api')) return '百度词典版 API'
  if (provider?.includes('baidu_translate')) return '百度翻译 + Free Dictionary'
  return '词汇数据库'
}
