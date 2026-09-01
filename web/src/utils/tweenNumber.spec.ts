import { describe, expect, it } from 'vitest'
import { easeOutCubic, tweenNumber } from './tweenNumber'

describe('tweenNumber', () => {
  it('stays at the start and lands on the end', () => {
    expect(tweenNumber(10, 20, 0)).toBe(10)
    expect(tweenNumber(10, 20, 1)).toBe(20)
  })

  it('eases out so mid-progress is past halfway', () => {
    expect(easeOutCubic(0.5)).toBeGreaterThan(0.5)
    expect(tweenNumber(0, 100, 0.5)).toBeGreaterThan(50)
  })
})
