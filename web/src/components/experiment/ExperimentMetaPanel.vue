<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import type { Experiment, ExperimentValidation, ExperimentProtocol } from '@/api/experimentApi'
import ExperimentNotebookPanel from '@/components/experiment/ExperimentNotebookPanel.vue'
import UiBadge from '@/components/ui/Badge.vue'
import UiButton from '@/components/ui/Button.vue'

const props = withDefaults(
  defineProps<{
    experiment: Experiment
    validation: ExperimentValidation | null
    protocol: ExperimentProtocol | null
    protocolPlayers: NonNullable<ExperimentProtocol['players']>
    protocolDrift: boolean
    protocolSummaryBits: string[]
    shortExperimentId: (id: string) => string
    /** Dialog body: no collapsible wrapper. */
    dialog?: boolean
  }>(),
  {
    dialog: false,
  },
)

const emit = defineEmits<{
  saved: [experiment: Experiment]
  downloadManifest: []
  clone: []
}>()

const { t } = useI18n()
const router = useRouter()

const metaSummaryBits = computed((): string[] => {
  const bits: string[] = []
  const h = (props.experiment.hypothesis ?? '').trim()
  if (h) bits.push(h.length > 28 ? `${h.slice(0, 28)}…` : h)
  if (props.protocolSummaryBits.length) bits.push(props.protocolSummaryBits[0] ?? '')
  if (props.validation && props.validation.control_experiment_ids.length > 0) {
    bits.push(
      props.validation.validation_ready
        ? t('experiment.validationReady')
        : t('experiment.validationPending'),
    )
  }
  if (bits.length === 0) bits.push(t('experiment.metaPanelEmpty'))
  return bits
})
</script>

