<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import GuideFlowDiagram, { type GuideDiagramId } from '@/components/guide/GuideFlowDiagram.vue'

const props = defineProps<{
  id: string
  diagram?: GuideDiagramId
  compact?: boolean
}>()

const { t, tm, te } = useI18n()

function listItems(key: 'steps' | 'bullets'): string[] {
  const raw = tm(`guide.sections.${props.id}.${key}`)
  return Array.isArray(raw) ? (raw as string[]) : []
}
</script>

<template>
  <section :id="id" class="scroll-mt-24" :class="compact ? '' : 'border-b border-ink-border/60 pb-ink-8 last:border-0'">
    <h3
      :class="
        compact
          ? 'text-lead font-semibold text-ink-text'
          : 'text-title font-semibold tracking-tight text-ink-text'
      "
    >
      {{ t(`guide.sections.${id}.title`) }}
    </h3>

    <p
      v-if="te(`guide.sections.${id}.body`)"
      class="mt-ink-2 max-w-3xl text-body leading-relaxed text-ink-text-secondary"
    >
      {{ t(`guide.sections.${id}.body`) }}
    </p>

    <GuideFlowDiagram v-if="diagram" :diagram="diagram" class="mt-ink-4" />

    <ol
      v-if="listItems('steps').length"
      class="mt-ink-3 max-w-3xl list-decimal space-y-ink-2 pl-5 text-body leading-relaxed text-ink-text-secondary"
    >
      <li v-for="(step, idx) in listItems('steps')" :key="idx">{{ step }}</li>
    </ol>

    <ul
      v-if="listItems('bullets').length"
      class="mt-ink-3 max-w-3xl list-disc space-y-1.5 pl-5 text-body leading-relaxed text-ink-text-secondary"
    >
      <li v-for="(item, idx) in listItems('bullets')" :key="idx">{{ item }}</li>
    </ul>
  </section>
</template>
