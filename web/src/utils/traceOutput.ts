import { tt } from '@/i18n'

export type TraceAction = {
  actionType: string
  cards: string[]
  target: string | null
  thinking: string
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return null
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string')
}

function readActionType(source: Record<string, unknown> | null): string {
  if (!source) return ''
  const raw = source.action_type ?? source.type
  return typeof raw === 'string' ? raw.trim() : ''
}

/** Live games store a flat payload; demo seed nests `{ action: { action_type } }`. */
export function parseTraceDecision(output: unknown): TraceAction {
  const root = asRecord(output) ?? {}
  const nested = asRecord(root.action)
  const actionType = readActionType(nested) || readActionType(root) || 'UNKNOWN'
  const cards = asStringList(nested?.cards ?? root.cards)
  const targetRaw = nested?.target ?? root.target
  const thinking = typeof root.thinking === 'string' ? root.thinking : ''
  return {
    actionType,
    cards,
    target: typeof targetRaw === 'string' && targetRaw ? targetRaw : null,
    thinking,
  }
}

export function actionTypeLabel(actionType: string): string {
  const key = actionType.trim().toUpperCase()
  const i18nKey = `action.${key}`
  const translated = tt(i18nKey)
  if (translated !== i18nKey) return translated
  return actionType.trim() || tt('action.UNKNOWN')
}
