<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'

export type GuideDiagramId = 'loop' | 'detail' | 'pipeline'

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

const caption = computed(() => t(`guide.diagrams.${props.diagram}.caption`))
</script>

<template>
  <figure
    class="overflow-x-auto rounded-ink-md border border-ink-border/80 bg-ink-surface-muted/40 p-ink-4"
  >
    <figcaption
      v-if="caption"
      class="mb-ink-3 text-caption font-medium tracking-wide text-ink-text-secondary uppercase"
    >
      {{ caption }}
    </figcaption>

    <div v-if="diagram === 'loop'" class="flex items-center gap-ink-1 sm:gap-ink-2">
      <template v-for="(node, idx) in nodes" :key="`${node.label}-${idx}`">
        <div
          class="flex min-w-0 flex-1 flex-col items-center gap-ink-2 rounded-ink border px-ink-1 py-ink-3 text-center sm:px-ink-2"
          :class="
            node.tone === 'primary'
              ? 'border-ink-primary/40 bg-ink-primary-muted/50'
              : node.tone === 'muted'
                ? 'border-ink-border/60 bg-ink-surface/60 text-ink-text-secondary'
                : 'border-ink-border bg-ink-surface'
          "
        >
          <Icon :icon="node.icon" class="h-5 w-5 shrink-0 text-ink-primary" />
          <span class="text-caption leading-snug font-medium text-ink-text">{{ node.label }}</span>
        </div>
        <Icon
          v-if="idx < nodes.length - 1"
          icon="lucide:arrow-right"
          class="h-4 w-4 shrink-0 text-ink-text-muted"
        />
      </template>
    </div>

    <div v-else-if="diagram === 'detail'" class="space-y-ink-2">
      <div
        v-for="(node, idx) in nodes"
        :key="`${node.label}-${idx}`"
        class="flex min-w-0 items-center gap-ink-2 rounded-ink border px-ink-3 py-ink-2"
        :class="
          node.tone === 'primary'
            ? 'border-ink-primary/40 bg-ink-primary-muted/40'
            : 'border-ink-border bg-ink-surface'
        "
      >
        <Icon :icon="node.icon" class="h-4 w-4 shrink-0 text-ink-primary" />
        <div class="min-w-0">
          <p class="text-body font-medium text-ink-text">{{ node.label }}</p>
          <p class="text-caption text-ink-text-secondary">
            {{ t(`guide.diagrams.detail.items.${idx}`) }}
          </p>
        </div>
      </div>
    </div>

    <div v-else-if="diagram === 'pipeline'" class="space-y-ink-3">
      <div
        class="rounded-ink border border-ink-primary/30 bg-ink-primary-muted/30 px-ink-3 py-ink-2 text-center text-body font-medium text-ink-text"
      >
        {{ t('guide.diagrams.pipeline.hub') }}
      </div>
      <div class="flex justify-center">
        <Icon icon="lucide:arrow-down" class="h-4 w-4 text-ink-text-muted" />
      </div>
      <div class="grid gap-ink-2 sm:grid-cols-2 lg:grid-cols-4">
        <div
          v-for="(node, idx) in nodes"
          :key="`${node.label}-${idx}`"
          class="rounded-ink border border-ink-border bg-ink-surface px-ink-3 py-ink-3"
        >
          <div class="mb-ink-1 flex items-center gap-ink-2">
            <Icon :icon="node.icon" class="h-4 w-4 text-ink-primary" />
            <span class="text-body font-medium text-ink-text">{{ node.label }}</span>
          </div>
          <p class="text-caption leading-relaxed text-ink-text-secondary">
            {{ t(`guide.diagrams.pipeline.items.${idx}`) }}
          </p>
        </div>
      </div>
    </div>
  </figure>
</template>
