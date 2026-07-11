import { describe, expect, it } from 'vitest'
import chatContainerSource from './ChatContainer.tsx?raw'

describe('ChatContainer mobile scroll behavior', () => {
  it('lets readers leave the bottom during streamed assistant output', () => {
    expect(chatContainerSource).not.toContain('scrollIntoView')
    expect(chatContainerSource).toContain('distanceFromBottom < 96')
    expect(chatContainerSource).toContain('pauseAutoScrollForReading')
    expect(chatContainerSource).toContain('if (!shouldAutoScrollRef.current) return')
    expect(chatContainerSource).toContain("messages[messages.length - 1]?.role === 'user'")
    expect(chatContainerSource).toContain('binn-viewport-height')
    expect(chatContainerSource).toContain('data-header-scroll-surface')
  })
})
