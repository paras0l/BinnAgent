import {
  ArrowLeft,
  BookOpen,
  Check,
  Clipboard,
  ExternalLink,
  FileInput,
  RefreshCw,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useToast } from '@/hooks/useToast'
import type { Learner } from '@/types'

interface VocabularyDetailPageProps {
  learner?: Learner
  term: string
  onBack: () => void
  backLabel?: string
}

const TARGET_URL = 'https://chat.deepseek.com/'

export function VocabularyDetailPage({
  learner,
  term,
  onBack,
  backLabel = '返回词汇练习',
}: VocabularyDetailPageProps) {
  const { showToast } = useToast()
  const [termInput, setTermInput] = useState(term.trim())
  const [activeTerm, setActiveTerm] = useState(term.trim())
  const [isSaving, setIsSaving] = useState(false)
  const prompt = useMemo(() => buildVocabularyPrompt(activeTerm), [activeTerm])
  const storageKey = useMemo(
    () => `binnVocabularyDetail:${activeTerm.trim().toLocaleLowerCase()}`,
    [activeTerm],
  )
  const [html, setHtml] = useState(() => localStorage.getItem(storageKey) ?? '')
  const [isCopied, setIsCopied] = useState(false)
  const safeHtml = useMemo(() => sanitizeHtml(html), [html])
  const canSaveToVocabulary = Boolean(learner && activeTerm.trim() && html.trim())
  const saveButtonLabel = !html.trim()
    ? '先粘贴 HTML 后加入词库'
    : isSaving
      ? '正在加入词库…'
      : '加入词库 / 更新字段'

  useEffect(() => {
    const nextTerm = term.trim()
    setTermInput(nextTerm)
    setActiveTerm(nextTerm)
  }, [term])

  useEffect(() => {
    setHtml(localStorage.getItem(storageKey) ?? '')
  }, [storageKey])

  const updateHtml = useCallback((value: string) => {
    setHtml(value)
    if (value.trim()) localStorage.setItem(storageKey, value)
    else localStorage.removeItem(storageKey)
  }, [storageKey])

  useEffect(() => {
    const handleReturnedHtml = (event: MessageEvent) => {
      if (event.source !== window) return
      const data = event.data as { type?: string; html?: string }
      if (data.type !== 'BINN_GRAMMAR_HTML_RETURNED' || typeof data.html !== 'string') return
      updateHtml(data.html)
      showToast('已接收词汇详解 HTML。', { variant: 'success' })
    }
    window.addEventListener('message', handleReturnedHtml)
    return () => window.removeEventListener('message', handleReturnedHtml)
  }, [showToast, updateHtml])

  const copyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(prompt)
      window.postMessage({
        type: 'BINN_GRAMMAR_PROMPT_READY',
        prompt,
        topicTitle: activeTerm,
        sourceUrl: window.location.href,
        targetUrl: TARGET_URL,
      }, window.location.origin)
      setIsCopied(true)
      showToast('词汇详解指令已复制。', { variant: 'success' })
      window.setTimeout(() => setIsCopied(false), 1800)
    } catch {
      showToast('复制失败，请手动复制指令。', { variant: 'error' })
    }
  }

  const launchTarget = async () => {
    await copyPrompt()
    window.open(TARGET_URL, '_blank', 'noopener,noreferrer')
  }

  const applyTermInput = () => {
    const nextTerm = termInput.trim()
    if (!nextTerm) {
      showToast('先输入一个要详解的词。', { variant: 'warning' })
      return
    }
    setActiveTerm(nextTerm)
  }

  const addToVocabulary = async () => {
    if (!learner) {
      showToast('当前没有学习者，无法加入词库。', { variant: 'error' })
      return
    }
    if (!activeTerm.trim()) {
      showToast('先输入一个要加入词库的词。', { variant: 'warning' })
      return
    }
    if (!html.trim()) {
      showToast('先粘贴 AI 返回的 HTML，再加入词库。', { variant: 'warning' })
      return
    }
    setIsSaving(true)
    try {
      const response = await fetch(`/api/learners/${learner.id}/vocabulary/detail-html`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ term: activeTerm.trim(), html }),
      })
      if (!response.ok) throw new Error('保存失败')
      const result = await response.json() as { created: boolean; word: string }
      showToast(
        result.created ? `已将 ${result.word} 加入词库。` : `已更新 ${result.word} 的词库字段。`,
        { variant: 'success' },
      )
    } catch {
      showToast('加入词库失败，请稍后再试。', { variant: 'error' })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#f7f8fc] px-4 py-8 sm:px-6">
      <div className="mx-auto max-w-7xl">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-2 text-sm font-bold text-slate-500 hover:text-indigo-600"
        >
          <ArrowLeft className="size-4" />{backLabel}
        </button>

        <header className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-black text-indigo-600">词汇详解</p>
          <div className="mt-3 flex flex-col gap-3 sm:flex-row">
            <input
              value={termInput}
              onChange={(event) => setTermInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') applyTermInput()
              }}
              className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-4 py-3 text-2xl font-black tracking-tight text-slate-950 outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 sm:text-4xl"
              placeholder="输入要详解的单词或词组"
              aria-label="词汇详解词条"
            />
            <button
              type="button"
              onClick={applyTermInput}
              className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-black text-white hover:bg-slate-800"
            >
              生成指令
            </button>
          </div>
          <p className="mt-2 text-sm text-slate-500">
            聚焦一个单词或词组，理解词义层次、搭配、语境和易错用法。
          </p>
        </header>

        <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
          <section className="rounded-2xl border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <FileInput className="size-5 text-indigo-600" />
                  <h2 className="text-lg font-black">详解阅读区</h2>
                </div>
                <p className="mt-1 text-sm text-slate-500">粘贴 AI 返回的 HTML 后即可阅读。</p>
              </div>
              <button
                type="button"
                onClick={() => updateHtml('')}
                className="rounded-lg border p-2 text-slate-500 hover:bg-slate-50"
                title="清空内容"
              >
                <RefreshCw className="size-4" />
              </button>
            </div>
            <div className="mt-4 min-h-[560px] overflow-hidden rounded-xl border border-slate-200 bg-white">
              {safeHtml ? (
                <iframe
                  title={`${activeTerm} 词汇详解`}
                  srcDoc={detailDocument(safeHtml)}
                  sandbox=""
                  className="h-[640px] w-full"
                />
              ) : (
                <div className="flex min-h-[560px] flex-col items-center justify-center px-6 text-center text-slate-400">
                  <BookOpen className="size-10 text-indigo-200" />
                  <p className="mt-4 text-sm font-bold">
                    复制右侧指令生成详解，再把 HTML 粘贴回来。
                  </p>
                </div>
              )}
            </div>
          </section>

          <aside className="space-y-5">
            <section className="rounded-2xl border border-slate-200 bg-white p-5">
              <h2 className="text-lg font-black">生成词汇详解</h2>
              <p className="mt-1 text-sm text-slate-500">已将“{activeTerm || '待输入'}”写入专用 prompt。</p>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => void copyPrompt()}
                  className="inline-flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-bold hover:bg-slate-50"
                >
                  {isCopied ? <Check className="size-4 text-emerald-600" /> : <Clipboard className="size-4" />}
                  {isCopied ? '已复制' : '复制指令'}
                </button>
                <button
                  type="button"
                  onClick={() => void launchTarget()}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-3 py-2.5 text-sm font-bold text-white hover:bg-indigo-700"
                >
                  <ExternalLink className="size-4" />复制并跳转
                </button>
              </div>
              <button
                type="button"
                onClick={() => void addToVocabulary()}
                disabled={isSaving || !canSaveToVocabulary}
                className="mt-3 w-full rounded-xl bg-emerald-600 px-3 py-2.5 text-sm font-bold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-emerald-300"
                title={
                  html.trim()
                    ? '把当前词汇详解 HTML 提取并写入词库'
                    : '先在 HTML 输入区粘贴 AI 返回内容'
                }
              >
                {saveButtonLabel}
              </button>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-5">
              <h2 className="text-lg font-black">Prompt 预览</h2>
              <textarea
                readOnly
                value={prompt}
                className="mt-3 h-72 w-full resize-none rounded-xl border bg-slate-50 p-3 text-xs leading-relaxed outline-none"
              />
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-5">
              <h2 className="text-lg font-black">HTML 输入</h2>
              <textarea
                value={html}
                onChange={(event) => updateHtml(event.target.value)}
                placeholder="粘贴 AI 返回的 HTML 片段…"
                className="mt-3 h-64 w-full resize-none rounded-xl border p-3 font-mono text-xs leading-relaxed outline-none focus:border-indigo-500"
              />
            </section>
          </aside>
        </div>
      </div>
    </div>
  )
}

