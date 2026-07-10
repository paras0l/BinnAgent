import { describe, expect, it } from 'vitest'
import type { ExpressionSystemAction } from '@/services/expressionLabApi'
import { findExpressionAction } from './actionMatching'

const actions: ExpressionSystemAction[] = [
  {
    id: 'neutral',
    type: 'save_writing_phrase',
    label: '收藏中性表达',
    status: 'candidate',
    payload: { text: 'That point may be too absolute.' },
  },
  {
    id: 'polite',
    type: 'save_writing_phrase',
    label: '收藏委婉表达',
    status: 'saved',
    payload: { text: 'That claim may be a little too strong.' },
  },
]

describe('Expression block action matching', () => {
  it('keeps a saved action attached to its original expression', () => {
    expect(findExpressionAction(
      actions,
      'save_writing_phrase',
      'That claim may be a little too strong.',
    )?.id).toBe('polite')
  })

  it('does not attach the only remaining candidate to unrelated content', () => {
    expect(findExpressionAction(
      actions.filter((action) => action.status !== 'saved'),
      'save_writing_phrase',
      'This is a different expression.',
    )).toBeUndefined()
  })
})
