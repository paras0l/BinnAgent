import type { ExpressionSystemAction } from '@/services/expressionLabApi'
import { displayValue } from './blockData'

export function findExpressionAction(
  actions: ExpressionSystemAction[],
  type: string,
  value: string,
  specActionId = '',
) {
  const normalized = value.trim().toLocaleLowerCase()
  const candidates = actions.filter((action) => action.type === type)
  if (specActionId) {
    const byId = candidates.find((action) => (
      action.spec_action_id === specActionId || action.id === specActionId
    ))
    if (byId) return byId
  }
  const matched = candidates.find((action) => {
    const payloadValues = Object.values(action.payload)
      .map(displayValue)
      .join(' ')
      .toLocaleLowerCase()
    return Boolean(
      normalized
      && payloadValues
      && (payloadValues.includes(normalized) || normalized.includes(payloadValues)),
    )
  })
  return matched ?? (!normalized && candidates.length === 1 ? candidates[0] : undefined)
}
