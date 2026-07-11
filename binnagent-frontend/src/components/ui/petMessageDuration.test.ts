import { describe, expect, it } from 'vitest'
import { petMessageDuration } from './petMessageDuration'

describe('petMessageDuration', () => {
  it('keeps more important messages visible longer', () => {
    const message = '我们一起看看这条学习线索。'
    const info = petMessageDuration({ message, variant: 'info' })
    const warning = petMessageDuration({ message, variant: 'warning' })
    const error = petMessageDuration({ message, variant: 'error' })

    expect(warning).toBeGreaterThan(info)
    expect(error).toBeGreaterThan(warning)
  })

  it('adds reading time for longer copy and its title', () => {
    const short = petMessageDuration({ message: '我们继续。', variant: 'info' })
    const long = petMessageDuration({
      title: '我们的学习记忆',
      message: '我把这次找到的学习线索记下来了，下次我们可以从这里接着走。',
      variant: 'info',
    })

    expect(long).toBeGreaterThan(short)
  })

  it('weights explicit priority but respects the variant maximum', () => {
    const normal = petMessageDuration({ message: '正在整理。', priority: 0, variant: 'info' })
    const important = petMessageDuration({ message: '正在整理。', priority: 5, variant: 'info' })
    const capped = petMessageDuration({ message: '长'.repeat(300), priority: 9, variant: 'info' })

    expect(important).toBeGreaterThan(normal)
    expect(capped).toBe(10_000)
  })
})
