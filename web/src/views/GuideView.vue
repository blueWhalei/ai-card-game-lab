<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
import GuideModuleSection from '@/components/guide/GuideModuleSection.vue'
import type { GuideDiagramId } from '@/components/guide/GuideFlowDiagram.vue'

type ModuleDef = {
  id: string
  icon: string
  diagram?: GuideDiagramId
}

const { t } = useI18n()

const modules: ModuleDef[] = [
  { id: 'overview', icon: 'lucide:info', diagram: 'sidebar' },
  { id: 'quickStart', icon: 'lucide:route', diagram: 'loop' },
  { id: 'experiments', icon: 'lucide:beaker' },
  { id: 'experimentDetail', icon: 'lucide:layout-dashboard', diagram: 'detail' },
  { id: 'playerConfigs', icon: 'lucide:flask-conical' },
  { id: 'games', icon: 'lucide:swords' },
  { id: 'pipeline', icon: 'lucide:workflow', diagram: 'pipeline' },
  { id: 'compare', icon: 'lucide:git-compare' },
  { id: 'tune', icon: 'lucide:sliders-horizontal' },
  { id: 'prerequisites', icon: 'lucide:plug' },
]

const activeId = ref(modules[0]?.id ?? 'overview')
let observer: IntersectionObserver | null = null

function scrollTo(id: string): void {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(() => {
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
  for (const mod of modules) {
    const el = document.getElementById(mod.id)
    if (el) observer.observe(el)
  }
})

onUnmounted(() => {
  observer?.disconnect()
})
</script>

<template>
  <div class="page-container pb-16">
    <div class="grid gap-8 lg:grid-cols-[minmax(0,1fr)_12rem] xl:grid-cols-[minmax(0,1fr)_14rem]">
      <div class="min-w-0 space-y-2">
        <p class="mb-6 text-pretty text-sm leading-relaxed text-ink-text-secondary">
          {{ t('guide.intro') }}
        </p>

        <details class="mb-4 rounded-ink border border-ink-border bg-ink-surface-muted/40 lg:hidden">
          <summary
            class="cursor-pointer list-none px-3 py-2 text-sm font-medium marker:content-none [&::-webkit-details-marker]:hidden"
          >
            {{ t('guide.tocTitle') }}
          </summary>
          <div class="space-y-0.5 border-t border-ink-border px-2 py-2">
            <button
              v-for="mod in modules"
              :key="`m-${mod.id}`"
              type="button"
              class="flex w-full items-center gap-2 rounded-[6px] px-2 py-1.5 text-left text-sm text-ink-text-secondary hover:bg-ink-surface-muted"
              @click="scrollTo(mod.id)"
            >
              <Icon :icon="mod.icon" class="h-3.5 w-3.5" />
              {{ t(`guide.sections.${mod.id}.title`) }}
            </button>
          </div>
        </details>

        <GuideModuleSection
          v-for="mod in modules"
          :key="mod.id"
          :id="mod.id"
          :icon="mod.icon"
          :diagram="mod.diagram"
        />
      </div>

      <nav
        class="hidden lg:block"
        aria-label="Guide modules"
      >
        <div class="sticky top-6 space-y-0.5">
          <p class="mb-2 px-2 text-xs font-semibold tracking-wide text-ink-text-muted uppercase">
            {{ t('guide.tocTitle') }}
          </p>
          <button
            v-for="mod in modules"
            :key="mod.id"
            type="button"
            class="flex w-full items-center gap-2 rounded-[6px] px-2 py-1.5 text-left text-sm transition-colors"
            :class="
              activeId === mod.id
                ? 'bg-ink-primary-muted font-medium text-ink-primary'
                : 'text-ink-text-secondary hover:bg-ink-surface-muted hover:text-ink-text'
            "
            @click="scrollTo(mod.id)"
          >
            <Icon :icon="mod.icon" class="h-3.5 w-3.5 shrink-0 opacity-80" />
            <span class="truncate">{{ t(`guide.sections.${mod.id}.title`) }}</span>
          </button>
        </div>
      </nav>
    </div>
  </div>
</template>
