<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'

export type GuideDiagramId = 'loop' | 'sidebar' | 'detail' | 'pipeline'

const props = defineProps<{
  diagram: GuideDiagramId
}>()

const { t, tm } = useI18n()

type FlowNode = {
  label: string
  icon: string
  tone?: 'default' | 'primary' | 'muted'
}

const nodes = computed((): FlowNode[] => {
  const raw = tm(`guide.diagrams.${props.diagram}.nodes`)
  if (!Array.isArray(raw)) return []
  return raw as FlowNode[]
})

const caption = computed(() => {
  const key = `guide.diagrams.${props.diagram}.caption`
  return t(key)
})
</script>

<template>
  <figure
    class="overflow-x-auto rounded-ink-md border border-ink-border/80 bg-ink-surface-muted/40 p-4"
  >
    <figcaption
      v-if="caption"
      class="mb-3 text-xs font-medium tracking-wide text-ink-text-secondary uppercase"
    >
      {{ caption }}
    </figcaption>

    <!-- Main loop: horizontal pipeline -->
    <div
      v-if="diagram === 'loop'"
      class="flex min-w-max items-center gap-1.5 pb-1"
    >
      <template v-for="(node, idx) in nodes" :key="`${node.label}-${idx}`">
        <div
          class="flex w-[7.25rem] shrink-0 flex-col items-center gap-1.5 rounded-ink border px-2 py-2.5 text-center"
          :class="
            node.tone === 'primary'
              ? 'border-ink-primary/40 bg-ink-primary-muted/50'
              : node.tone === 'muted'
                ? 'border-ink-border/60 bg-ink-surface/60 text-ink-text-secondary'
                : 'border-ink-border bg-ink-surface'
          "
        >
          <Icon :icon="node.icon" class="h-5 w-5 shrink-0 text-ink-primary" />
          <span class="text-xs leading-snug font-medium text-ink-text">{{ node.label }}</span>
        </div>
        <Icon
          v-if="idx < nodes.length - 1"
          icon="lucide:arrow-right"
          class="h-4 w-4 shrink-0 text-ink-text-muted"
        />
      </template>
    </div>

    <!-- Sidebar: three columns -->
    <div
      v-else-if="diagram === 'sidebar'"
      class="grid gap-3 sm:grid-cols-3"
    >
      <div
        v-for="(node, idx) in nodes"
        :key="`${node.label}-${idx}`"
        class="rounded-ink border border-ink-border bg-ink-surface px-3 py-3"
      >
        <div class="mb-2 flex items-center gap-2">
          <Icon :icon="node.icon" class="h-4 w-4 text-ink-primary" />
          <span class="text-sm font-semibold text-ink-text">{{ node.label }}</span>
        </div>
        <p class="text-xs leading-relaxed text-ink-text-secondary">
          {{ t(`guide.diagrams.sidebar.items.${idx}`) }}
        </p>
      </div>
    </div>

    <!-- Experiment detail: stacked zones -->
    <div v-else-if="diagram === 'detail'" class="space-y-2">
      <div
        v-for="(node, idx) in nodes"
        :key="`${node.label}-${idx}`"
        class="flex min-w-0 items-center gap-2 rounded-ink border px-3 py-2.5"
        :class="
          node.tone === 'primary'
            ? 'border-ink-primary/40 bg-ink-primary-muted/40'
            : 'border-ink-border bg-ink-surface'
        "
      >
        <Icon :icon="node.icon" class="h-4 w-4 shrink-0 text-ink-primary" />
        <div class="min-w-0">
          <p class="text-sm font-medium text-ink-text">{{ node.label }}</p>
          <p class="text-xs text-ink-text-secondary">
            {{ t(`guide.diagrams.detail.items.${idx}`) }}
          </p>
        </div>
      </div>
    </div>

    <!-- Pipeline branch -->
    <div v-else-if="diagram === 'pipeline'" class="space-y-3">
      <div
        class="rounded-ink border border-ink-primary/30 bg-ink-primary-muted/30 px-3 py-2 text-center text-sm font-medium text-ink-text"
      >
        {{ t('guide.diagrams.pipeline.hub') }}
      </div>
      <div class="flex justify-center">
        <Icon icon="lucide:arrow-down" class="h-4 w-4 text-ink-text-muted" />
      </div>
      <div class="grid gap-2 sm:grid-cols-3">
        <div
          v-for="(node, idx) in nodes"
          :key="`${node.label}-${idx}`"
          class="rounded-ink border border-ink-border bg-ink-surface px-3 py-2.5"
        >
          <div class="mb-1 flex items-center gap-2">
            <Icon :icon="node.icon" class="h-4 w-4 text-ink-primary" />
            <span class="text-sm font-medium text-ink-text">{{ node.label }}</span>
          </div>
          <p class="text-xs leading-relaxed text-ink-text-secondary">
            {{ t(`guide.diagrams.pipeline.items.${idx}`) }}
          </p>
        </div>
      </div>
    </div>
  </figure>
</template>
