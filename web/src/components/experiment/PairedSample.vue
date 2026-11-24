<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { DealPurpose, PairedOutcomeCounts } from '@/api/experimentApi'

defineProps<{
  purpose: DealPurpose
  effective: number
  excluded: number
  counts: PairedOutcomeCounts
  a: string
  b: string
}>()
const { t } = useI18n()
const cells = ['both_won', 'a_only_won', 'b_only_won', 'both_lost'] as const
</script>

<template>
  <section
    class="space-y-ink-2 border-y border-ink-border py-ink-3"
    :aria-label="t('focus.pairCounts')"
  >
    <p class="text-body">
      {{ t(`focus.purpose.${purpose}`) }} ·
      {{ t('focus.sampleSize', { planned: effective + excluded, effective, excluded }) }}
    </p>
    <template v-if="effective">
      <p class="break-words text-caption text-ink-text-muted">{{ t('focus.arms', { a, b }) }}</p>
      <dl class="grid grid-cols-2 gap-ink-2 sm:grid-cols-4">
        <div v-for="cell in cells" :key="cell">
          <dt class="text-caption text-ink-text-muted">{{ t(`focus.outcomes.${cell}`) }}</dt>
          <dd class="text-title tabular-nums">{{ counts[cell] }}</dd>
        </div>
      </dl>
      <p
        v-if="counts.a_only_won === 0 && counts.b_only_won === 0"
        class="text-caption text-ink-text-secondary"
      >
        {{ t('focus.allAgree') }}
      </p>
    </template>
  </section>
</template>
