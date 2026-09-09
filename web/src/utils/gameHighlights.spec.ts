import { describe, expect, it } from 'vitest'
import {
  findCommentaryAtIndex,
  findReplayIndex,
  formatEvExplain,
} from './gameHighlights'

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

describe('findCommentaryAtIndex', () => {
  it('returns the row mapped to the replay frame', () => {
    const items = [
      {
        round_number: 2,
        player_id: 'p1',
        action_type: 'CHAIN_PAIR',
        cards: ['C8', 'D8'],
      },
    ]
    expect(findCommentaryAtIndex(rounds, items, 1)).toEqual(items[0])
    expect(findCommentaryAtIndex(rounds, items, 0)).toBeNull()
  })
})

describe('formatEvExplain', () => {
  const t = (key: string, values?: Record<string, unknown>) => {
    if (key === 'game.evExplainAi') return `AI ${values?.ai}`
    if (key === 'game.evExplainBaseline') return `Baseline ${values?.base}`
    if (key === 'game.evExplainBest') return `EV-best ${values?.best}`
    if (key === 'game.evExplainLoss') return `loss ${values?.loss}`
    return key
  }

  it('returns null without baseline or best', () => {
    expect(formatEvExplain({ action_id: 'A' }, t, 'fallback')).toBeNull()
  })

  it('joins AI baseline best and loss', () => {
    expect(
      formatEvExplain(
        {
          action_id: 'A1',
          baseline_label: 'B',
          best_action_id: 'Z',
          ev_loss: 0.25,
        },
        t,
        'fallback',
      ),
    ).toBe('AI A1 · Baseline B · EV-best Z · loss 0.25')
  })
})
