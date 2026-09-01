<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
import type { ExperimentNextStep } from '@/api/experimentApi'
import UiBadge from '@/components/ui/Badge.vue'
import UiButton from '@/components/ui/Button.vue'
import UiDropdownMenu from '@/components/ui/DropdownMenu.vue'
import type { DropdownMenuItemDef } from '@/components/ui/DropdownMenu.vue'

const props = defineProps<{
  name: string
  statusLabel: string
  statusVariant: 'default' | 'success' | 'warning' | 'danger' | 'accent' | 'muted'
  benchmark?: boolean
  finished: number
  target: number
  usableDecisions: number
  subtitle?: string
  nextStep: ExperimentNextStep | null
  nextStepHint: string
  primaryLabel: string
  primaryDisabled?: boolean
  latestGameId?: string | null
  openMenuItems: DropdownMenuItemDef[]
}>()

const emit = defineEmits<{
  back: []
  primary: []
  openLatest: []
  menuSelect: [id: string]
}>()

const { t } = useI18n()

const primaryIsWatch = computed(() => props.nextStep?.action === 'games')

const showWatchSecondary = computed(
  () => !primaryIsWatch.value && Boolean(props.latestGameId),
)
</script>

<template>
  <div
    class="rounded-ink-md border border-ink-border bg-ink-surface-muted/50 px-3 py-2.5"
  >
    <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
      <button
        type="button"
        class="inline-flex shrink-0 items-center gap-1 text-sm text-ink-text-secondary hover:text-ink-text"
        @click="emit('back')"
      >
        <Icon icon="lucide:arrow-left" class="h-4 w-4" />
        <span class="hidden sm:inline">{{ t('experiment.backToList') }}</span>
      </button>

      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-2">
          <h1 class="truncate text-base font-semibold text-ink-text">{{ name }}</h1>
          <UiBadge :variant="statusVariant" class="shrink-0">{{ statusLabel }}</UiBadge>
          <UiBadge v-if="benchmark" variant="accent" class="shrink-0">
            {{ t('experiment.modeBenchmark') }}
          </UiBadge>
          <span class="shrink-0 text-xs tabular-nums text-ink-text-secondary sm:text-sm">
            {{ finished }}/{{ target }}
          </span>
          <span
            v-if="usableDecisions > 0"
            class="shrink-0 text-xs tabular-nums text-ink-primary"
          >
            {{ t('experiment.kpiUsable') }} {{ usableDecisions }}
          </span>
        </div>
        <p v-if="subtitle?.trim()" class="mt-0.5 line-clamp-1 text-xs text-ink-text-secondary">
          {{ subtitle }}
        </p>
        <p
          v-else-if="nextStepHint"
          class="mt-0.5 line-clamp-1 text-xs text-ink-text-secondary"
        >
          {{ nextStepHint }}
        </p>
      </div>

      <div class="flex shrink-0 flex-wrap items-center gap-1.5">
        <UiButton size="sm" :disabled="primaryDisabled" @click="emit('primary')">
          <Icon v-if="primaryIsWatch" icon="lucide:eye" class="mr-1 h-3.5 w-3.5" />
          <Icon
            v-else-if="nextStep?.action === 'collect'"
            icon="lucide:play"
            class="mr-1 h-3.5 w-3.5"
          />
          {{ primaryLabel }}
        </UiButton>
        <UiButton
          v-if="showWatchSecondary"
          size="sm"
          variant="secondary"
          type="button"
          @click="emit('openLatest')"
        >
          {{ t('experiment.openLatest') }}
        </UiButton>
        <UiDropdownMenu :items="openMenuItems" @select="emit('menuSelect', $event)">
          <UiButton size="sm" variant="secondary" type="button">
            <Icon icon="lucide:more-horizontal" class="h-4 w-4" />
          </UiButton>
        </UiDropdownMenu>
      </div>
    </div>
  </div>
</template>
