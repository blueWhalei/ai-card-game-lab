<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { experimentProgressParts } from '@/utils/experimentStage'
import UiButton from '@/components/ui/Button.vue'

const props = withDefaults(
  defineProps<{
    /** The one sentence this act exists to say. */
    claim: string
    /** Supporting line under the claim. */
    detail?: string
    /** Headline number when the phase is really about a quantity. */
    metricValue?: number | null
    metricTotal?: number | null
    metricLabel?: string
    actionLabel?: string
    actionDisabled?: boolean
    actionLoading?: boolean
    /** Renders the claim as provisional rather than settled. */
    weak?: boolean
  }>(),
  {
    actionDisabled: false,
    actionLoading: false,
    weak: false,
  },
)

const emit = defineEmits<{
  action: []
}>()

const { t } = useI18n()

const hasMetric = computed(() => props.metricValue != null)

const progress = computed(() => {
  if (props.metricValue == null || props.metricTotal == null) return null
  return experimentProgressParts(props.metricValue, props.metricTotal)
})

const progressPercent = computed(() => {
  if (!progress.value || progress.value.target <= 0) return null
  return Math.min(100, Math.round((progress.value.shownFinished / progress.value.target) * 100))
})
</script>

<template>
  <section
    class="stage-action ink-section grid gap-ink-6 py-ink-2"
    :class="{ 'has-metric': hasMetric }"
  >
    <div class="min-w-0">
      <h2 class="ink-verdict-claim max-w-2xl" :class="{ 'is-weak': weak }">{{ claim }}</h2>
      <p v-if="detail" class="mt-ink-3 max-w-2xl text-body leading-relaxed text-ink-text-secondary">
        {{ detail }}
      </p>
      <div
        v-if="actionLabel || $slots.secondary || $slots['before-action']"
        class="mt-ink-6 flex flex-wrap items-center gap-ink-3"
      >
        <slot name="before-action" />
        <UiButton
          v-if="actionLabel"
          size="lg"
          :disabled="actionDisabled"
          :loading="actionLoading"
          @click="emit('action')"
          >{{ actionLabel }}</UiButton
        >
        <slot name="secondary" />
      </div>
    </div>
    <div v-if="hasMetric" class="stage-metric">
      <p class="ink-verdict-number" :class="{ 'is-weak': weak }">
        {{ progress ? progress.shownFinished : metricValue }}
        <span v-if="progress" class="text-title font-normal text-ink-text-muted">
          / {{ progress.target }}</span
        >
      </p>
      <p v-if="metricLabel" class="mt-ink-2 text-caption text-ink-text-muted">{{ metricLabel }}</p>
      <p v-if="progress && progress.extra > 0" class="mt-ink-1 text-caption text-ink-text-muted">
        {{ t('stage.progressExtraOnly', { extra: progress.extra }) }}
      </p>
      <div
        v-if="progressPercent != null"
        class="mt-ink-4 h-1 overflow-hidden rounded-full bg-ink-border"
        role="presentation"
      >
        <div
          class="h-full rounded-full bg-ink-primary transition-[width]"
          :style="{ width: `${progressPercent}%` }"
        />
      </div>
    </div>
  </section>
</template>
<style scoped>
.stage-metric {
  border-top: 1px solid var(--ink-border);
  padding-top: var(--ink-space-4);
}
@media (min-width: 768px) {
  .has-metric {
    grid-template-columns: minmax(0, 1fr) 200px;
    align-items: center;
  }
  .stage-metric {
    border-top: 0;
    border-left: 1px solid var(--ink-border);
    padding: var(--ink-space-4) 0 var(--ink-space-4) var(--ink-space-8);
  }
}
</style>
