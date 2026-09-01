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

const metaChipClass =
  'inline-flex h-5 shrink-0 items-center rounded-[6px] bg-ink-surface-muted px-1.5 text-xs font-medium tabular-nums leading-none text-ink-text-secondary'
</script>

<template>
  <div
    class="rounded-ink-md border border-ink-border bg-ink-surface-muted/50 px-3 py-2.5"
  >
    <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
      <!-- Left: identity + meta -->
      <div class="min-w-0 flex-1">
        <button
          type="button"
          class="mb-1.5 inline-flex h-6 items-center gap-1 text-xs text-ink-text-secondary hover:text-ink-text"
          @click="emit('back')"
        >
          <Icon icon="lucide:arrow-left" class="h-3.5 w-3.5" />
          <span>{{ t('experiment.backToList') }}</span>
        </button>

        <h1 class="truncate text-base font-semibold leading-tight text-ink-text">
          {{ name }}
        </h1>

        <div class="mt-1.5 flex flex-wrap items-center gap-1.5">
          <UiBadge :variant="statusVariant" size="xs">{{ statusLabel }}</UiBadge>
          <UiBadge v-if="benchmark" variant="accent" size="xs">
            {{ t('experiment.modeBenchmark') }}
          </UiBadge>
          <span :class="metaChipClass">
            {{ finished }}/{{ target }}
          </span>
          <span
            v-if="usableDecisions > 0"
            :class="[metaChipClass, 'bg-ink-primary-muted text-ink-primary']"
          >
            {{ t('experiment.kpiUsable') }} {{ usableDecisions }}
          </span>
        </div>

        <p
          v-if="subtitle?.trim()"
          class="mt-1.5 line-clamp-1 text-xs leading-snug text-ink-text-secondary"
        >
          {{ subtitle }}
        </p>
        <p
          v-else-if="nextStepHint"
          class="mt-1.5 line-clamp-1 text-xs leading-snug text-ink-text-secondary"
        >
          {{ nextStepHint }}
        </p>
      </div>

      <!-- Right: primary CTA + secondary + overflow, one tight cluster -->
      <div
        class="flex shrink-0 flex-wrap items-center gap-1.5 border-t border-ink-border pt-2 sm:border-t-0 sm:pt-0"
      >
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
          <Icon icon="lucide:eye" class="mr-1 h-3.5 w-3.5" />
          {{ t('experiment.openLatest') }}
        </UiButton>
        <UiDropdownMenu :items="openMenuItems" @select="emit('menuSelect', $event)">
          <UiButton size="sm" variant="secondary" type="button" :aria-label="t('common.more')">
            <Icon icon="lucide:more-horizontal" class="h-4 w-4" />
          </UiButton>
        </UiDropdownMenu>
      </div>
    </div>
  </div>
</template>
