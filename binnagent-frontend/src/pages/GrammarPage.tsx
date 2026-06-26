import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  Check,
  CheckCircle2,
  Clipboard,
  ExternalLink,
  FileInput,
  Maximize2,
  Plus,
  Puzzle,
  RefreshCw,
  Search,
  Star,
  StarOff,
  Trash2,
  X,
} from 'lucide-react'
import {
  GRAMMAR_CATEGORY_LABELS,
  GRAMMAR_TOPICS,
  type GrammarCategory,
  type GrammarTopic,
} from '@/data/grammarTopics'
import type { GrammarHtmlCacheResponse, Learner, LearningProgressItem } from '@/types'
import { useToast } from '@/hooks/useToast'

type CategoryFilter = 'all' | GrammarCategory

interface GrammarTarget {
  id: string
  label: string
  url: string
}

interface StoredGrammarState {
  topicId: string
  prompt: string
  html?: string
  htmlByTopicId?: Record<string, string>
  targetId: string
  targets: GrammarTarget[]
}

interface GrammarPageProps {
  learner: Learner
  onBack: () => void
  backLabel?: string
  initialTopic?: string | null
}

const DEFAULT_TARGETS: GrammarTarget[] = [
  { id: 'deepseek', label: 'DeepSeek', url: 'https://chat.deepseek.com/' },
]

const STORAGE_KEY = 'binnGrammarMicroLesson'
const PROMPT_VERSION = 'v1'
const EXTENSION_PATH = '/Users/binge/Documents/BinnAgent/browser-extension/grammar-autofill'

type CacheStatus = 'idle' | 'loading' | 'hit' | 'miss' | 'saving' | 'saved' | 'error' | 'bypassed'

const BASE_IFRAME_STYLE = `
  <style>
    :root { color-scheme: light; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #0f172a;
      background: #ffffff;
      line-height: 1.72;
    }
    main, article, section { max-width: 840px; margin: 0 auto; }
    body > * { padding: 24px; }
    h1 { font-size: 28px; line-height: 1.2; margin: 0 0 16px; }
    h2 { font-size: 20px; margin: 24px 0 10px; }
    h3 { font-size: 16px; margin: 18px 0 8px; }
    p { margin: 8px 0; }
    ul, ol { padding-left: 24px; }
    li + li { margin-top: 6px; }
    code {
      border-radius: 6px;
      background: #eef2ff;
      padding: 2px 5px;
      color: #3730a3;
    }
    .example, blockquote {
      border-left: 4px solid #6366f1;
      background: #f8fafc;
      margin: 12px 0;
      padding: 10px 14px;
    }
    table { width: 100%; border-collapse: collapse; }
    th, td { border: 1px solid #e2e8f0; padding: 8px; }
  </style>
`

