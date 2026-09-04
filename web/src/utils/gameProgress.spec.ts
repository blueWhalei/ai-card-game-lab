import { describe, expect, it } from 'vitest'
import { formatGameProgress } from './gameProgress'

const names: Record<string, string> = { tiger: '激进虎' }
const playerName = (id: string) => names[id] ?? id

function t(key: string, values?: Record<string, unknown>): string {
  if (key === 'gamesTab.progressQueued') return '尚未发牌'
  if (key === 'gamesTab.progressBidding') return '叫分中'
  if (key === 'gamesTab.progressPlaying') return `出牌 · 第 ${values?.n} 轮`
  if (key === 'gamesTab.progressEndgame') return `残局 · 第 ${values?.n} 轮`
  if (key === 'gamesTab.progressSeat') return ` · 轮到「${values?.name}」`
  return key
}

describe('formatGameProgress', () => {
  it('treats missing snapshots as not dealt', () => {
    expect(formatGameProgress(null, t, playerName)).toBe('尚未发牌')
    expect(formatGameProgress({ phase: 'queued', round: null, player_id: null }, t, playerName)).toBe(
      '尚未发牌',
    )
  })

  it('renders bidding without a seat as a short phrase', () => {
    expect(
      formatGameProgress({ phase: 'bidding', round: 1, player_id: null }, t, playerName),
    ).toBe('叫分中')
  })

  it('renders playing as one sentence with the current seat', () => {
    expect(
      formatGameProgress({ phase: 'playing', round: 12, player_id: 'tiger' }, t, playerName),
    ).toBe('出牌 · 第 12 轮 · 轮到「激进虎」')
  })

  it('renders endgame the same way', () => {
    expect(
      formatGameProgress({ phase: 'endgame', round: 28, player_id: 'tiger' }, t, playerName),
    ).toBe('残局 · 第 28 轮 · 轮到「激进虎」')
  })
})
