import { useState, useRef, useCallback, useEffect } from 'react'
import type { ChatMessage, ChatSkillEvent, ConversationThread, MemorySummary } from '@/types'

interface HistoryResponse {
  thread_id: string | null
  skill_id?: string | null
  skill_name?: string | null
  messages: Array<{
    id: string
    role: 'user' | 'assistant'
    content: string
    created_at: string
  }>
}

interface StreamEvent {
  event: string
  data: Record<string, unknown>
}

function parseSseEvent(rawEvent: string): StreamEvent | null {
  const lines = rawEvent.split('\n')
  let event = 'message'
  const dataLines: string[] = []

  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trimStart())
    }
  }

  if (dataLines.length === 0) return null

  try {
    return { event, data: JSON.parse(dataLines.join('\n')) as Record<string, unknown> }
  } catch {
    return null
  }
}

function stripContinuationStatus(content: string): string {
  return content.replace(/\n\n_正在继续生成\.\.\._$/u, '')
}

export function useChat(
  learnerId: string,
  options: { onGeneratingChange?: (isGenerating: boolean) => void } = {}
) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [threadId, setThreadId] = useState<string | null>(null)
  const [conversations, setConversations] = useState<ConversationThread[]>([])
  const [memorySummary, setMemorySummary] = useState<MemorySummary | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(true)
  const [skillStatus, setSkillStatus] = useState('')
  const [activeSkillId, setActiveSkillId] = useState<string | null>(null)
  const [activeSkillName, setActiveSkillName] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const onGeneratingChangeRef = useRef(options.onGeneratingChange)

  useEffect(() => {
    onGeneratingChangeRef.current = options.onGeneratingChange
  }, [options.onGeneratingChange])

  const loadConversations = useCallback(async () => {
    const response = await fetch(`/api/learners/${learnerId}/conversations`)
    if (!response.ok) throw new Error('Failed to load conversations')
    const data: ConversationThread[] = await response.json()
    setConversations(data)
    return data
  }, [learnerId])

  const loadMemorySummary = useCallback(async () => {
    const response = await fetch(`/api/learners/${learnerId}/memory/summary`)
    if (!response.ok) throw new Error('Failed to load memory summary')
    const data: MemorySummary = await response.json()
    setMemorySummary(data)
    return data
  }, [learnerId])

  const loadThread = useCallback(async (nextThreadId: string) => {
    setIsLoadingHistory(true)
    try {
      const response = await fetch(
        `/api/learners/${learnerId}/conversations/${nextThreadId}/messages`
      )
      if (!response.ok) throw new Error('Failed to load thread messages')
      const data: HistoryResponse['messages'] = await response.json()
      const conversation = conversations.find(item => item.thread_id === nextThreadId)
      setThreadId(nextThreadId)
      setActiveSkillId(conversation?.skill_id ?? null)
      setActiveSkillName(conversation?.skill_name ?? null)
      setSkillStatus('')
      setMessages(data.map(toChatMessage))
    } catch (err) {
      console.error('Conversation thread error:', err)
      setThreadId(null)
      setMessages([])
    } finally {
      setIsLoadingHistory(false)
    }
  }, [conversations, learnerId])

  const startNewConversation = useCallback(() => {
    setThreadId(null)
    setMessages([])
    setSkillStatus('')
    setActiveSkillId(null)
    setActiveSkillName(null)
  }, [])

  const exitSkill = useCallback(async () => {
    if (!threadId) {
      setActiveSkillId(null)
      setActiveSkillName(null)
      setSkillStatus('')
      return
    }

    try {
      const response = await fetch(`/api/learners/${learnerId}/conversations/${threadId}/skill`, {
        method: 'DELETE',
      })
      if (!response.ok) throw new Error('Failed to exit skill')
      setActiveSkillId(null)
      setActiveSkillName(null)
      setSkillStatus('')
      void loadConversations()
    } catch (err) {
      console.error('Exit skill error:', err)
      setSkillStatus('退出 Skill 失败，请稍后重试。')
    }
  }, [learnerId, loadConversations, threadId])

  useEffect(() => {
    let cancelled = false

    const timer = window.setTimeout(() => {
      Promise.all([
        fetch(`/api/learners/${learnerId}/conversations/latest`).then((response) => {
          if (!response.ok) throw new Error('Failed to load conversation history')
          return response.json() as Promise<HistoryResponse>
        }),
        loadConversations(),
        loadMemorySummary(),
      ])
        .then(([latest]) => {
          if (cancelled) return
          setThreadId(latest.thread_id)
          setActiveSkillId(latest.skill_id ?? null)
          setActiveSkillName(latest.skill_name ?? null)
          setMessages(latest.messages.map(toChatMessage))
        })
        .catch((err) => {
          if (!cancelled) {
            console.error('Conversation history error:', err)
            setMessages([])
            setThreadId(null)
          }
        })
        .finally(() => {
          if (!cancelled) setIsLoadingHistory(false)
        })
    }, 0)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [learnerId, loadConversations, loadMemorySummary])

  const sendMessage = useCallback(async (content: string, skillId?: string | null) => {
    setSkillStatus('')
    const requestedSkillId = skillId ?? activeSkillId
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    setMessages(prev => [...prev, userMsg])
    setIsLoading(true)
    onGeneratingChangeRef.current?.(true)

    const assistantId = crypto.randomUUID()
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
    }
    setMessages(prev => [...prev, assistantMsg])

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          learner_id: learnerId,
          message: content,
          thread_id: threadId,
          skill_id: requestedSkillId || undefined,
        }),
        signal: controller.signal,
      })

      if (!response.ok || !response.body) throw new Error('Chat stream request failed')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      const handleStreamEvent = (parsed: StreamEvent) => {
        if (parsed.event === 'meta' && typeof parsed.data.thread_id === 'string') {
          setThreadId(parsed.data.thread_id)
          setActiveSkillId(typeof parsed.data.skill_id === 'string' ? parsed.data.skill_id : null)
          setActiveSkillName(typeof parsed.data.skill_name === 'string' ? parsed.data.skill_name : null)
        }

        if (parsed.event === 'delta' && typeof parsed.data.content === 'string') {
          const delta = parsed.data.content
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? { ...m, content: `${stripContinuationStatus(m.content)}${delta}` }
                : m
            )
          )
        }

        if (parsed.event === 'continuation') {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? { ...m, content: `${m.content}\n\n_正在继续生成..._` }
                : m
            )
          )
        }

      if (parsed.event === 'done') {
        setIsLoading(false)
        onGeneratingChangeRef.current?.(false)
          if (typeof parsed.data.thread_id === 'string') {
            setThreadId(parsed.data.thread_id)
          }
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? {
                    ...m,
                    id: typeof parsed.data.message_id === 'string' ? parsed.data.message_id : m.id,
                    content: typeof parsed.data.reply === 'string' ? parsed.data.reply : m.content,
                  }
                : m
            )
          )
          void loadConversations()
          void loadMemorySummary()
        }

        if (parsed.event === 'skill') {
          const event = parsed.data as unknown as ChatSkillEvent
          if (event.skill_id) {
            setActiveSkillId(event.skill_id)
          }
          if (event.skill_name) {
            setActiveSkillName(event.skill_name)
          }
          if (event.name !== 'vocabulary_agent') return
          if (event.status === 'started') {
            setSkillStatus(event.message || '词汇 Agent 正在后台整理词卡...')
          } else if (event.status === 'completed') {
            setSkillStatus(event.message || `已沉淀 ${event.saved_count ?? 0} 个词到词汇本`)
            void loadMemorySummary()
          } else if (event.status === 'skipped') {
            setSkillStatus(event.message || '本轮没有发现符合标准的可沉淀词汇')
          } else if (event.status === 'failed') {
            setSkillStatus(event.message || '词汇沉淀暂时失败，对话内容已保留')
          }
        }

        if (parsed.event === 'error') {
          throw new Error(
            typeof parsed.data.detail === 'string'
              ? parsed.data.detail
              : 'Chat stream failed'
          )
        }
      }

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop() ?? ''

        for (const rawEvent of events) {
          const parsed = parseSseEvent(rawEvent)
          if (!parsed) continue
          handleStreamEvent(parsed)
        }
      }

      const trailingEvent = parseSseEvent(buffer.trim())
      if (trailingEvent) {
        handleStreamEvent(trailingEvent)
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        setMessages(prev =>
          prev.filter(m => m.id !== assistantId || m.content.trim().length > 0)
        )
      } else if (err instanceof Error) {
        console.error('Chat error:', err)
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantId
              ? {
                  ...m,
                  content: m.content
                    ? `${m.content}\n\n_流式连接失败，请检查 Ollama / 后端 SSE / 代理配置_`
                    : '流式连接失败，请检查 Ollama / 后端 SSE / 代理配置',
                }
              : m
          )
        )
      }
    } finally {
      setIsLoading(false)
      onGeneratingChangeRef.current?.(false)
      abortRef.current = null
    }
  }, [activeSkillId, learnerId, threadId, loadConversations, loadMemorySummary])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    setIsLoading(false)
    onGeneratingChangeRef.current?.(false)
  }, [])

  return {
    messages,
    threadId,
    conversations,
    memorySummary,
    skillStatus,
    activeSkillId,
    activeSkillName,
    sendMessage,
    cancel,
    exitSkill,
    loadThread,
    startNewConversation,
    isLoading,
    isLoadingHistory,
  }
}

function toChatMessage(message: HistoryResponse['messages'][number]): ChatMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    timestamp: new Date(message.created_at).getTime(),
  }
}
