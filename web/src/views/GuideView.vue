<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
import GuideFlowDiagram from '@/components/guide/GuideFlowDiagram.vue'
import GuideModuleSection from '@/components/guide/GuideModuleSection.vue'
import type { GuideDiagramId } from '@/components/guide/GuideFlowDiagram.vue'
import {
  GUIDE_HERO_ID,
  GUIDE_LOOKUP_GROUPS,
  type GuideLookupGroupId,
  parseGuideHash,
} from '@/utils/guideSections'

const SECTION_DIAGRAM: Partial<Record<string, GuideDiagramId>> = {
  experimentDetail: 'detail',
  pipeline: 'pipeline',
}

const { t, tm } = useI18n()
const route = useRoute()

const heroSteps = computed((): string[] => {
  const raw = tm('guide.sections.quickStart.steps')
  return Array.isArray(raw) ? (raw as string[]) : []
})

const activeId = ref<string>(GUIDE_HERO_ID)
const openGroup = ref<GuideLookupGroupId | null>(null)
let observer: IntersectionObserver | null = null

function scrollTo(id: string): void {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function goTo(hashOrId: string): Promise<void> {
  const raw = hashOrId.startsWith('#') ? hashOrId : `#${hashOrId}`
  const target = parseGuideHash(raw)
  if (!target) return
  openGroup.value = target.groupId
  activeId.value = target.sectionId
  await nextTick()
  scrollTo(target.sectionId)
}

function onToggle(groupId: GuideLookupGroupId, event: Event): void {
  const el = event.currentTarget
  if (!(el instanceof HTMLDetailsElement)) return
  if (el.open) {
    openGroup.value = groupId
    const first = GUIDE_LOOKUP_GROUPS.find((g) => g.id === groupId)?.sectionIds[0]
    if (first) activeId.value = first
  } else if (openGroup.value === groupId) {
    openGroup.value = null
  }
}

function setupObserver(): void {
  observer?.disconnect()
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting && entry.target.id) {
          activeId.value = entry.target.id
        }
      }
    },
    { rootMargin: '-20% 0px -60% 0px', threshold: 0 },
  )
  const hero = document.getElementById(GUIDE_HERO_ID)
  if (hero) observer.observe(hero)
  const group = GUIDE_LOOKUP_GROUPS.find((g) => g.id === openGroup.value)
  for (const id of group?.sectionIds ?? []) {
    const el = document.getElementById(id)
    if (el) observer.observe(el)
  }
}

function isGroupActive(groupId: GuideLookupGroupId): boolean {
  const group = GUIDE_LOOKUP_GROUPS.find((g) => g.id === groupId)
  return group?.sectionIds.includes(activeId.value) ?? false
}

onMounted(() => {
  const hash = route.hash.replace('#', '')
  if (hash) void goTo(hash)
  else setupObserver()
})

watch(
  () => route.hash,
  (hash) => {
    const id = hash.replace('#', '')
    if (id) void goTo(id)
  },
)

watch(openGroup, () => {
  void nextTick(setupObserver)
})

onUnmounted(() => {
  observer?.disconnect()
})
</script>

