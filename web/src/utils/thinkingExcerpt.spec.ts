import { describe, expect, it } from 'vitest'
import { thinkingExcerpt } from './thinkingExcerpt'

describe('thinkingExcerpt', () => {
  it('returns an empty string for blank input', () => {
    expect(thinkingExcerpt('   ')).toBe('')
  })

  it('keeps a short thought intact', () => {
    expect(thinkingExcerpt('先看看有没有炸弹')).toBe('先看看有没有炸弹')
  })

  it('collapses whitespace and trims to the seat length', () => {
    const text = '先看看\n有没有炸弹。  然后决定是否跟。'.repeat(4)
    const excerpt = thinkingExcerpt(text, 20)
    expect(excerpt.endsWith('…')).toBe(true)
    expect(excerpt.length).toBeLessThanOrEqual(21)
    expect(excerpt.includes('\n')).toBe(false)
  })
})
