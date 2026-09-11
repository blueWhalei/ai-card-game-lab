import { afterEach, describe, expect, it } from 'vitest'
import { localeRef } from '@/i18n'
import { experimentOutcomeText } from './experimentOutcomes'

afterEach(() => {
  localeRef().value = 'zh-CN'
})

describe('experiment outcome summary', () => {
  it('does not present cancelled games as completed games', () => {
    localeRef().value = 'en'
    expect(
      experimentOutcomeText({
        status_counts: { finished: 0, cancelled: 10 },
        games_with_winner: 0,
      }),
    ).toBe('10 cancelled · 0 decided games')
  })
  it('keeps no-bid games separate from completed games and wins', () => {
    localeRef().value = 'en'
    expect(
      experimentOutcomeText({
        status_counts: { finished: 3, no_bid: 2, failed: 1 },
        games_with_winner: 3,
      }),
    ).toBe('3 completed · 2 no-bid games · 1 failed · 3 decided games')
  })
  it('does not invent status counts for older summaries', () => {
    localeRef().value = 'zh-CN'
    expect(experimentOutcomeText({ games_with_winner: 0 })).toBe('分出胜负 0 局')
  })
})
