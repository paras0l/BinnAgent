/* eslint-disable react-refresh/only-export-components -- Action boundary helpers are exported for regression tests. */
import { useMemo, useState, type ChangeEvent } from 'react'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { FormField } from '@/components/ui/FormField'
import type { ExpressionSystemAction } from '@/services/expressionLabApi'
import { displayValue } from './blockData'

export const ACTION_EDITABLE_FIELDS: Record<string, string[]> = {
  save_writing_phrase: ['text', 'chinese_meaning', 'explanation', 'usage_scene', 'register', 'template', 'examples', 'tags'],
  save_vocabulary: ['word', 'meaning', 'collocations', 'examples', 'source_expression', 'reason'],
  save_grammar_point: ['topic', 'rule', 'error', 'correction', 'minimal_pairs'],
  create_practice: ['count', 'focus'],
}

interface ExpressionActionDialogProps {
  action: ExpressionSystemAction | null
  isBusy: boolean
  onCancel: () => void
  onConfirm: (payloadOverrides: Record<string, unknown>) => void
}

export function ExpressionActionDialog({ action, isBusy, onCancel, onConfirm }: ExpressionActionDialogProps) {
  if (!action) return null
  return <ExpressionActionDialogForm key={action.id} action={action} isBusy={isBusy} onCancel={onCancel} onConfirm={onConfirm} />
}

function ExpressionActionDialogForm({ action, isBusy, onCancel, onConfirm }: ExpressionActionDialogProps & { action: ExpressionSystemAction }) {
  const editableFields = useMemo(() => action ? editableFieldsForAction(action) : [], [action])
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(
    editableFieldsForAction(action).map((field) => [field, editableValue(action.payload[field])]),
  ))

  return (
    <ConfirmDialog
      open
      title={dialogTitle(action)}
      description={dialogDescription(action)}
      confirmLabel={isBusy ? '正在保存…' : action.label}
      isBusy={isBusy}
      onCancel={onCancel}
      onConfirm={() => onConfirm(buildExpressionActionEdits(action, values))}
    >
      {editableFields.length > 0 ? (
        <div className="max-h-[52dvh] space-y-3 overflow-y-auto overscroll-contain pr-1">
          {editableFields.map((field) => {
            const value = values[field] ?? ''
            const useTextarea = ['text', 'rule', 'examples', 'usage_scene', 'source_expression', 'minimal_pairs', 'reason', 'note'].includes(field)
            const handleChange = (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setValues((current) => ({ ...current, [field]: event.target.value }))
            return useTextarea ? (
              <FormField
                key={field}
                as="textarea"
                label={fieldLabel(field)}
                name={`expression_action_${field}`}
                value={value}
                onChange={handleChange}
              />
            ) : (
              <FormField key={field} label={fieldLabel(field)} name={`expression_action_${field}`} value={value} onChange={handleChange} type={field === 'count' ? 'number' : 'text'} min={field === 'count' ? 1 : undefined} max={field === 'count' ? 3 : undefined} step={field === 'count' ? 1 : undefined} />
            )
          })}
        </div>
      ) : (
        <p className="rounded-lg bg-slate-50 p-3 text-sm leading-6 text-slate-600">这项操作没有需要编辑的字段，确认后执行。</p>
      )}
    </ConfirmDialog>
  )
}

export function editableFieldsForAction(action: ExpressionSystemAction) {
  const whitelist = ACTION_EDITABLE_FIELDS[action.type] ?? []
  const serverFields = action.editable_fields ?? []
  return serverFields.filter((field) => whitelist.includes(field) && field in action.payload)
}

export function buildExpressionActionEdits(action: ExpressionSystemAction, values: Record<string, string>) {
  return Object.fromEntries(editableFieldsForAction(action).map((field) => {
    const original = action.payload[field]
    const value = values[field]?.trim() ?? ''
    if (Array.isArray(original)) {
      if (original.every((item) => typeof item === 'string')) return [field, value.split(/\n|,/).map((item) => item.trim()).filter(Boolean)]
      return [field, parseStructuredValue(value, original)]
    }
    if (original && typeof original === 'object') return [field, parseStructuredValue(value, original)]
    if (typeof original === 'number') return [field, Number(value) || original]
    if (typeof original === 'boolean') return [field, value === 'true' || value === '是']
    return [field, value]
  }))
}

function dialogTitle(action: ExpressionSystemAction) {
  if (action.type === 'save_writing_phrase') return '确认收藏表达'
  if (action.type === 'save_vocabulary') return '确认加入词汇本'
  if (action.type === 'save_grammar_point') return '确认记录语法点'
  if (action.type === 'create_practice') return '确认生成练习'
  if (action.type === 'dismiss_suggestion') return '确认这条建议不适合你'
  return `确认${action.label}`
}

function dialogDescription(action: ExpressionSystemAction) {
  if (['save_writing_phrase', 'save_vocabulary', 'save_grammar_point'].includes(action.type)) return '保存前可以检查并修改下面的内容。只有你确认后，系统才会写入长期学习资产。'
  if (action.type === 'create_practice') return '确认练习数量和类型后，系统会把练习加入本次学习。'
  if (action.type === 'copy_expression') return '确认后复制表达，并记录本次学习动作。'
  if (action.type === 'dismiss_suggestion') return '这会记录你的反馈，但不会删除输入或已经保存的资产。'
  if (action.type === 'mark_completed') return '确认后结束本次学习，会话和已完成练习仍可回看。'
  return '请检查这项操作，确认后系统才会执行。'
}

function fieldLabel(field: string) {
  const labels: Record<string, string> = {
    text: '英文表达', chinese_meaning: '中文含义', explanation: '说明', usage_scene: '使用场景', register: '语域 / 语气', template: '迁移模板', examples: '例句（结构化内容）', tags: '标签', word: '单词或短语', meaning: '释义', collocations: '常见搭配', source_expression: '来源表达', topic: '语法点名称', rule: '语法规则', error: '错误示例', correction: '正确示例', minimal_pairs: '最小对比', reason: '推荐原因', count: '练习数量（1–3）', focus: '练习重点',
  }
  return labels[field] ?? field
}

function parseStructuredValue(value: string, fallback: unknown) {
  try { return JSON.parse(value) as unknown } catch { return fallback }
}

function editableValue(value: unknown) {
  if (Array.isArray(value) && value.every((item) => typeof item === 'string')) return value.join('\n')
  if (value && typeof value === 'object') return JSON.stringify(value, null, 2)
  return displayValue(value)
}
