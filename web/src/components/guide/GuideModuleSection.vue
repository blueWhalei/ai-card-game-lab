<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
import GuideFlowDiagram, { type GuideDiagramId } from '@/components/guide/GuideFlowDiagram.vue'

const props = defineProps<{
  id: string
  icon: string
  diagram?: GuideDiagramId
}>()

const { t, tm, te } = useI18n()

function listItems(key: 'steps' | 'bullets'): string[] {
  const raw = tm(`guide.sections.${props.id}.${key}`)
  return Array.isArray(raw) ? (raw as string[]) : []
}
</script>

<template>
  <section :id="id" class="scroll-mt-24 border-b border-ink-border/60 pb-10 last:border-0">
    <div class="mb-4 flex items-center gap-2">
      <span
        class="flex h-8 w-8 items-center justify-center rounded-ink bg-ink-primary-muted text-ink-primary"
      >
        <Icon :icon="icon" class="h-4 w-4" />
      </span>
      <h2 class="text-lg font-semibold text-ink-text">{{ t(`guide.sections.${id}.title`) }}</h2>
    </div>

    <p
      v-if="te(`guide.sections.${id}.body`)"
      class="mb-4 max-w-3xl text-sm leading-relaxed text-ink-text-secondary"
    >
      {{ t(`guide.sections.${id}.body`) }}
    </p>

    <GuideFlowDiagram v-if="diagram" :diagram="diagram" class="mb-5" />

    <ol
      v-if="listItems('steps').length"
      class="mb-4 max-w-3xl list-decimal space-y-2 pl-5 text-sm leading-relaxed text-ink-text-secondary"
    >
      <li v-for="(step, idx) in listItems('steps')" :key="idx">{{ step }}</li>
    </ol>

    <ul
      v-if="listItems('bullets').length"
      class="max-w-3xl list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-ink-text-secondary"
    >
      <li v-for="(item, idx) in listItems('bullets')" :key="idx">{{ item }}</li>
    </ul>
  </section>
</template>
