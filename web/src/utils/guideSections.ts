export const GUIDE_HERO_ID = 'quickStart' as const

export type GuideLookupGroupId = 'pages' | 'analyze' | 'metrics' | 'setup'

export type GuideLookupGroup = {
  id: GuideLookupGroupId
  sectionIds: readonly string[]
  icon: string
}

export const GUIDE_LOOKUP_GROUPS: readonly GuideLookupGroup[] = [
  {
    id: 'pages',
    sectionIds: ['experiments', 'experimentDetail', 'playerConfigs', 'games', 'compare'],
    icon: 'lucide:layout-dashboard',
  },
  {
    id: 'analyze',
    sectionIds: ['pipeline'],
    icon: 'lucide:workflow',
  },
  {
    id: 'metrics',
    sectionIds: ['metrics'],
    icon: 'lucide:calculator',
  },
  {
    id: 'setup',
    sectionIds: ['tune', 'prerequisites'],
    icon: 'lucide:plug',
  },
]

const SECTION_TO_GROUP = new Map<string, GuideLookupGroupId>(
  GUIDE_LOOKUP_GROUPS.flatMap((group) =>
    group.sectionIds.map((sectionId) => [sectionId, group.id] as const),
  ),
)

export type GuideHashTarget = {
  sectionId: string
  groupId: GuideLookupGroupId | null
}

export function parseGuideHash(hash: string): GuideHashTarget | null {
  const sectionId = hash.replace(/^#/, '').trim()
  if (!sectionId) return null
  if (sectionId === GUIDE_HERO_ID) {
    return { sectionId: GUIDE_HERO_ID, groupId: null }
  }
  const groupId = SECTION_TO_GROUP.get(sectionId)
  if (!groupId) return null
  return { sectionId, groupId }
}
