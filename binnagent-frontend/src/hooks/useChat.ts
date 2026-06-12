import { useState, useRef, useCallback } from 'react'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (content: string) => {
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    setMessages(prev => [...prev, userMsg])
    setIsLoading(true)

    const assistantId = crypto.randomUUID()
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
    }
    setMessages(prev => [...prev, assistantMsg])

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const response = await fetch('/api/chat/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: content }),
        signal: controller.signal,
      })

      if (!response.ok) throw new Error('Chat request failed')
      
      const data = await response.json()
      
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId
            ? { ...m, content: data.response || data.message || 'Sorry, I could not process your request.' }
            : m
        )
      )
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== 'AbortError') {
        console.error('Chat error:', err)
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantId
              ? { ...m, content: '抱歉，发生了错误。请稍后重试。' }
              : m
          )
        )
      }
    } finally {
      setIsLoading(false)
      abortRef.current = null
    }
  }, [])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    setIsLoading(false)
  }, [])

  return { messages, sendMessage, cancel, isLoading }
}
