import { useRef, useEffect } from 'react'
import { useChat } from '@/hooks/useChat'
import { MessageBubble } from './MessageBubble'
import { ChatInput } from './ChatInput'
import { TypingIndicator } from './TypingIndicator'
import { WelcomeScreen } from './WelcomeScreen'

export function ChatContainer() {
  const { messages, sendMessage, cancel, isLoading } = useChat()
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleStartLesson = () => sendMessage('开始一节对话课')
  const handleReviewVocab = () => sendMessage('我想复习今天的词汇')
  const handlePracticeSpeaking = () => sendMessage('我想练习口语场景')

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <WelcomeScreen
            onStartLesson={handleStartLesson}
            onReviewVocab={handleReviewVocab}
            onPracticeSpeaking={handlePracticeSpeaking}
          />
        ) : (
          messages.map(msg => (
            <MessageBubble
              key={msg.id}
              role={msg.role}
              content={msg.content}
              timestamp={msg.timestamp}
              isStreaming={isLoading && msg.role === 'assistant' && msg === messages[messages.length - 1]}
            />
          ))
        )}
        {isLoading && messages[messages.length - 1]?.content === '' && (
          <TypingIndicator />
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t p-4">
        <ChatInput onSend={sendMessage} onCancel={cancel} isLoading={isLoading} />
      </div>
    </div>
  )
}
