<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { ExperimentValidation, ExperimentProtocol } from '@/api/experimentApi'
import UiButton from '@/components/ui/Button.vue'

const props = defineProps<{
  validation: ExperimentValidation | null
  protocol: ExperimentProtocol | null
  protocolPlayers: NonNullable<ExperimentProtocol['players']>
  protocolDrift: boolean
  shortExperimentId: (id: string) => string
}>()

const emit = defineEmits<{
  downloadManifest: []
  clone: []
}>()

const { t } = useI18n()
const router = useRouter()

const fingerprintBits = computed((): string[] => {
  const p = props.protocol
  if (!p) return []
  const bits: string[] = []
  if (p.game_type) bits.push(`${t('experiment.fingerprintGame')}: ${p.game_type}`)
  if (p.engine_version) bits.push(`${t('experiment.fingerprintEngine')}: ${p.engine_version}`)
  if (p.decision_schema_version != null) {
    bits.push(`${t('experiment.fingerprintDecision')}: v${p.decision_schema_version}`)
  }
  if (p.phases?.length) bits.push(`${t('experiment.fingerprintPhases')}: ${p.phases.join(', ')}`)
  for (const [phase, key] of Object.entries(p.prompt_keys ?? {})) {
    const label = ['playing', 'bidding'].includes(phase) ? t(`promptDesign.phases.${phase}`) : phase
    bits.push(
      `${t('experiment.fingerprintPromptVersion')} · ${label}: ${p.prompt_versions?.[key] || t('report.missing')}`,
    )
    bits.push(
      `${t('experiment.fingerprintPromptHash')} · ${label}: ${p.prompt_hashes?.[key] || t('report.missing')}`,
    )
  }
  if (p.prompt_keys && Object.keys(p.prompt_keys).length) {
    bits.push(
      `${t('experiment.fingerprintPrompts')}: ${Object.entries(p.prompt_keys)
        .map(([k, v]) => `${k}→${v}`)
        .join(', ')}`,
    )
  }
  if (p.rules_ref) bits.push(`${t('experiment.fingerprintRules')}: ${p.rules_ref}`)
  return bits
})
</script>

<template>
  <div class="space-y-ink-6">
    <section
      v-if="validation?.control_experiment_ids.length"
      class="rounded-ink-md border border-ink-border/80 bg-ink-surface-muted/30 p-4"
    >
      <div class="flex flex-wrap items-center gap-2 text-sm text-ink-text-secondary">
        <span class="font-medium text-ink-text">{{ t('experiment.linkedControls') }}</span>
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
        <ul v-if="fingerprintBits.length" class="flex flex-wrap gap-1.5 text-xs">
          <li
            v-for="(bit, i) in fingerprintBits"
            :key="i"
            class="rounded-[6px] bg-ink-surface px-1.5 py-0.5 text-ink-text-secondary"
          >
            {{ bit }}
          </li>
        </ul>
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