<template>
  <details
    v-if="!dialog"
    class="group rounded-ink-md border border-ink-border bg-ink-surface-muted/40 open:bg-ink-surface-muted/60"
  >
    <summary
      class="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-sm marker:content-none [&::-webkit-details-marker]:hidden"
    >
      <Icon
        icon="lucide:chevron-right"
        class="h-3.5 w-3.5 shrink-0 text-ink-text-secondary transition-transform group-open:rotate-90"
      />
      <span class="shrink-0 font-medium text-ink-text">{{ t('experiment.metaPanelTitle') }}</span>
      <span class="min-w-0 truncate text-sm text-ink-text-secondary">
        {{ metaSummaryBits.join(' · ') }}
      </span>
    </summary>

    <div class="space-y-4 border-t border-ink-border px-3 py-3">
      <ExperimentNotebookPanel :experiment="experiment" flat @saved="emit('saved', $event)" />

      <div
        v-if="validation"
        class="flex flex-wrap items-center gap-2 rounded-ink border border-ink-border/80 bg-ink-surface/60 px-2.5 py-2 text-xs text-ink-text-secondary"
      >
        <span class="font-medium text-ink-text">{{ t('experiment.validationTitle') }}</span>
        <UiBadge :variant="validation.validation_ready ? 'success' : 'warning'">
          {{
            validation.validation_ready
              ? t('experiment.validationReady')
              : t('experiment.validationPending')
          }}
        </UiBadge>
        <span>{{ t('experiment.validationPaired', { n: validation.paired_n }) }}</span>
        <button
          v-for="cid in validation.control_experiment_ids"
          :key="cid"
          type="button"
          class="text-ink-primary hover:underline"
          @click="router.push(`/experiments/${cid}`)"
        >
          {{ shortExperimentId(cid) }}
        </button>
      </div>

      <div v-if="protocol" class="space-y-2 text-sm text-ink-text-secondary">
        <p class="text-xs font-medium text-ink-text">{{ t('experiment.protocolTitle') }}</p>
        <ul class="flex flex-wrap gap-1.5">
          <li
            v-for="p in protocolPlayers"
            :key="p.id"
            class="rounded-ink border border-ink-border bg-ink-surface px-2 py-0.5 tabular-nums"
          >
            <span class="font-medium text-ink-text">{{ p.name }}</span>
            <span class="text-ink-text-secondary">
              · {{ p.model_config.model_name }} · T={{
                p.model_config.temperature ?? t('common.dash')
              }}
            </span>
          </li>
        </ul>
        <p v-if="protocolDrift" class="text-xs text-ink-warning">
          {{ t('experiment.protocolDriftShort') }}
        </p>
        <p
          v-if="protocol.pair_deals && protocol.source_experiment_id"
          class="text-xs"
          :title="protocol.source_experiment_id"
        >
          {{
            t('experiment.protocolSource', {
              id: shortExperimentId(protocol.source_experiment_id),
            })
          }}
        </p>
        <div class="flex flex-wrap gap-2">
          <UiButton size="sm" variant="secondary" @click="emit('downloadManifest')">
            {{ t('experiment.downloadManifest') }}
          </UiButton>
          <UiButton size="sm" variant="secondary" @click="emit('clone')">
            {{ t('experiment.cloneExperiment') }}
          </UiButton>
        </div>
      </div>
    </div>
  </details>

  <div v-else class="space-y-5">
    <section class="rounded-ink-md border border-ink-border/80 bg-ink-surface-muted/30 p-4">
      <ExperimentNotebookPanel :experiment="experiment" flat @saved="emit('saved', $event)" />
    </section>

    <section
      v-if="validation"
      class="rounded-ink-md border border-ink-border/80 bg-ink-surface-muted/30 p-4"
    >
      <div class="flex flex-wrap items-center gap-2 text-sm text-ink-text-secondary">
      <span class="font-medium text-ink-text">{{ t('experiment.validationTitle') }}</span>
      <UiBadge :variant="validation.validation_ready ? 'success' : 'warning'">
        {{
          validation.validation_ready
            ? t('experiment.validationReady')
            : t('experiment.validationPending')
        }}
      </UiBadge>
      <span>{{ t('experiment.validationPaired', { n: validation.paired_n }) }}</span>
      <button
        v-for="cid in validation.control_experiment_ids"
        :key="cid"
        type="button"
        class="text-ink-primary hover:underline"
        @click="router.push(`/experiments/${cid}`)"
      >
        {{ shortExperimentId(cid) }}
      </button>
      </div>
    </section>

    <section
      v-if="protocol"
      class="rounded-ink-md border border-ink-border/80 bg-ink-surface-muted/30 p-4"
    >
      <div class="space-y-3 text-sm text-ink-text-secondary">
        <p class="text-sm font-medium text-ink-text">{{ t('experiment.protocolTitle') }}</p>
        <ul class="flex flex-wrap gap-2">
          <li
            v-for="p in protocolPlayers"
            :key="p.id"
            class="rounded-ink border border-ink-border bg-ink-surface px-2.5 py-1 tabular-nums"
          >
          <span class="font-medium text-ink-text">{{ p.name }}</span>
          <span class="text-ink-text-secondary">
            · {{ p.model_config.model_name }} · T={{
              p.model_config.temperature ?? t('common.dash')
            }}
          </span>
        </li>
      </ul>
      <p v-if="protocolDrift" class="text-xs text-ink-warning">
        {{ t('experiment.protocolDriftShort') }}
      </p>
      <p
        v-if="protocol.pair_deals && protocol.source_experiment_id"
        class="text-xs"
        :title="protocol.source_experiment_id"
      >
        {{
          t('experiment.protocolSource', {
            id: shortExperimentId(protocol.source_experiment_id),
          })
        }}
      </p>
      <div class="flex flex-wrap gap-2">
        <UiButton size="sm" variant="secondary" @click="emit('downloadManifest')">
          {{ t('experiment.downloadManifest') }}
        </UiButton>
        <UiButton size="sm" variant="secondary" @click="emit('clone')">
          {{ t('experiment.cloneExperiment') }}
        </UiButton>
      </div>
      </div>
    </section>
  </div>
</template>