function buildVocabularyPrompt(term: string) {
  return `请为英语学习者制作一个“词汇详解微课”，目标词汇（可能是单词或词组）是：${term}。

请严格遵守：
1. 先判断它是单词还是词组；若存在多个常见词性或义项，按真实使用频率分层，不要堆砌冷僻释义。
2. 内容控制在约 700-1000 中文字等量，适合 5-8 分钟阅读，讲清“怎么理解、怎么搭配、怎么在句子里使用”。
3. 仅输出一个 HTML 片段，不要 Markdown 代码围栏，不要输出 HTML 之外的解释。
4. HTML 必须包含：标题、音标与词性（词组则说明类型）、核心义项、构词或记忆线索、常用搭配、4-6 个分级例句及中文解释、近义词辨析或易混词、常见错误、2 道小练习及答案。
5. 每个例句都必须包含“${term}”或其合理词形变化；明确标注正式/口语、及物/不及物、可数/不可数等关键限制（仅在适用时）。
6. 如果是词组，重点说明整体含义、固定结构、可否拆分、宾语位置和常见变体；不要把它误当作单个词讲解。
7. 不确定的词源或用法不要编造。禁止输出 <script>、外链资源、表单、iframe 或自动播放媒体。

学习者背景：初中到 CET 四六级阶段，母语为中文，喜欢中英结合、结构清楚、例句实用。`
}

function sanitizeHtml(value: string) {
  if (!value.trim()) return ''
  const document = new DOMParser().parseFromString(value, 'text/html')
  document.querySelectorAll('script, iframe, object, embed, form, link, meta').forEach((node) => node.remove())
  document.querySelectorAll('*').forEach((element) => {
    for (const attribute of Array.from(element.attributes)) {
      if (/^on/i.test(attribute.name) || ['src', 'href', 'action'].includes(attribute.name.toLowerCase())) {
        element.removeAttribute(attribute.name)
      }
    }
  })
  return document.body.innerHTML
}

function detailDocument(content: string) {
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>body{margin:0;padding:28px;font-family:ui-sans-serif,system-ui;color:#0f172a;line-height:1.75}main,article,section{max-width:820px;margin:auto}h1{font-size:30px}h2{font-size:21px;margin-top:28px;color:#3730a3}p,li{font-size:15px}blockquote,.example{margin:14px 0;padding:10px 14px;border-left:4px solid #6366f1;background:#f8fafc}code{padding:2px 5px;border-radius:5px;background:#eef2ff;color:#3730a3}table{width:100%;border-collapse:collapse}th,td{padding:8px;border:1px solid #e2e8f0}</style></head><body>${content}</body></html>`
}
