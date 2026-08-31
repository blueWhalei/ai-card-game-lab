import { describe, expect, it } from 'vitest'
import { DEFAULT_PAGE_SIZE, parsePageSize } from './pagination'

describe('parsePageSize', () => {
  it('defaults to 10', () => {
    expect(DEFAULT_PAGE_SIZE).toBe(10)
    expect(parsePageSize(undefined)).toBe(10)
    expect(parsePageSize('')).toBe(10)
    expect(parsePageSize('7')).toBe(10)
  })

  it('accepts 10, 20, and 50', () => {
    expect(parsePageSize('10')).toBe(10)
    expect(parsePageSize(20)).toBe(20)
    expect(parsePageSize('50')).toBe(50)
  })
})
