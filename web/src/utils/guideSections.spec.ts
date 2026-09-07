import { describe, expect, it } from 'vitest'
import { GUIDE_HERO_ID, GUIDE_LOOKUP_GROUPS, parseGuideHash } from './guideSections'

describe('parseGuideHash', () => {
  it('opens the metrics glossary for MetricHint deep links', () => {
    expect(parseGuideHash('#metrics')).toEqual({
      sectionId: 'metrics',
      groupId: 'metrics',
    })
  })

  it('maps a page section to its lookup group', () => {
    expect(parseGuideHash('#experimentDetail')).toEqual({
      sectionId: 'experimentDetail',
      groupId: 'pages',
    })
    expect(parseGuideHash('pipeline')).toEqual({
      sectionId: 'pipeline',
      groupId: 'analyze',
    })
    expect(parseGuideHash('#prerequisites')).toEqual({
      sectionId: 'prerequisites',
      groupId: 'setup',
    })
  })

  it('treats hero and legacy overview hashes as the start section', () => {
    expect(parseGuideHash('#quickStart')).toEqual({
      sectionId: GUIDE_HERO_ID,
      groupId: null,
    })
    expect(parseGuideHash('#overview')).toEqual({
      sectionId: GUIDE_HERO_ID,
      groupId: null,
    })
  })

  it('returns null for empty or unknown hashes', () => {
    expect(parseGuideHash('')).toBeNull()
    expect(parseGuideHash('#')).toBeNull()
    expect(parseGuideHash('#nope')).toBeNull()
  })
})

describe('GUIDE_LOOKUP_GROUPS', () => {
  it('keeps metrics in its own group so the glossary is not mixed into pages', () => {
    const metrics = GUIDE_LOOKUP_GROUPS.find((g) => g.id === 'metrics')
    expect(metrics?.sectionIds).toEqual(['metrics'])
  })
})
