<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type {
  ConclusionDraftBlunder,
  ExperimentDelta,
  ExperimentVerdictKey,
} from '@/api/experimentApi'
import { experimentApi } from '@/api/experimentApi'
import { formatDeltaPp, formatWinRateCi } from '@/utils/experimentWorkbench'
import { verdictHeadlineOf } from '@/utils/experimentStage'
import { useLocale } from '@/composables/useLocale'
import { getErrorMessage } from '@/utils/error'
import ExperimentScenarioBars from '@/components/experiment/ExperimentScenarioBars.vue'
import MetricHint from '@/components/common/MetricHint.vue'
import UiButton from '@/components/ui/Button.vue'
import UiDialog from '@/components/ui/Dialog.vue'
import UiTextarea from '@/components/ui/Textarea.vue'

const props = defineProps<{
  experimentId: string
  existingConclusion?: string
  delta: ExperimentDelta
  verdictKey: ExperimentVerdictKey
  /** Extra decisive games that would lift the pair out of low power. */
  gamesNeeded: number
  actionLabel?: string
  actionDisabled?: boolean
}>()

const emit = defineEmits<{
  action: []
  compare: []
  openPeer: []
  conclusionSaved: []
}>()

const { t } = useI18n()
const { locale } = useLocale()
const router = useRouter()

const weak = computed(() => !props.delta.can_conclude)

const headline = computed(() => verdictHeadlineOf(props.delta, props.gamesNeeded))

const claim = computed(() =>
  t(`stage.${headline.value.key}`, headline.value.params ?? {}),
)

/** Supporting line under a weak headline — names the provisional delta. */
const supportDetail = computed(() => {
  if (!weak.value) {
    return t('stage.evidence.sufficient', { n: props.delta.paired_n })
  }
  const key = props.verdictKey
  if (key === 'stronger' || key === 'weaker' || key === 'even') {
    return t('stage.diffSoFar', {
      delta: formatDeltaPp(props.delta.landlord_win_rate_diff),
      claim: t(`stage.verdict.${key}`),
    })
  }
  return ''
})

const supportLine = computed(() => {
  const parts = [
    t('stage.support.paired', { n: props.delta.paired_n }),
    t('stage.support.interval', {
      range: formatWinRateCi(props.delta.this_landlord_win_rate_ci ?? undefined),
    }),
  ]
  return parts.join(' · ')
})

const hasConclusion = computed(() => Boolean(props.existingConclusion?.trim()))
const draftOpen = ref(false)
const draftText = ref('')
const draftBlunders = ref<ConclusionDraftBlunder[]>([])
const draftLoading = ref(false)
const draftSaving = ref(false)
const draftError = ref('')

async function openDraft(): Promise<void> {
  draftError.value = ''
  draftLoading.value = true
  try {
    const res = await experimentApi.conclusionDraft(props.experimentId, locale.value)
    draftText.value = res.data.text
    draftBlunders.value = res.data.blunders ?? []
    draftOpen.value = true
  } catch (err) {
    draftError.value = getErrorMessage(err)
  } finally {
    draftLoading.value = false
  }
}

async function saveDraft(): Promise<void> {
  if (hasConclusion.value) {
    const ok = window.confirm(t('stage.draft.overwriteConfirm'))
    if (!ok) return
  }
  draftSaving.value = true
  draftError.value = ''
  try {
    await experimentApi.update(props.experimentId, { conclusion: draftText.value })
    draftOpen.value = false
    emit('conclusionSaved')
  } catch (err) {
    draftError.value = getErrorMessage(err)
  } finally {
    draftSaving.value = false
  }
}

function openBlunder(row: ConclusionDraftBlunder): void {
  draftOpen.value = false
  void router.push({
    path: '/pipeline/decisions',
    query: {
      experiment_id: props.experimentId,
      ...(row.game_id ? { game_id: row.game_id } : {}),
      decision_id: row.id,
    },
  })
}

