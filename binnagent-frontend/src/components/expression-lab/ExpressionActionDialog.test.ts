import { describe, expect, it } from 'vitest'
import type { ExpressionSystemAction } from '@/services/expressionLabApi'
import {
  buildExpressionActionEdits,
  editableFieldsForAction,
} from './ExpressionActionDialog'

function vocabularyAction(
  editableFields: string[],
): ExpressionSystemAction {
  return {
    id: 'action-1',
    type: 'save_vocabulary',
    label: '加入词汇本',
    requires_confirmation: true,
    editable_fields: editableFields,
    payload: {
      word: 'absolute',
      meaning: '绝对的',
      collocations: ['absolute certainty'],
      source_expression: 'That claim sounds too absolute.',
    },
  }
}

describe('Expression Lab action edit boundary', () => {
  it('treats an empty server editable_fields list as no edit permission', () => {
    const action = vocabularyAction([])

    expect(editableFieldsForAction(action)).toEqual([])
    expect(buildExpressionActionEdits(action, { word: 'categorical' })).toEqual({})
  })

  it('uses the intersection of server fields, client allowlist, and payload fields', () => {
    const action = vocabularyAction(['meaning', 'type', 'unknown', 'word'])

    expect(editableFieldsForAction(action)).toEqual(['meaning', 'word'])
    expect(buildExpressionActionEdits(action, {
      meaning: '武断的；绝对的',
      word: 'categorical',
      type: 'save_writing_phrase',
      unknown: 'exfiltrate',
    })).toEqual({
      meaning: '武断的；绝对的',
      word: 'categorical',
    })
  })

  it('normalizes editable string-list values without changing noneditable payload', () => {
    const action = vocabularyAction(['collocations'])

    expect(buildExpressionActionEdits(action, {
      collocations: 'absolute certainty\nabsolute power, absolute majority',
      word: 'must stay ignored',
    })).toEqual({
      collocations: ['absolute certainty', 'absolute power', 'absolute majority'],
    })
  })

  it('lets the user choose one to three generated practice questions', () => {
    const action: ExpressionSystemAction = {
      id: 'practice-1',
      type: 'create_practice',
      label: '生成练习',
      requires_confirmation: true,
      editable_fields: ['count', 'focus', 'action_type'],
      payload: { count: 2, focus: '委婉表达迁移' },
    }

    expect(editableFieldsForAction(action)).toEqual(['count', 'focus'])
    expect(buildExpressionActionEdits(action, { count: '3', focus: '正式写作' })).toEqual({
      count: 3,
      focus: '正式写作',
    })
  })
})
