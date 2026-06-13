import { ChatContainer } from '@/components/chat/ChatContainer'
import type { Learner } from '@/types'

interface ChatPageProps {
  learner: Learner
}

export function ChatPage({ learner }: ChatPageProps) {
  return <ChatContainer learnerId={learner.id} />
}
