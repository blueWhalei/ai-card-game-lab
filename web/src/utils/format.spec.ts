import { describe, expect, it } from 'vitest'
import { formatDateTime } from './format'

describe('formatDateTime', () => {
  it('renders local YYYY-MM-DD HH:mm:ss', () => {
    const date = new Date(2026, 8, 4, 14, 47, 25)
    expect(formatDateTime(date.toISOString())).toBe('2026-09-04 14:47:25')
  })

  it('returns a dash when the value is missing', () => {
    expect(formatDateTime(null)).toBe('-')
    expect(formatDateTime(undefined)).toBe('-')
    expect(formatDateTime('')).toBe('-')
  })
})
