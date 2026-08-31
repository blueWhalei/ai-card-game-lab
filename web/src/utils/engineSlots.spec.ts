import { describe, expect, it } from 'vitest'
import {
  engineById,
  isValidPlayerSelection,
  maxSelectable,
  playerCountLabel,
} from './engineSlots'

const doudizhu = { id: 'doudizhu', min_players: 3, max_players: 3 }
const flexible = { id: 'demo', min_players: 2, max_players: 4 }

describe('engineSlots', () => {
  it('labels a fixed player count', () => {
    expect(playerCountLabel(doudizhu)).toBe('3')
  })

  it('labels a player range', () => {
    expect(playerCountLabel(flexible)).toBe('2–4')
  })

  it('defaults to three when engine is unknown', () => {
    expect(playerCountLabel(undefined)).toBe('3')
    expect(maxSelectable(undefined)).toBe(3)
    expect(isValidPlayerSelection(3, undefined)).toBe(true)
    expect(isValidPlayerSelection(2, undefined)).toBe(false)
  })

  it('validates against engine slots', () => {
    expect(isValidPlayerSelection(3, doudizhu)).toBe(true)
    expect(isValidPlayerSelection(2, doudizhu)).toBe(false)
    expect(isValidPlayerSelection(4, flexible)).toBe(true)
    expect(engineById([doudizhu, flexible], 'demo')).toEqual(flexible)
  })
})
