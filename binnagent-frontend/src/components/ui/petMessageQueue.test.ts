import { describe, expect, it } from 'vitest'
import { enqueuePetMessage, type QueueMessage } from './petMessageQueue'

function message(id: string, variant: QueueMessage['variant'], text = id): QueueMessage {
  return { id, message: text, variant }
}

describe('pet message queue', () => {
  it('lets urgent messages preempt informational guidance', () => {
    const queue = enqueuePetMessage(
      [message('intro', 'info'), message('saved', 'success')],
      message('failure', 'error'),
      5,
    )
    expect(queue.map((item) => item.id)).toEqual(['failure', 'saved', 'intro'])
  })

  it('keeps equal-priority messages stable and coalesces duplicates', () => {
    const queue = enqueuePetMessage(
      [message('first', 'info', 'Same'), message('second', 'info', 'Other')],
      message('latest', 'info', 'Same'),
      5,
    )
    expect(queue.map((item) => item.id)).toEqual(['second', 'latest'])
  })

  it('caps the queue after priority ordering', () => {
    const queue = enqueuePetMessage(
      [message('one', 'info'), message('two', 'info'), message('three', 'warning')],
      message('four', 'error'),
      3,
    )
    expect(queue.map((item) => item.id)).toEqual(['four', 'three', 'one'])
  })

  it('lets active work feedback preempt ordinary info without outranking success', () => {
    const queue = enqueuePetMessage(
      [message('intro', 'info'), message('done', 'success')],
      { ...message('working', 'info'), priority: 5 },
      5,
    )
    expect(queue.map((item) => item.id)).toEqual(['done', 'working', 'intro'])
  })
})
