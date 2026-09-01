import { describe, expect, it } from 'vitest'
import { bestIndex, formatDelta, metricUnit } from './compareMatrix'

describe('bestIndex', () => {
  it('picks highest for higher kind', () => {
    expect(bestIndex([0.3, 0.5, 0.4], 'higher')).toBe(1)
  })

  it('picks lowest for lower kind', () => {
    expect(bestIndex([1200, 800, 900], 'lower')).toBe(1)
  })

  it('skips nulls', () => {
    expect(bestIndex([null, 0.2, null], 'higher')).toBe(1)
    expect(bestIndex([null, null], 'higher')).toBeNull()
  })
})

describe('formatDelta', () => {
  it('formats rate as percentage points', () => {
    expect(formatDelta(0.4, 0.5, 'rate')).toBe('−10pp')
    expect(formatDelta(0.55, 0.5, 'rate')).toBe('+5pp')
  })

  it('formats ms with second shortcut', () => {
    expect(formatDelta(2500, 1000, 'ms')).toBe('+1.5s')
    expect(formatDelta(400, 600, 'ms')).toBe('−200ms')
  })

  it('returns null when equal or missing', () => {
    expect(formatDelta(1, 1, 'count')).toBeNull()
    expect(formatDelta(null, 1, 'count')).toBeNull()
  })

  it('formats count with unicode minus', () => {
    expect(formatDelta(3, 5, 'count')).toBe('−2')
  })
})

describe('metricUnit', () => {
  it('maps known ids', () => {
    expect(metricUnit('p50')).toBe('ms')
    expect(metricUnit('finished')).toBe('count')
    expect(metricUnit('landlord')).toBe('rate')
  })
})
