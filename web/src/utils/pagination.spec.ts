import { describe, expect, it } from 'vitest'
import { DEFAULT_PAGE_SIZE, parsePageSize } from './pagination'

describe('parsePageSize', () => {
  it('defaults to 20', () => {
    expect(DEFAULT_PAGE_SIZE).toBe(20)
    expect(parsePageSize(undefined)).toBe(20)
    expect(parsePageSize('')).toBe(20)
    expect(parsePageSize('7')).toBe(20)
  })

  it('accepts 10, 20, and 50', () => {
    expect(parsePageSize('10')).toBe(10)
    expect(parsePageSize(20)).toBe(20)
    expect(parsePageSize('50')).toBe(50)
  })
})
