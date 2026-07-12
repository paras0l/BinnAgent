import { describe, expect, it } from 'vitest'
import source from './InteractiveHtmlArtifact.tsx?raw'

describe('InteractiveHtmlArtifact confirmation boundary', () => {
  it('buffers sandbox events until the learner confirms sending them to chat', () => {
    expect(source).toContain('setPendingEvent(event)')
    expect(source).toContain('组件已产生结果，确认后再发送给 AI。')
    expect(source).toContain('onClick={sendPendingEvent}')
    expect(source).toContain('结果待确认 · 带入对话')
    expect(source).not.toContain("if (disabled || ['ready', 'resize', 'timeout', 'rebuild'].includes(event.type)) return\n    onAction(")
  })

  it('keeps sandbox errors out of the learner answer flow', () => {
    expect(source).toContain("typeof event.payload.error === 'string'")
    expect(source).toContain('组件脚本触发安全限制，没有执行，也没有发送任何学习结果。')
    expect(source).toContain('onClick={requestSafeRebuild}')
  })
})
