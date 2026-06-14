import { ChatContainer } from '@/components/chat/ChatContainer'
import type { Learner } from '@/types'

interface ChatPageProps {
  learner: Learner
  draft: string
  onDraftChange: (value: string) => void
  skillFocus: string | null
  onSkillFocusChange: (value: string | null) => void
  onGeneratingChange: (isGenerating: boolean) => void
  onLockedAction: () => void
}

export function ChatPage({
  learner,
  draft,
  onDraftChange,
  skillFocus,
  onSkillFocusChange,
  onGeneratingChange,
  onLockedAction,
}: ChatPageProps) {
  return (
    <ChatContainer
      learnerId={learner.id}
      draft={draft}
      onDraftChange={onDraftChange}
      skillFocus={skillFocus}
      onSkillFocusChange={onSkillFocusChange}
      onGeneratingChange={onGeneratingChange}
      onLockedAction={onLockedAction}
    />
  )
}
