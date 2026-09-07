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
  return Math.min(
    100,
    Math.round((progress.value.shownFinished / progress.value.target) * 100),
  )
})
</script>

<template>
  <section class="ink-section py-ink-6">
    <p v-if="hasMetric && progress" class="ink-verdict-number" :class="{ 'is-weak': weak }">
      {{ progress.shownFinished }}
      <span class="text-title font-normal text-ink-text-muted">
        / {{ progress.target }}
      </span>
    </p>
    <p v-else-if="hasMetric" class="ink-verdict-number" :class="{ 'is-weak': weak }">
      {{ metricValue }}
    </p>
    <p v-if="hasMetric && metricLabel" class="mt-ink-1 text-caption text-ink-text-muted">
      {{ metricLabel }}
      <span v-if="progress && progress.extra > 0" class="ml-ink-2">
        · {{ t('stage.progressExtraOnly', { extra: progress.extra }) }}
      </span>
    </p>

    <div
      v-if="progressPercent != null"
      class="mt-ink-3 h-px w-full max-w-md bg-ink-border"
      role="presentation"
    >
      <div
        class="h-px bg-ink-primary transition-[width] duration-(--ink-duration-content) ease-(--ink-ease-out)"
        :style="{ width: `${progressPercent}%` }"
      />
    </div>

    <h2
      class="ink-verdict-claim"
      :class="[{ 'is-weak': weak }, hasMetric ? 'mt-ink-4' : '']"
    >
      {{ claim }}
    </h2>
    <p v-if="detail" class="mt-ink-2 max-w-2xl text-lead text-ink-text-secondary">
      {{ detail }}
    </p>

    <div v-if="actionLabel || $slots.secondary || $slots['before-action']" class="mt-ink-6 flex flex-wrap items-center gap-ink-3">
      <slot name="before-action" />
      <UiButton
        v-if="actionLabel"
        size="lg"
        :disabled="actionDisabled"
        :loading="actionLoading"
        @click="emit('action')"
      >
        {{ actionLabel }}
      </UiButton>
      <slot name="secondary" />
    </div>
  </section>
</template>
