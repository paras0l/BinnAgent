import { ChatContainer } from '@/components/chat/ChatContainer'
import type { Learner } from '@/types'

interface ChatPageProps {
  learner: Learner
  draft: string
  onDraftChange: (value: string) => void
  pendingPrompt?: {
    id: number
    prompt: string
    skillFocus: string | null
  } | null
  onPendingPromptConsumed?: () => void
  skillFocus: string | null
  onSkillFocusChange: (value: string | null) => void
  onGeneratingChange: (isGenerating: boolean) => void
  onLockedAction: () => void
}

export function ChatPage({
  learner,
  draft,
  onDraftChange,
  pendingPrompt,
  onPendingPromptConsumed,
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
      pendingPrompt={pendingPrompt}
      onPendingPromptConsumed={onPendingPromptConsumed}
      skillFocus={skillFocus}
      onSkillFocusChange={onSkillFocusChange}
      onGeneratingChange={onGeneratingChange}
      onLockedAction={onLockedAction}
    />
  )
}
