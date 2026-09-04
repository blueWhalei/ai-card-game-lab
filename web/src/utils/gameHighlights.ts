import type { GameHighlight } from '@/api/gameApi'

export interface ReplayRoundRef {
  round_num: number
  player_id: string
  action_type: string
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
