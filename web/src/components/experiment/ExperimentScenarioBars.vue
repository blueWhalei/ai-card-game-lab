<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ExperimentScenarioDiff } from '@/api/experimentApi'
import {
  EXPERIMENT_SCENARIO_IDS,
  formatDeltaPp,
  type ExperimentScenarioId,
} from '@/utils/experimentWorkbench'

/** Above this absolute gap a scenario is worth calling out in words. */
const NOTABLE_DIFF = 0.05
/** A bar spanning the full half-track represents this much difference. */
const FULL_SCALE_DIFF = 0.2

const props = defineProps<{
  diffs?: Record<string, ExperimentScenarioDiff>
}>()

const { t } = useI18n()

function labelFor(id: ExperimentScenarioId): string {
  const map: Record<ExperimentScenarioId, string> = {
    bidding: t('experiment.scenarioBidding'),
    playing: t('experiment.scenarioPlaying'),
    endgame: t('experiment.scenarioEndgame'),
    bomb: t('experiment.scenarioBomb'),
  }
  return map[id]
}

const rows = computed(() =>
  EXPERIMENT_SCENARIO_IDS.map((id) => {
    const diff = props.diffs?.[id]
    const value = diff?.train_usable_rate_diff ?? null
    const magnitude = value == null ? 0 : Math.min(1, Math.abs(value) / FULL_SCALE_DIFF)
    return {
      id,
      label: labelFor(id),
      n: diff?.this_n ?? 0,
      value,
      display: formatDeltaPp(value),
      widthPercent: Math.round(magnitude * 50),
      positive: (value ?? 0) > 0,
    }
  }).filter((row) => row.n > 0 || row.value != null),
)

const notable = computed(() => {
  const ranked = rows.value
    .filter((row) => row.value != null && Math.abs(row.value) >= NOTABLE_DIFF)
    .sort((a, b) => Math.abs(b.value ?? 0) - Math.abs(a.value ?? 0))
  return ranked[0] ?? null
})
</script>

<template>
  <div v-if="rows.length > 0" class="ink-section">
    <p class="text-caption font-medium text-ink-text-secondary">
      {{ t('stage.scenarioTitle') }}
    </p>

    <ul class="mt-ink-2 space-y-ink-1">
      <li v-for="row in rows" :key="row.id" class="flex items-center gap-ink-3">
        <span class="w-12 shrink-0 text-caption text-ink-text-muted">{{ row.label }}</span>
        <span class="relative h-3 min-w-0 flex-1 max-w-xs">
          <span class="absolute inset-y-0 left-1/2 w-px bg-ink-border" />
          <span
            v-if="row.value != null"
            class="absolute inset-y-0.75 bg-ink-text-muted/50"
            :style="
              row.positive
                ? { left: '50%', width: `${row.widthPercent}%` }
                : { right: '50%', width: `${row.widthPercent}%` }
            "
          />
        </span>
        <span class="w-16 shrink-0 text-caption tabular-nums text-ink-text-secondary">
          {{ row.display }}
        </span>
      </li>
    </ul>

    <p v-if="notable" class="mt-ink-2 text-caption text-ink-text-secondary">
      {{ t('stage.scenarioNotable', { name: notable.label, delta: notable.display }) }}
    </p>
  </div>
</template>
