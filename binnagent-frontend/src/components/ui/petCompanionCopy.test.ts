import { describe, expect, it } from 'vitest'
import { companionizePetMessage, loadingCompanionMessage } from './petCompanionCopy'

describe('pet companion copy', () => {
  it('uses collaborative language for memory and learning loads', () => {
    expect(loadingCompanionMessage('正在读取学习记忆')).toContain('我们')
    expect(loadingCompanionMessage('正在加载学习中心')).toContain('陪你')
  })

  it('always returns a calm fallback without commands', () => {
    const message = loadingCompanionMessage('正在打开页面')
    expect(message).toContain('一起')
    expect(message).not.toContain('请')
    expect(message).not.toContain('错误')
  })

  it('softens legacy command and failure phrases in pet messages', () => {
    expect(companionizePetMessage('请先完成练习')).toBe('我们先完成练习')
    expect(companionizePetMessage('保存失败，请重试')).toBe('保存还没完成，我们一起再试')
    expect(companionizePetMessage('让我来教你')).toBe('我陪你拆开它')
  })
})
