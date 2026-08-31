import { describe, expect, it } from 'vitest'
import { actionTypeLabel, parseTraceDecision } from './traceOutput'

describe('parseTraceDecision', () => {
  it('reads live-game flat output_data', () => {
    const parsed = parseTraceDecision({
      action_type: 'PAIR',
      cards: ['3s', '3h'],
      thinking: '对子压过上家',
    })
    expect(parsed.actionType).toBe('PAIR')
    expect(parsed.cards).toEqual(['3s', '3h'])
    expect(parsed.thinking).toBe('对子压过上家')
  })

  it('reads nested demo-seed action', () => {
    const parsed = parseTraceDecision({
      action: { action_type: 'PASS', cards: [] },
      thinking: '过',
    })
    expect(parsed.actionType).toBe('PASS')
    expect(parsed.cards).toEqual([])
  })

  it('falls back to UNKNOWN when empty', () => {
    expect(parseTraceDecision({}).actionType).toBe('UNKNOWN')
    expect(parseTraceDecision(null).actionType).toBe('UNKNOWN')
  })

  it('labels doudizhu action types in Chinese', () => {
    expect(actionTypeLabel('PASS')).toBe('不出')
    expect(actionTypeLabel('bid_pass')).toBe('不叫')
    expect(actionTypeLabel('CUSTOM')).toBe('CUSTOM')
  })
})