export function GrammarPage({ learner, onBack, backLabel = '返回探索', initialTopic }: GrammarPageProps) {
  const { showToast } = useToast()
  const storedState = useMemo(() => readStoredGrammarState(), [])
  const topicOptions = useMemo(() => {
    const title = initialTopic?.trim()
    if (!title) return GRAMMAR_TOPICS
    const existing = GRAMMAR_TOPICS.find((topic) => topic.title === title)
    if (existing) return GRAMMAR_TOPICS
    return [createGrammarTopic(title), ...GRAMMAR_TOPICS]
  }, [initialTopic])
  const initialTopicId = useMemo(() => {
    const title = initialTopic?.trim()
    if (!title) return null
    return topicOptions.find((topic) => topic.title === title)?.id ?? null
  }, [initialTopic, topicOptions])
  const [category, setCategory] = useState<CategoryFilter>('all')
  const [query, setQuery] = useState('')
  const [selectedTopicId, setSelectedTopicId] = useState(
    initialTopicId ?? (storedState.topicId && topicOptions.some((topic) => topic.id === storedState.topicId)
      ? storedState.topicId
      : topicOptions[0]?.id ?? '')
  )
  const [targets, setTargets] = useState<GrammarTarget[]>(
    storedState.targets.length > 0 ? storedState.targets : DEFAULT_TARGETS
  )
  const [targetId, setTargetId] = useState(storedState.targetId || DEFAULT_TARGETS[0].id)
  const [newTargetLabel, setNewTargetLabel] = useState('')
  const [newTargetUrl, setNewTargetUrl] = useState('')
  const [htmlByTopicId, setHtmlByTopicId] = useState<Record<string, string>>(storedState.htmlByTopicId ?? {})
  const [cacheStatusByTopicId, setCacheStatusByTopicId] = useState<Record<string, CacheStatus>>({})
  const [bypassedCacheTopicIds, setBypassedCacheTopicIds] = useState<string[]>([])
  const [progressByTopicId, setProgressByTopicId] = useState<Record<string, LearningProgressItem>>({})
  const [isCopied, setIsCopied] = useState(false)
  const [isExtensionPathCopied, setIsExtensionPathCopied] = useState(false)
  const [isImmersiveReading, setIsImmersiveReading] = useState(false)
  const [renderedPrompt, setRenderedPrompt] = useState<{ topicId: string; prompt: string; prompt_hash: string; version: string } | null>(null)

  const selectedTopic = useMemo(
    () => topicOptions.find((topic) => topic.id === selectedTopicId) ?? topicOptions[0],
    [selectedTopicId, topicOptions]
  )

  const fallbackPrompt = useMemo(() => buildGrammarPrompt(selectedTopic), [selectedTopic])
  const activeRenderedPrompt = renderedPrompt?.topicId === selectedTopic.id ? renderedPrompt : null
  const prompt = activeRenderedPrompt?.prompt ?? fallbackPrompt
  const promptVersion = activeRenderedPrompt?.version ?? PROMPT_VERSION
  const promptHash = activeRenderedPrompt?.prompt_hash ?? stableHash(`${promptVersion}:${selectedTopic.id}:${prompt}`)
  const currentHtml = htmlByTopicId[selectedTopic.id] ?? ''
  const currentProgress = progressByTopicId[selectedTopic.id]
  const currentCacheStatus = cacheStatusByTopicId[selectedTopic.id] ?? 'idle'

  const setTopicHtml = useCallback((topicId: string, nextHtml: string) => {
    setHtmlByTopicId((current) => ({ ...current, [topicId]: nextHtml }))
    setBypassedCacheTopicIds((current) => current.filter((id) => id !== topicId))
    setCacheStatusByTopicId((current) => ({ ...current, [topicId]: nextHtml.trim() ? 'saving' : 'idle' }))
  }, [])

  const persistGrammarProgress = useCallback(
    async (
      topic: GrammarTopic,
      payload: { is_favorite?: boolean; mark_opened?: boolean; mark_learned?: boolean }
    ) => {
      try {
        const response = await fetch(
          `/api/learners/${learner.id}/learning-progress/grammar/${encodeURIComponent(topic.id)}`,
          {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title: topic.title,
              metadata: {
                category: topic.category,
                level: topic.level,
                tags: topic.tags,
                shortDescription: topic.shortDescription,
              },
              ...payload,
            }),
          }
        )
        if (!response.ok) throw new Error('Failed to persist grammar progress')
        const updated = (await response.json()) as LearningProgressItem
        setProgressByTopicId((current) => ({ ...current, [updated.item_id]: updated }))
      } catch (err) {
        console.error('Grammar progress save error:', err)
        showToast('语法学习进度暂时无法保存，本地操作不会中断。', { variant: 'warning' })
      }
    },
    [learner.id, showToast]
  )

  const saveGrammarHtmlToCache = useCallback(
    async (topicId: string, html: string, hash: string, version: string) => {
      setCacheStatusByTopicId((current) => ({ ...current, [topicId]: 'saving' }))
      try {
        const response = await fetch(
          `/api/learners/${learner.id}/grammar/topics/${encodeURIComponent(topicId)}/html-cache`,
          {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              html,
              prompt_hash: hash,
              prompt_version: version,
              source: 'frontend',
            }),
          }
        )
        if (!response.ok) throw new Error('Failed to save grammar cache')
        setCacheStatusByTopicId((current) => ({ ...current, [topicId]: 'saved' }))
      } catch (err) {
        console.error('Grammar cache save error:', err)
        setCacheStatusByTopicId((current) => ({ ...current, [topicId]: 'error' }))
        showToast('语法 HTML 缓存暂时无法保存，但当前页面内容已保留。', { variant: 'warning' })
      }
    },
    [learner.id, showToast]
  )

  useEffect(() => {
    const stored: StoredGrammarState = {
      topicId: selectedTopic.id,
      prompt,
      htmlByTopicId,
      targetId,
      targets,
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stored))
  }, [htmlByTopicId, prompt, selectedTopic.id, targetId, targets])

  useEffect(() => {
    let isMounted = true
    fetch(`/api/learners/${learner.id}/learning-progress?skill=grammar`)
      .then((response) => {
        if (!response.ok) throw new Error('Failed to load grammar progress')
        return response.json() as Promise<LearningProgressItem[]>
      })
      .then((items) => {
        if (!isMounted) return
        setProgressByTopicId(Object.fromEntries(items.map((item) => [item.item_id, item])))
      })
      .catch((err) => {
        console.error('Grammar progress load error:', err)
        if (isMounted) showToast('语法学习进度暂时无法加载，本页仍可继续使用。', { variant: 'warning' })
      })
    return () => {
      isMounted = false
    }
  }, [learner.id, showToast])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void persistGrammarProgress(selectedTopic, { mark_opened: true })
    }, 0)
    return () => window.clearTimeout(timer)
  }, [persistGrammarProgress, selectedTopic])

  useEffect(() => {
    let isMounted = true
    const topicId = selectedTopic.id
    fetch('/api/prompts/grammar.micro_lesson.structured/render', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        version: PROMPT_VERSION,
        variables: {
          topic_title: selectedTopic.title,
          short_description: selectedTopic.shortDescription,
          tags: selectedTopic.tags,
          learner_background: 'CET 四六级备考，喜欢中英结合、规则清楚、例句实用。',
        },
      }),
    })
      .then((response) => {
        if (!response.ok) throw new Error('Failed to render grammar prompt')
        return response.json() as Promise<{ prompt: string; prompt_hash: string; version: string }>
      })
      .then((data) => {
        if (isMounted) setRenderedPrompt({ ...data, topicId })
      })
      .catch((err) => {
        console.error('Grammar prompt render error:', err)
        if (isMounted) showToast('后端 Prompt Registry 暂时不可用，已使用本地兼容 prompt。', { variant: 'warning' })
      })
    return () => {
      isMounted = false
    }
  }, [selectedTopic, showToast])

  useEffect(() => {
    if (currentHtml.trim()) return
    if (bypassedCacheTopicIds.includes(selectedTopic.id)) {
      return
    }

    let isMounted = true
    const topicId = selectedTopic.id
    const loadingTimer = window.setTimeout(() => {
      if (isMounted) setCacheStatusByTopicId((current) => ({ ...current, [topicId]: 'loading' }))
    }, 0)
    fetch(
      `/api/learners/${learner.id}/grammar/topics/${encodeURIComponent(topicId)}/html-cache?` +
        new URLSearchParams({ prompt_hash: promptHash, prompt_version: promptVersion }).toString()
    )
      .then((response) => {
        if (!response.ok) throw new Error('Failed to load grammar cache')
        return response.json() as Promise<GrammarHtmlCacheResponse>
      })
      .then((data) => {
        if (!isMounted) return
        if (data.cached && data.html) {
          setHtmlByTopicId((current) => {
            if (current[topicId]?.trim()) return current
            return { ...current, [topicId]: data.html ?? '' }
          })
          setCacheStatusByTopicId((current) => ({ ...current, [topicId]: 'hit' }))
        } else {
          setCacheStatusByTopicId((current) => ({ ...current, [topicId]: 'miss' }))
        }
      })
      .catch((err) => {
        console.error('Grammar cache load error:', err)
        if (isMounted) {
          setCacheStatusByTopicId((current) => ({ ...current, [topicId]: 'error' }))
          showToast('语法缓存暂时无法读取，可以继续手动生成或粘贴 HTML。', { variant: 'warning' })
        }
      })

    return () => {
      isMounted = false
      window.clearTimeout(loadingTimer)
    }
  }, [bypassedCacheTopicIds, currentHtml, learner.id, promptHash, promptVersion, selectedTopic.id, showToast])

  useEffect(() => {
    const html = currentHtml.trim()
    if (!html) return
    const timer = window.setTimeout(() => {
      void saveGrammarHtmlToCache(selectedTopic.id, html, promptHash, promptVersion)
    }, 900)
    return () => window.clearTimeout(timer)
  }, [currentHtml, promptHash, promptVersion, saveGrammarHtmlToCache, selectedTopic.id])

  useEffect(() => {
    const handleReturnedHtml = (event: MessageEvent) => {
      if (event.source !== window) return
      const data = event.data as { type?: string; html?: string }
      if (data?.type !== 'BINN_GRAMMAR_HTML_RETURNED' || typeof data.html !== 'string') return
      setTopicHtml(selectedTopic.id, extractHtmlFragment(data.html))
      showToast('已从浏览器扩展接收 HTML，预览区已更新。', { variant: 'success' })
    }
    window.addEventListener('message', handleReturnedHtml)
    return () => window.removeEventListener('message', handleReturnedHtml)
  }, [selectedTopic.id, setTopicHtml, showToast])

  useEffect(() => {
    if (!isImmersiveReading) return
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setIsImmersiveReading(false)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isImmersiveReading])

  const visibleTopics = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    return topicOptions.filter((topic) => category === 'all' || topic.category === category).filter((topic) => {
      if (!normalized) return true
      return [topic.title, topic.shortDescription, topic.level, ...topic.tags]
        .join(' ')
        .toLowerCase()
        .includes(normalized)
    })
  }, [category, query, topicOptions])

  const selectedTarget = targets.find((target) => target.id === targetId) ?? targets[0] ?? DEFAULT_TARGETS[0]
  const safeHtml = useMemo(() => sanitizeHtml(extractHtmlFragment(currentHtml)), [currentHtml])
  const iframeSrcDoc = `${BASE_IFRAME_STYLE}<body>${safeHtml || emptyPreviewMarkup(selectedTopic.title)}</body>`
  const immersiveSrcDoc = useMemo(
    () => buildImmersiveSrcDoc(extractHtmlFragment(currentHtml), selectedTopic.title),
    [currentHtml, selectedTopic.title]
  )

  const copyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(prompt)
      window.postMessage(
        {
          type: 'BINN_GRAMMAR_PROMPT_READY',
          prompt,
          topicTitle: selectedTopic.title,
          sourceUrl: window.location.href,
          targetUrl: selectedTarget.url,
        },
        window.location.origin
      )
      setIsCopied(true)
      showToast('Prompt 已复制。若已安装扩展，跳转后会尝试自动填充输入框。', { variant: 'success' })
      window.setTimeout(() => setIsCopied(false), 1800)
    } catch (err) {
      console.error('Copy grammar prompt error:', err)
      showToast('复制失败，请手动复制 prompt。', { variant: 'error' })
    }
  }

  const launchTarget = async () => {
    await copyPrompt()
    window.open(normalizeUrl(selectedTarget.url), '_blank', 'noopener,noreferrer')
  }

  const regenerateCurrentTopic = () => {
    setHtmlByTopicId((current) => {
      const next = { ...current }
      delete next[selectedTopic.id]
      return next
    })
    setBypassedCacheTopicIds((current) => uniqueList([selectedTopic.id, ...current]))
    setCacheStatusByTopicId((current) => ({ ...current, [selectedTopic.id]: 'bypassed' }))
    showToast('已清空当前知识点的 HTML。下一次返回的新 HTML 会覆盖缓存。', {
      variant: 'warning',
      duration: 5000,
    })
  }

  const copyExtensionPath = async () => {
    try {
      await navigator.clipboard.writeText(EXTENSION_PATH)
      setIsExtensionPathCopied(true)
      showToast('扩展目录路径已复制。打开 Chrome/Edge 扩展页后选择这个文件夹。', { variant: 'success' })
      window.setTimeout(() => setIsExtensionPathCopied(false), 1800)
    } catch (err) {
      console.error('Copy extension path error:', err)
      showToast(`扩展目录：${EXTENSION_PATH}`, { variant: 'info', duration: 7000 })
    }
  }

  const addTarget = () => {
    const label = newTargetLabel.trim()
    const url = normalizeUrl(newTargetUrl)
    if (!label || !url) {
      showToast('请填写目标网站名称和网址。', { variant: 'warning' })
      return
    }
    const target: GrammarTarget = {
      id: `target-${Date.now()}`,
      label,
      url,
    }
    setTargets((prev) => [...prev, target])
    setTargetId(target.id)
    setNewTargetLabel('')
    setNewTargetUrl('')
    showToast('目标网站已添加。', { variant: 'success' })
  }

  const removeTarget = (id: string) => {
    if (targets.length <= 1) {
      showToast('至少保留一个跳转目标。', { variant: 'warning' })
      return
    }
    setTargets((prev) => prev.filter((target) => target.id !== id))
    if (targetId === id) {
      const nextTarget = targets.find((target) => target.id !== id)
      if (nextTarget) setTargetId(nextTarget.id)
    }
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-5 p-6">
      <section className="rounded-xl border bg-card p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <button
              type="button"
              onClick={onBack}
              className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <ArrowLeft className="h-4 w-4" />
              {backLabel}
            </button>
            <p className="mt-4 text-sm font-semibold text-primary">语法微知识点</p>
            <h1 className="mt-1 text-2xl font-bold text-foreground">选择一个小语法点，让外部 AI 生成精讲 HTML</h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              每次只学一个具体规则，prompt 会限制篇幅和输出结构，适合 5-8 分钟读完并做两道小练习。
            </p>
          </div>
          <div className="rounded-lg border bg-background px-4 py-3 text-sm text-muted-foreground">
            当前学习者：<span className="font-medium text-foreground">{learner.nickname}</span>
          </div>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="flex min-h-[620px] flex-col rounded-xl border bg-card p-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-foreground">知识点库</h2>
              <p className="text-sm text-muted-foreground">按分类筛选，颗粒度保持在一个具体规则。</p>
            </div>
            <div className="relative w-full lg:w-72">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="w-full rounded-lg border bg-background py-2 pl-9 pr-3 text-sm outline-none transition-colors focus:border-primary"
                placeholder="搜索主将从现、since..."
              />
            </div>
          </div>

          <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
            <CategoryButton active={category === 'all'} label="全部" onClick={() => setCategory('all')} />
            {Object.entries(GRAMMAR_CATEGORY_LABELS).map(([id, label]) => (
              <CategoryButton
                key={id}
                active={category === id}
                label={label}
                onClick={() => setCategory(id as GrammarCategory)}
              />
            ))}
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-2">
            {visibleTopics.map((topic) => (
              <button
                key={topic.id}
                type="button"
                onClick={() => setSelectedTopicId(topic.id)}
                className={`min-h-[142px] rounded-lg border p-4 text-left transition-colors ${
                  selectedTopic.id === topic.id
                    ? 'border-primary bg-primary/10'
                    : 'bg-background hover:border-primary/50 hover:bg-muted/50'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs text-muted-foreground">{GRAMMAR_CATEGORY_LABELS[topic.category]}</p>
                    <h3 className="mt-1 text-base font-semibold text-foreground">{topic.title}</h3>
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    {progressByTopicId[topic.id]?.is_favorite && <Star className="h-4 w-4 fill-warning text-warning" />}
                    {progressByTopicId[topic.id]?.status === 'learned' && <CheckCircle2 className="h-4 w-4 text-success" />}
                    <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                      {topic.level}
                    </span>
                  </div>
                </div>
                <p className="mt-3 line-clamp-2 text-sm text-muted-foreground">{topic.shortDescription}</p>
                <div className="mt-3 flex flex-wrap gap-1">
                  {topic.tags.map((tag) => (
                    <span key={tag} className="rounded-md bg-primary/10 px-2 py-1 text-xs text-primary">
                      {tag}
                    </span>
                  ))}
                </div>
              </button>
            ))}
          </div>
        </section>

        <aside className="flex flex-col gap-5">
          <section className="rounded-xl border bg-card p-5">
            <h2 className="text-lg font-semibold text-foreground">生成链路</h2>
            <p className="mt-1 text-sm text-muted-foreground">先复制 prompt，再跳转到目标 AI 网站。</p>

            <div className="mt-4 rounded-lg border bg-background p-3">
              <p className="text-xs font-medium text-muted-foreground">当前知识点</p>
              <div className="mt-1 flex items-center justify-between gap-3">
                <p className="text-base font-semibold text-foreground">{selectedTopic.title}</p>
                <span className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                  打开 {currentProgress?.opened_count ?? 0} 次
                </span>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{selectedTopic.shortDescription}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() =>
                    void persistGrammarProgress(selectedTopic, {
                      is_favorite: !currentProgress?.is_favorite,
                    })
                  }
                  className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium text-foreground transition-colors hover:bg-muted"
                >
                  {currentProgress?.is_favorite ? (
                    <Star className="h-4 w-4 fill-warning text-warning" />
                  ) : (
                    <StarOff className="h-4 w-4" />
                  )}
                  {currentProgress?.is_favorite ? '取消喜爱' : '喜爱'}
                </button>
                <button
                  type="button"
                  onClick={() => void persistGrammarProgress(selectedTopic, { mark_learned: true })}
                  className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium text-foreground transition-colors hover:bg-muted disabled:opacity-60"
                  disabled={currentProgress?.status === 'learned'}
                >
                  <CheckCircle2 className="h-4 w-4 text-success" />
                  {currentProgress?.status === 'learned' ? '已学习' : '标记已学习'}
                </button>
                <button
                  type="button"
                  onClick={regenerateCurrentTopic}
                  className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium text-foreground transition-colors hover:bg-muted"
                >
                  <RefreshCw className="h-4 w-4" />
                  重新生成
                </button>
              </div>
            </div>

            <label className="mt-4 block text-sm font-medium text-foreground" htmlFor="grammar-target">
              跳转网站
            </label>
            <div className="mt-2 flex gap-2">
              <select
                id="grammar-target"
                value={selectedTarget.id}
                onChange={(event) => setTargetId(event.target.value)}
                className="min-w-0 flex-1 rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              >
                {targets.map((target) => (
                  <option key={target.id} value={target.id}>
                    {target.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => removeTarget(selectedTarget.id)}
                className="rounded-lg border p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-error"
                title="删除当前目标"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-3 grid grid-cols-[1fr_1fr_auto] gap-2">
              <input
                value={newTargetLabel}
                onChange={(event) => setNewTargetLabel(event.target.value)}
                className="min-w-0 rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                placeholder="网站名"
              />
              <input
                value={newTargetUrl}
                onChange={(event) => setNewTargetUrl(event.target.value)}
                className="min-w-0 rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                placeholder="https://..."
              />
              <button
                type="button"
                onClick={addTarget}
                className="rounded-lg border p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                title="添加网站"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-4 flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                onClick={() => void copyPrompt()}
                className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
              >
                {isCopied ? <Check className="h-4 w-4 text-success" /> : <Clipboard className="h-4 w-4" />}
                {isCopied ? '已复制' : '复制指令'}
              </button>
              <button
                type="button"
                onClick={() => void launchTarget()}
                className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                <ExternalLink className="h-4 w-4" />
                复制并跳转
              </button>
            </div>
          </section>

          <section className="rounded-xl border bg-card p-5">
            <h2 className="text-lg font-semibold text-foreground">Prompt 预览</h2>
            <textarea
              readOnly
              value={prompt}
              className="mt-3 h-64 w-full resize-none rounded-lg border bg-background p-3 text-xs leading-relaxed text-foreground outline-none"
            />
          </section>

          <section className="rounded-xl border bg-card p-5">
            <div className="flex items-center gap-2">
              <Puzzle className="h-5 w-5 text-primary" />
              <h2 className="text-lg font-semibold text-foreground">安装自动填充扩展</h2>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              需要安装本项目自带的 Chromium 扩展，安装后跳转到 DeepSeek 才能自动填入 prompt，并只把 HTML 代码片段发送回本页。
            </p>
            <ol className="mt-4 space-y-2 text-sm text-foreground">
              <li>1. 打开 Chrome/Edge 的扩展管理页：chrome://extensions 或 edge://extensions。</li>
              <li>2. 开启“开发者模式”。</li>
              <li>3. 点击“加载已解压的扩展程序”。</li>
              <li>4. 选择下面这个目录。</li>
            </ol>
            <div className="mt-3 rounded-lg border bg-background p-3">
              <p className="break-all font-mono text-xs text-foreground">{EXTENSION_PATH}</p>
            </div>
            <button
              type="button"
              onClick={() => void copyExtensionPath()}
              className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
            >
              {isExtensionPathCopied ? <Check className="h-4 w-4 text-success" /> : <Clipboard className="h-4 w-4" />}
              {isExtensionPathCopied ? '路径已复制' : '复制扩展目录'}
            </button>
            <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
              DeepSeek 的 HTML 代码区通常有复制按钮：先复制代码块，再点扩展的“发送回 BinnAgent”。如果代码块是完整 HTML 文档，扩展会保留 head/style/body。没装扩展也能用：手动粘贴 prompt，AI 输出 HTML 后再粘贴回左侧 HTML 输入区。
            </p>
          </section>
        </aside>
      </div>

      <section className="grid gap-5 xl:grid-cols-[420px_minmax(0,1fr)]">
        <div className="rounded-xl border bg-card p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-foreground">HTML 输入</h2>
              <p className="text-sm text-muted-foreground">扩展回传或手动粘贴 AI 输出的 HTML。</p>
              <p className="mt-1 text-xs text-muted-foreground">{cacheStatusText(currentCacheStatus)}</p>
            </div>
            <button
              type="button"
              onClick={() => setTopicHtml(selectedTopic.id, '')}
              className="rounded-lg border p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              title="清空 HTML"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
          <textarea
            value={currentHtml}
            onChange={(event) => setTopicHtml(selectedTopic.id, event.target.value)}
            className="mt-4 h-[460px] w-full resize-none rounded-lg border bg-background p-3 font-mono text-xs leading-relaxed text-foreground outline-none focus:border-primary"
            placeholder="把 AI 返回的 HTML 片段粘贴到这里，或使用浏览器扩展发送回 BinnAgent。"
          />
        </div>

        <div className="rounded-xl border bg-card p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <FileInput className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-semibold text-foreground">阅读预览</h2>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                预览在沙箱 iframe 中渲染，脚本、表单和 iframe 会被移除或阻止执行。
              </p>
            </div>
            <button
              type="button"
              onClick={() => setIsImmersiveReading(true)}
              className="inline-flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
            >
              <Maximize2 className="h-4 w-4" />
              沉浸阅读
            </button>
          </div>
          <iframe
            title={`${selectedTopic.title} 讲解预览`}
            sandbox=""
            srcDoc={iframeSrcDoc}
            className="mt-4 h-[520px] w-full rounded-lg border bg-white"
          />
        </div>
      </section>

      {isImmersiveReading && (
        <div className="fixed inset-0 z-[80] bg-white">
          <div className="pointer-events-none absolute left-4 right-4 top-4 z-[90] flex items-start justify-between gap-3">
            <div className="pointer-events-auto rounded-lg border bg-background/95 px-3 py-2 shadow-lg backdrop-blur">
              <p className="max-w-[60vw] truncate text-sm font-semibold text-foreground">{selectedTopic.title}</p>
              <p className="text-xs text-muted-foreground">原样沉浸式阅读，按 Esc 可退出</p>
            </div>
            <button
              type="button"
              onClick={() => setIsImmersiveReading(false)}
              className="pointer-events-auto inline-flex items-center gap-2 rounded-lg border bg-background/95 px-3 py-2 text-sm font-medium text-foreground shadow-lg backdrop-blur transition-colors hover:bg-muted"
            >
              <X className="h-4 w-4" />
              退出
            </button>
          </div>
          <iframe
            title={`${selectedTopic.title} 沉浸式阅读`}
            srcDoc={immersiveSrcDoc}
            className="h-screen w-screen border-0 bg-white"
          />
        </div>
      )}
    </div>
  )
}

function CategoryButton({
  active,
  label,
  onClick,
}: {
  active: boolean
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`shrink-0 rounded-lg border px-3 py-2 text-sm transition-colors ${
        active
          ? 'border-primary bg-primary/10 font-medium text-primary'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground'
      }`}
    >
      {label}
    </button>
  )
}

function buildGrammarPrompt(topic: GrammarTopic) {
  return `请为英语学习者讲解一个“语法微知识点”：${topic.title}。

请严格遵守：
1. 只讲这个微知识点，不要扩展到“${GRAMMAR_CATEGORY_LABELS[topic.category]}”整个大类，也不要写成长篇语法课。
2. 内容控制在约 600-900 中文字等量，适合 5-8 分钟阅读；可以讲得具体，但不要发散。
3. 仅输出一个 HTML 片段，不要 Markdown 代码围栏，不要解释 HTML 之外的文字。
4. HTML 结构必须包含：标题、适用场景、核心规则、3-5 个英文例句及中文解释、常见误区、2 道小练习、答案。
5. 例句必须服务“${topic.title}”这个知识点；如果是主将从现，只讲时间/条件状语从句中从句用一般现在时表示将来。
6. 禁止输出 <script>、外链 JS、表单、iframe、自动播放媒体。

学习者背景：CET 四六级备考，喜欢中英结合、规则清楚、例句实用。
知识点简介：${topic.shortDescription}
相关标签：${topic.tags.join('、')}`
}

function createGrammarTopic(title: string): GrammarTopic {
  const normalizedTitle = title.trim()
  return {
    id: `knowledge-${stableHash(normalizedTitle.toLocaleLowerCase())}`,
    category: inferGrammarCategory(normalizedTitle),
    title: normalizedTitle,
    level: '基础',
    tags: ['教材语法', '单元知识'],
    shortDescription: `来自教材单元知识的语法点“${normalizedTitle}”，请围绕该标题识别并讲清最核心的规则。`,
  }
}

function inferGrammarCategory(title: string): GrammarCategory {
  const normalized = title.toLocaleLowerCase()
  if (/冠词|article|介词|preposition/.test(normalized)) return 'article-preposition'
  if (/时态|tense|现在时|过去时|将来时/.test(normalized)) return 'tense'
  if (/从句|clause|疑问句|question/.test(normalized)) return 'clause'
  if (/非谓语|不定式|动名词|分词/.test(normalized)) return 'nonfinite'
  if (/虚拟|subjunctive/.test(normalized)) return 'subjunctive'
  if (/情态|modal/.test(normalized)) return 'modal'
  if (/主谓一致|agreement/.test(normalized)) return 'agreement'
  if (/易错|辨析|区别/.test(normalized)) return 'error-prone'
  return 'sentence-structure'
}

function readStoredGrammarState(): Partial<StoredGrammarState> & {
  htmlByTopicId: Record<string, string>
  targets: GrammarTarget[]
} {
  const fallback = { htmlByTopicId: {}, targets: [] }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return fallback
    const stored = JSON.parse(raw) as Partial<StoredGrammarState>
    const htmlByTopicId =
      stored.htmlByTopicId && typeof stored.htmlByTopicId === 'object'
        ? stored.htmlByTopicId
        : typeof stored.html === 'string' && typeof stored.topicId === 'string'
          ? { [stored.topicId]: stored.html }
          : {}
    return {
      topicId: typeof stored.topicId === 'string' ? stored.topicId : undefined,
      targetId: typeof stored.targetId === 'string' ? stored.targetId : undefined,
      htmlByTopicId,
      targets: Array.isArray(stored.targets) ? stored.targets.filter(isGrammarTarget) : [],
    }
  } catch {
    localStorage.removeItem(STORAGE_KEY)
    return fallback
  }
}

function isGrammarTarget(value: unknown): value is GrammarTarget {
  if (!value || typeof value !== 'object') return false
  const target = value as Partial<GrammarTarget>
  return typeof target.id === 'string' && typeof target.label === 'string' && typeof target.url === 'string'
}

function normalizeUrl(value: string) {
  const trimmed = value.trim()
  if (!trimmed) return ''
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  return `https://${trimmed}`
}

function uniqueList(items: string[]) {
  return Array.from(new Set(items))
}

function stableHash(value: string) {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(16).padStart(8, '0')
}

function cacheStatusText(status: CacheStatus) {
  if (status === 'loading') return '正在查找缓存...'
  if (status === 'hit') return '已使用缓存讲解，可直接阅读或重新生成。'
  if (status === 'miss') return '暂无缓存，可复制指令生成。'
  if (status === 'saving') return '正在保存 HTML 缓存...'
  if (status === 'saved') return 'HTML 已保存到缓存。'
  if (status === 'bypassed') return '已跳过缓存，请重新生成当前知识点。'
  if (status === 'error') return '缓存服务暂时不可用，本地内容仍可使用。'
  return '选择知识点后会自动查找缓存。'
}

function extractHtmlFragment(value: string) {
  const fenced = value.match(/```(?:html)?\s*([\s\S]*?)```/i)
  return (fenced?.[1] ?? value).trim()
}

function sanitizeHtml(value: string) {
  if (!value.trim()) return ''
  const parser = new DOMParser()
  const doc = parser.parseFromString(value, 'text/html')
  doc.querySelectorAll('script, iframe, form, object, embed, link, meta, base').forEach((node) => node.remove())
  doc.querySelectorAll('*').forEach((node) => {
    for (const attribute of Array.from(node.attributes)) {
      const name = attribute.name.toLowerCase()
      const attrValue = attribute.value.trim().toLowerCase()
      if (name.startsWith('on')) node.removeAttribute(attribute.name)
      if ((name === 'href' || name === 'src') && attrValue.startsWith('javascript:')) {
        node.removeAttribute(attribute.name)
      }
      if (name === 'src' && /^https?:\/\//i.test(attribute.value)) {
        node.removeAttribute(attribute.name)
      }
    }
  })
  return doc.body.innerHTML
}

function buildImmersiveSrcDoc(value: string, topicTitle: string) {
  const html = value.trim()
  if (!html) {
    return `<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>${escapeHtml(topicTitle)}</title></head><body>${emptyPreviewMarkup(topicTitle)}</body></html>`
  }
  if (/<!doctype html/i.test(html) || /<html[\s>]/i.test(html)) return html
  return `<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>${escapeHtml(topicTitle)}</title></head><body>${html}</body></html>`
}

function emptyPreviewMarkup(topicTitle: string) {
  return `
    <main>
      <h1>${escapeHtml(topicTitle)} 讲解预览</h1>
      <p>从目标 AI 网站复制 HTML 后粘贴到左侧，或使用浏览器扩展发送回 BinnAgent。</p>
      <blockquote>这里会渲染一个适合阅读的语法微课页面。</blockquote>
    </main>
  `
}

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}
