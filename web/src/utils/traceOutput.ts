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

export type PlayAction = {
  action_type?: string
  type?: string
  cards?: string[]
}

export function formatPlayAction(action: PlayAction | null | undefined): string {
  if (!action) return '—'
  const type = actionTypeLabel(String(action.action_type || action.type || ''))
  const cards = action.cards?.length ? ` ${action.cards.join(' ')}` : ''
  return `${type}${cards}`.trim()
}

export function samePlayAction(
  a: PlayAction | null | undefined,
  b: PlayAction | null | undefined,
): boolean {
  if (!a || !b) return false
  const typeA = String(a.action_type || a.type || '').toUpperCase()
  const typeB = String(b.action_type || b.type || '').toUpperCase()
  if (typeA !== typeB) return false
  const cardsA = (a.cards ?? []).join(',')
  const cardsB = (b.cards ?? []).join(',')
  return cardsA === cardsB
}

export type WinProbabilityExplain = {
  probability: number
  confidence: string
  reasoning: string
}

export type HandAnalysisExplain = {
  bomb_count: number
  rocket: boolean
  strength_score: number
}

export function parseLegalActions(value: unknown): PlayAction[] {
  if (!Array.isArray(value)) return []
  const out: PlayAction[] = []
  for (const item of value) {
    const rec = asRecord(item)
    if (!rec) continue
    const actionType = readActionType(rec)
    if (!actionType) continue
    out.push({ action_type: actionType, cards: asStringList(rec.cards) })
  }
  return out
}

export function parseWinProbability(value: unknown): WinProbabilityExplain | null {
  const rec = asRecord(value)
  if (!rec) return null
  const probability = rec.probability
  if (typeof probability !== 'number' || Number.isNaN(probability)) return null
  return {
    probability,
    confidence: typeof rec.confidence === 'string' ? rec.confidence : '',
    reasoning: typeof rec.reasoning === 'string' ? rec.reasoning : '',
  }
}

export function parseHandAnalysis(value: unknown): HandAnalysisExplain | null {
  const rec = asRecord(value)
  if (!rec) return null
  return {
    bomb_count: typeof rec.bomb_count === 'number' ? rec.bomb_count : 0,
    rocket: Boolean(rec.rocket),
    strength_score: typeof rec.strength_score === 'number' ? rec.strength_score : 0,
  }
}
