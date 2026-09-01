import { describe, expect, it } from 'vitest'
import {
  engineById,
  isValidPlayerSelection,
  maxSelectable,
  playerCountLabel,
  supportsBenchmark,
} from './engineSlots'
import type { EngineInfo } from './engineSlots'

const doudizhu: EngineInfo = {
  id: 'doudizhu',
  game_type: 'doudizhu',
  min_players: 3,
  max_players: 3,
  engine_version: '1',
  phases: ['bidding', 'playing'],
  prompt_keys: { playing: 'doudizhu_playing', bidding: 'doudizhu_bidding' },
  supports_deal_seed: true,
  benchmark_seed_count: 50,
  roles: ['landlord', 'peasant'],
  eval_metric_ids: ['role:landlord'],
  decision_schema_version: 1,
  rules_ref: null,
}
const flexible: EngineInfo = {
  id: 'demo',
  game_type: 'demo',
  min_players: 2,
  max_players: 4,
  engine_version: '1',
  phases: ['playing'],
  prompt_keys: { playing: 'demo_playing' },
  supports_deal_seed: false,
  benchmark_seed_count: 0,
  roles: [],
  eval_metric_ids: [],
  decision_schema_version: 1,
  rules_ref: null,
}

describe('engineSlots', () => {
  it('labels a fixed player count', () => {
    expect(playerCountLabel(doudizhu)).toBe('3')
  })

  it('labels a player range', () => {
    expect(playerCountLabel(flexible)).toBe('2–4')
  })

  it('rejects selection when engine is unknown', () => {
    expect(playerCountLabel(undefined)).toBe('—')
    expect(maxSelectable(undefined)).toBe(0)
    expect(isValidPlayerSelection(3, undefined)).toBe(false)
  })

  it('validates against engine slots', () => {
    expect(isValidPlayerSelection(3, doudizhu)).toBe(true)
    expect(isValidPlayerSelection(2, doudizhu)).toBe(false)
    expect(isValidPlayerSelection(4, flexible)).toBe(true)
    expect(engineById([doudizhu, flexible], 'demo')).toEqual(flexible)
  })

  it('gates benchmark on deal-seed capability', () => {
    expect(supportsBenchmark(doudizhu)).toBe(true)
    expect(supportsBenchmark(flexible)).toBe(false)
    expect(supportsBenchmark(undefined)).toBe(false)
  })
})