function blunderLabel(row: ConclusionDraftBlunder): string {
  const loss =
    row.ev_loss == null || Number.isNaN(Number(row.ev_loss))
      ? '?'
      : Number(row.ev_loss).toFixed(2)
  return t('stage.draft.openBlunder', {
    round: row.round_number ?? '?',
    action: row.action_id || '?',
    loss,
  })
}
</script>

<template>
  <section id="experiment-verdict" class="ink-section py-ink-6">
    <p class="text-caption text-ink-text-muted">
      {{
        t(delta.relation === 'vs_source' ? 'experiment.deltaVsSource' : 'experiment.deltaVsControl')
      }}
      ·
      <button type="button" class="text-ink-primary hover:underline" @click="emit('openPeer')">
        {{ delta.peer_name }}
      </button>
    </p>

    <h2 class="ink-verdict-claim mt-ink-2" :class="{ 'is-weak': weak }">{{ claim }}</h2>

    <p
      v-if="weak"
      class="mt-ink-3 text-title font-normal tabular-nums text-ink-text-muted"
    >
      {{ t('stage.diffLabel') }}
      {{ formatDeltaPp(delta.landlord_win_rate_diff) }}
    </p>
    <p v-else class="ink-verdict-number mt-ink-3">
      {{ formatDeltaPp(delta.landlord_win_rate_diff) }}
    </p>

    <p class="mt-ink-1 flex flex-wrap items-center gap-ink-1 text-caption text-ink-text-muted">
      {{ supportLine }}
      <MetricHint
        :plain="t('metricHint.overallDelta.plain')"
        :formula="t('metricHint.overallDelta.formula')"
      />
    </p>

    <p v-if="supportDetail" class="mt-ink-4 max-w-2xl text-lead text-ink-text-secondary">
      {{ supportDetail }}
    </p>

    <div class="mt-ink-6 flex flex-wrap items-center gap-ink-3">
      <UiButton
        v-if="actionLabel"
        size="lg"
        :disabled="actionDisabled"
        @click="emit('action')"
      >
        {{ actionLabel }}
      </UiButton>
      <UiButton variant="secondary" @click="emit('compare')">
        {{ t('experiment.compareFull') }}
      </UiButton>
      <UiButton
        variant="ghost"
        :loading="draftLoading"
        @click="openDraft"
      >
        {{
          hasConclusion ? t('stage.draft.regenerate') : t('stage.draft.generate')
        }}
      </UiButton>
    </div>

    <p v-if="draftError && !draftOpen" class="mt-ink-2 text-caption text-ink-danger">
      {{ draftError }}
    </p>

    <div class="mt-ink-6 max-w-xl" :class="{ 'opacity-60': weak }">
      <ExperimentScenarioBars :diffs="delta.scenario_diffs" :weak="weak" />
    </div>

    <UiDialog
      :open="draftOpen"
      size="lg"
      :title="t('stage.draft.dialogTitle')"
      :description="t('stage.draft.dialogHint')"
      @update:open="draftOpen = $event"
    >
      <div class="space-y-ink-3">
        <UiTextarea v-model="draftText" :rows="14" class="font-mono text-caption" />
        <div v-if="draftBlunders.length > 0" class="space-y-ink-2">
          <p class="text-caption font-medium text-ink-text-secondary">
            {{ t('stage.draft.blundersHeading') }}
          </p>
          <ul class="space-y-ink-1">
            <li v-for="row in draftBlunders" :key="row.id">
              <button
                type="button"
                class="text-left text-caption text-ink-primary hover:underline"
                @click="openBlunder(row)"
              >
                {{ blunderLabel(row) }}
              </button>
            </li>
          </ul>
        </div>
        <p v-if="draftError" class="text-caption text-ink-danger">{{ draftError }}</p>
        <div class="flex flex-wrap justify-end gap-ink-2">
          <UiButton variant="ghost" :disabled="draftSaving" @click="draftOpen = false">
            {{ t('common.cancel') }}
          </UiButton>
          <UiButton :loading="draftSaving" @click="saveDraft">
            {{ t('stage.draft.write') }}
          </UiButton>
        </div>
      </div>
    </UiDialog>
  </section>
</template>
