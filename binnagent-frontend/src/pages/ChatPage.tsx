import { ChatContainer } from '@/components/chat/ChatContainer'
import type { Learner } from '@/types'

interface ChatPageProps {
  learner: Learner
  draft: string
  onDraftChange: (value: string) => void
}

export function ChatPage({ learner, draft, onDraftChange }: ChatPageProps) {
  return (
    <ChatContainer
      learnerId={learner.id}
      draft={draft}
      onDraftChange={onDraftChange}
    />
  )
}
