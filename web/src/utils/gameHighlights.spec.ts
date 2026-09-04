import { describe, expect, it } from 'vitest'
import { findReplayIndex } from './gameHighlights'

const rounds = [
  { round_num: 1, player_id: 'p1', action_type: 'BID', cards: [] },
  { round_num: 2, player_id: 'p1', action_type: 'CHAIN_PAIR', cards: ['C8', 'D8'] },
  { round_num: 11, player_id: 'p1', action_type: 'SINGLE', cards: ['H6'] },
  { round_num: 34, player_id: 'p2', action_type: 'PASS', cards: [] },
  { round_num: 35, player_id: 'p1', action_type: 'SINGLE', cards: ['ST'] },
]

describe('findReplayIndex', () => {
  it('matches by action and cards when decision round lags replay', () => {
    expect(
      findReplayIndex(rounds, {
        round_number: 1,
        player_id: 'p1',
        action_type: 'CHAIN_PAIR',
        cards: ['C8', 'D8'],
      }),
    ).toBe(1)
    expect(
      findReplayIndex(rounds, {
        round_number: 34,
        player_id: 'p1',
        action_type: 'SINGLE',
        cards: ['ST'],
      }),
    ).toBe(4)
  })

  it('falls back to exact round when cards are empty', () => {
    expect(
      findReplayIndex(rounds, {
        round_number: 1,
        player_id: 'p1',
        action_type: 'BID',
        cards: [],
      }),
    ).toBe(0)
  })
})
