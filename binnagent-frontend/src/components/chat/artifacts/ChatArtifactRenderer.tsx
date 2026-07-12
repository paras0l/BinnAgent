import type { ChatArtifact } from './chatArtifacts'
import { ImageBoardArtifact } from './ImageBoardArtifact'
import { InteractiveHtmlArtifact } from './InteractiveHtmlArtifact'

interface ChatArtifactRendererProps {
  artifact: ChatArtifact
  disabled?: boolean
  onAction: (prompt: string) => void
}

export function ChatArtifactRenderer({ artifact, disabled, onAction }: ChatArtifactRendererProps) {
  switch (artifact.type) {
    case 'image_board':
      return <ImageBoardArtifact artifact={artifact} disabled={disabled} onAction={onAction} />
    case 'interactive_html':
      return <InteractiveHtmlArtifact artifact={artifact} disabled={disabled} onAction={onAction} />
  }
}
