import { describe, expect, it } from 'vitest'
import {
  controlSlotLabels,
  formatWinRate,
  formatWinRateCi,
  initialControlPlayerIds,
  remainingCollectCount,
  sanitizeNamePart,
  uniqueFilledIds,
} from './experimentWorkbench'

describe('experimentWorkbench', () => {
  it('sanitizes names for dataset titles', () => {
    expect(sanitizeNamePart('  a/b:c  ')).toBe('a-b-c')
    expect(sanitizeNamePart('   ')).toBe('experiment')
  })

  it('clamps remaining collect count', () => {
    expect(remainingCollectCount(10, 3)).toBe(7)
    expect(remainingCollectCount(10, 10)).toBe(1)
    expect(remainingCollectCount(80, 0)).toBe(50)
  })

  it('requires unique filled player ids', () => {
    expect(uniqueFilledIds(['a', 'b', 'c'])).toBe(true)
    expect(uniqueFilledIds(['a', 'a', 'c'])).toBe(false)
    expect(uniqueFilledIds(['a', '', 'c'])).toBe(false)
  })

  it('formats win rates and Wilson intervals', () => {
    expect(formatWinRate(0.44)).toBe('44%')
    expect(formatWinRateCi([0.19, 0.73])).toBe('19–73%')
  })

  it('labels control seats from engine slot count', () => {
    expect(controlSlotLabels(2)).toEqual(['新选手', '基线'])
    expect(controlSlotLabels(3)).toEqual(['新选手', '基线 A', '基线 B'])
    expect(controlSlotLabels(4)).toEqual(['新选手', '基线 A', '基线 B', '基线 C'])
    expect(controlSlotLabels(1)).toEqual([])
  })

  it('prefills challenger then unique baselines', () => {
    expect(initialControlPlayerIds(3, 'lora_new', ['a', 'b', 'c'])).toEqual([
      'lora_new',
      'a',
      'b',
    ])
    expect(initialControlPlayerIds(3, 'a', ['a', 'b', 'c'])).toEqual(['a', 'b', 'c'])
    expect(initialControlPlayerIds(2, 'lora_new', ['a', 'b'])).toEqual(['lora_new', 'a'])
  })
})
