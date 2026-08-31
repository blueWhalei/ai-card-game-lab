import { describe, expect, it } from 'vitest'
import { i18n, isAppLocale, localeRef, tt } from '@/i18n'

describe('i18n', () => {
  it('accepts only zh-CN and en', () => {
    expect(isAppLocale('zh-CN')).toBe(true)
    expect(isAppLocale('en')).toBe(true)
    expect(isAppLocale('zh')).toBe(false)
  })

  it('switches status labels with locale', () => {
    localeRef().value = 'zh-CN'
    expect(tt('experiment.status.pending_collect')).toBe('待开局')
    localeRef().value = 'en'
    expect(tt('experiment.status.pending_collect')).toBe('Ready to start')
    localeRef().value = 'zh-CN'
  })
})
