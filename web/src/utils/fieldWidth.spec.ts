import { describe, expect, it } from 'vitest'
import {
  computeFieldWidth,
  estimateEmWidth,
  FIELD_MAX_PX,
  FIELD_MIN_PX,
  hasExplicitWidth,
  INPUT_CHROME_PX,
  SELECT_CHROME_PX,
  widestText,
} from './fieldWidth'

describe('hasExplicitWidth', () => {
  it('treats stretch and fixed Tailwind widths as explicit', () => {
    expect(hasExplicitWidth('w-full')).toBe(true)
    expect(hasExplicitWidth('flex-1')).toBe(true)
    expect(hasExplicitWidth('w-40')).toBe(true)
    expect(hasExplicitWidth('h-8 w-[4.5rem] text-sm')).toBe(true)
  })

  it('ignores non-width classes', () => {
    expect(hasExplicitWidth(undefined)).toBe(false)
    expect(hasExplicitWidth('h-8 text-sm')).toBe(false)
    expect(hasExplicitWidth('max-w-[24rem]')).toBe(false)
  })
})

describe('computeFieldWidth', () => {
  it('adds chrome and clamps to min/max', () => {
    expect(computeFieldWidth(10, INPUT_CHROME_PX)).toBe(FIELD_MIN_PX)
    expect(computeFieldWidth(100, INPUT_CHROME_PX)).toBe(128)
    expect(computeFieldWidth(800, SELECT_CHROME_PX)).toBe(FIELD_MAX_PX)
  })
})

describe('widestText', () => {
  it('picks CJK over a shorter ASCII string of similar char count', () => {
    expect(estimateEmWidth('全部选手')).toBeGreaterThan(estimateEmWidth('All'))
    expect(widestText(['All players', '全部选手', ''])).toBe('All players')
    expect(widestText(['可训练', 'Trainable (yes)'])).toBe('Trainable (yes)')
  })
})
