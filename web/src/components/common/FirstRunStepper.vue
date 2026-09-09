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
  <section v-if="!allDone" class="ink-section">
    <div class="flex flex-wrap items-start justify-between gap-ink-2">
      <div>
        <h2 class="text-title font-semibold text-ink-text">{{ t('firstRun.title') }}</h2>
        <p class="mt-ink-1 text-body text-ink-text-secondary">{{ t('firstRun.subtitle') }}</p>
      </div>
      <UiButton
        size="sm"
        variant="ghost"
        data-testid="load-demo-experiment"
        :loading="demoLoading"
        @click="emit('demo')"
      >
        {{ t('experiment.loadDemo') }}
      </UiButton>
    </div>

    <ol class="mt-ink-4 space-y-ink-3">
      <li
        v-for="(step, index) in steps"
        :key="step.id"
        class="flex flex-wrap items-center gap-ink-2"
        :class="step.id === current ? '' : 'opacity-70'"
      >
        <span class="w-5 text-center text-caption tabular-nums text-ink-text-muted">
          {{ index + 1 }}
        </span>
        <Icon
          :icon="step.done ? 'lucide:circle-check' : 'lucide:circle'"
          class="h-4 w-4"
          :class="step.done ? 'text-ink-success' : 'text-ink-text-muted'"
        />
        <div class="min-w-0 flex-1">
          <p class="text-body font-medium text-ink-text">{{ t(`firstRun.step.${step.id}`) }}</p>
          <p class="text-caption text-ink-text-secondary">
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
