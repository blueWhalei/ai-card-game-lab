import type { GameHighlight } from '@/api/gameApi'

export interface ReplayRoundRef {
  round_num: number
  player_id: string
  action_type: string
  cards?: string[]
}

export type EvExplainFields = Pick<
  GameHighlight,
  'action_id' | 'baseline_label' | 'baseline_action_id' | 'best_action_id' | 'ev_loss'
> & {
  action_type?: string
  cards?: string[]
}

function cardsKey(cards: string[] | undefined): string {
  return (cards ?? []).join(',')
}

/** Map a highlight to a replay round index.

Decision ``round_number`` can lag ``rounds.round_num`` by one (bidding vs
playing). Prefer player + action + cards, then exact round, then round+1.
*/
export function findReplayIndex(
  rounds: ReplayRoundRef[],
  item: Pick<GameHighlight, 'round_number' | 'player_id' | 'action_type' | 'cards'>,
): number {
  const want = cardsKey(item.cards)
  const wantType = String(item.action_type || '').toUpperCase()
  const matches: { index: number; dist: number }[] = []
  rounds.forEach((round, index) => {
    if (round.player_id !== item.player_id) return
    if (String(round.action_type || '').toUpperCase() !== wantType) return
    if (cardsKey(round.cards) !== want) return
    matches.push({ index, dist: Math.abs(round.round_num - item.round_number) })
  })
  if (matches.length > 0) {
    matches.sort((a, b) => a.dist - b.dist)
    return matches[0]?.index ?? -1
  }
  const exact = rounds.findIndex(
    (round) => round.round_num === item.round_number && round.player_id === item.player_id,
  )
  if (exact >= 0) return exact
  return rounds.findIndex(
    (round) =>
      round.round_num === item.round_number + 1 && round.player_id === item.player_id,
  )
}

/** Find commentary row for the current replay frame (inverse of findReplayIndex). */
export function findCommentaryAtIndex(
  rounds: ReplayRoundRef[],
  items: Array<
    Pick<GameHighlight, 'round_number' | 'player_id' | 'action_type' | 'cards'>
  >,
  replayIndex: number,
): (typeof items)[number] | null {
  if (replayIndex < 0 || replayIndex >= rounds.length) return null
  for (const item of items) {
    if (findReplayIndex(rounds, item) === replayIndex) return item
  }
  return null
}

export function formatEvExplain(
  item: EvExplainFields,
  t: (key: string, values?: Record<string, unknown>) => string,
  aiFallback: string,
): string | null {
  const baseline = item.baseline_label || item.baseline_action_id || null
  if (!item.best_action_id && !baseline) return null
  const ai = item.action_id || aiFallback
  const parts = [t('game.evExplainAi', { ai })]
  if (baseline) {
    parts.push(t('game.evExplainBaseline', { base: baseline }))
  }
  if (item.best_action_id) {
    parts.push(t('game.evExplainBest', { best: item.best_action_id }))
    const loss =
      item.ev_loss == null || Number.isNaN(Number(item.ev_loss))
        ? '—'
        : Number(item.ev_loss).toFixed(2)
    parts.push(t('game.evExplainLoss', { loss }))
  }
  return parts.join(' · ')
}