<template>
  <div class="page-container pb-ink-12">
    <div class="grid gap-ink-8 lg:grid-cols-[minmax(0,1fr)_12rem] xl:grid-cols-[minmax(0,1fr)_14rem]">
      <div class="min-w-0">
        <p class="mb-ink-6 max-w-3xl text-pretty text-body leading-relaxed text-ink-text-secondary">
          {{ t('guide.intro') }}
        </p>

        <section :id="GUIDE_HERO_ID" class="ink-section scroll-mt-24">
          <h2 class="ink-section-title">{{ t('guide.sections.quickStart.title') }}</h2>
          <GuideFlowDiagram diagram="loop" class="mt-ink-4" />
          <ol
            class="mt-ink-4 max-w-3xl list-decimal space-y-ink-2 pl-5 text-body leading-relaxed text-ink-text-secondary"
          >
            <li v-for="(step, idx) in heroSteps" :key="idx">{{ step }}</li>
          </ol>
          <div class="mt-ink-4 flex flex-wrap gap-ink-4">
            <RouterLink
              to="/experiment-configs"
              class="text-body font-medium text-ink-primary hover:underline"
            >
              {{ t('guide.hero.goPlayers') }}
            </RouterLink>
            <RouterLink to="/" class="text-body font-medium text-ink-primary hover:underline">
              {{ t('guide.hero.goExperiments') }}
            </RouterLink>
          </div>
        </section>

        <div class="mt-ink-8">
          <h2 class="mb-ink-3 text-title font-semibold tracking-tight text-ink-text">
            {{ t('guide.lookupTitle') }}
          </h2>
          <div class="space-y-ink-3">
            <details
              v-for="group in GUIDE_LOOKUP_GROUPS"
              :key="group.id"
              class="group rounded-ink-md border border-ink-border"
              :open="openGroup === group.id"
              @toggle="onToggle(group.id, $event)"
            >
              <summary
                class="flex cursor-pointer list-none items-center gap-ink-2 px-ink-3 py-ink-3 text-body font-medium text-ink-text marker:content-none [&::-webkit-details-marker]:hidden"
              >
                <Icon
                  icon="lucide:chevron-right"
                  class="h-3.5 w-3.5 shrink-0 text-ink-text-secondary transition-transform group-open:rotate-90"
                />
                <Icon :icon="group.icon" class="h-4 w-4 shrink-0 text-ink-primary" />
                {{ t(`guide.groups.${group.id}`) }}
              </summary>
              <div class="space-y-ink-6 border-t border-ink-border px-ink-4 py-ink-4">
                <GuideModuleSection
                  v-for="sectionId in group.sectionIds"
                  :id="sectionId"
                  :key="sectionId"
                  :compact="true"
                  :diagram="SECTION_DIAGRAM[sectionId]"
                />
              </div>
            </details>
          </div>
        </div>
      </div>

      <nav class="hidden lg:block" :aria-label="t('guide.tocTitle')">
        <div class="sticky top-6 space-y-0.5">
          <p class="mb-ink-2 px-ink-2 text-caption font-semibold tracking-wide text-ink-text-muted uppercase">
            {{ t('guide.tocTitle') }}
          </p>
          <button
            type="button"
            class="flex w-full items-center gap-ink-2 rounded-[6px] px-ink-2 py-1.5 text-left text-body transition-colors"
            :class="
              activeId === GUIDE_HERO_ID
                ? 'bg-ink-primary-muted font-medium text-ink-primary'
                : 'text-ink-text-secondary hover:bg-ink-surface-muted hover:text-ink-text'
            "
            @click="goTo(GUIDE_HERO_ID)"
          >
            <Icon icon="lucide:route" class="h-3.5 w-3.5 shrink-0 opacity-80" />
            <span class="truncate">{{ t('guide.sections.quickStart.title') }}</span>
          </button>
          <p class="mt-ink-3 px-ink-2 pt-ink-2 text-caption font-semibold tracking-wide text-ink-text-muted uppercase">
            {{ t('guide.lookupTitle') }}
          </p>
          <button
            v-for="group in GUIDE_LOOKUP_GROUPS"
            :key="group.id"
            type="button"
            class="flex w-full items-center gap-ink-2 rounded-[6px] px-ink-2 py-1.5 text-left text-body transition-colors"
            :class="
              isGroupActive(group.id)
                ? 'bg-ink-primary-muted font-medium text-ink-primary'
                : 'text-ink-text-secondary hover:bg-ink-surface-muted hover:text-ink-text'
            "
            @click="goTo(group.sectionIds[0] ?? '')"
          >
            <Icon :icon="group.icon" class="h-3.5 w-3.5 shrink-0 opacity-80" />
            <span class="truncate">{{ t(`guide.groups.${group.id}`) }}</span>
          </button>
        </div>
      </nav>
    </div>
  </div>
</template>
