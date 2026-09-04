<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Icon } from '@iconify/vue'
import type { FirstRunStep, FirstRunStepId } from '@/utils/firstRun'
import { firstIncompleteStep } from '@/utils/firstRun'
import UiBadge from '@/components/ui/Badge.vue'
import UiButton from '@/components/ui/Button.vue'

const props = defineProps<{
  steps: FirstRunStep[]
  requiredPlayers: number
  demoLoading?: boolean
}>()

const emit = defineEmits<{
  settings: []
  players: []
  create: []
  demo: []
}>()

const { t } = useI18n()

const current = computed(() => firstIncompleteStep(props.steps))
const allDone = computed(() => current.value == null)

function actionLabel(id: FirstRunStepId): string {
  if (id === 'provider') return t('firstRun.goSettings')
  if (id === 'players') return t('firstRun.goPlayers')
  return t('experiment.create')
}

function runAction(id: FirstRunStepId): void {
  if (id === 'provider') emit('settings')
  else if (id === 'players') emit('players')
  else emit('create')
}
</script>

<template>
  <section
    v-if="!allDone"
    class="rounded-ink-md border border-ink-border bg-ink-surface px-3 py-2.5"
  >
    <div class="flex flex-wrap items-start justify-between gap-2">
      <div>
        <h2 class="text-sm font-semibold text-ink-text">{{ t('firstRun.title') }}</h2>
        <p class="mt-0.5 text-xs text-ink-text-secondary">{{ t('firstRun.subtitle') }}</p>
      </div>
      <UiButton size="sm" variant="ghost" :loading="demoLoading" @click="emit('demo')">
        {{ t('experiment.loadDemo') }}
      </UiButton>
    </div>

    <ol class="mt-3 space-y-2">
      <li
        v-for="(step, index) in steps"
        :key="step.id"
        class="flex flex-wrap items-center gap-2 rounded-ink border border-ink-border/80 px-2.5 py-2"
        :class="step.id === current ? 'bg-ink-surface-muted/70' : 'bg-ink-surface-muted/30'"
      >
        <span class="w-5 text-center text-xs tabular-nums text-ink-text-muted">{{ index + 1 }}</span>
        <Icon
          :icon="step.done ? 'lucide:circle-check' : 'lucide:circle'"
          class="h-4 w-4"
          :class="step.done ? 'text-ink-success' : 'text-ink-text-muted'"
        />
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium text-ink-text">{{ t(`firstRun.step.${step.id}`) }}</p>
          <p class="text-xs text-ink-text-secondary">
            {{
              step.id === 'players'
                ? t('firstRun.hint.players', { n: requiredPlayers })
                : t(`firstRun.hint.${step.id}`)
            }}
          </p>
        </div>
        <UiBadge v-if="step.done" variant="success" size="xs">{{ t('firstRun.done') }}</UiBadge>
        <UiButton
          v-else-if="step.id === current"
          size="sm"
          @click="runAction(step.id)"
        >
          {{ actionLabel(step.id) }}
        </UiButton>
      </li>
    </ol>
  </section>
</template>
