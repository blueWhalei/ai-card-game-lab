<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { DecisionPoint } from '@/api/decision'
import { actionTypeLabel } from '@/utils/traceOutput'
import CardDisplay from '@/components/game/CardDisplay.vue'

const props = defineProps<{
  point: Pick<DecisionPoint, 'chosen_action' | 'hand_cards'>
  actionId?: string
}>()
const { t } = useI18n()
const bidPoints = computed(() =>
  props.point.chosen_action.action_type === 'BID'
    ? /^BID\|\|([1-3])$/.exec(props.actionId ?? '')?.[1]
    : undefined,
)
</script>
<template>
  <div class="space-y-ink-4">
    <p class="text-caption text-ink-text-muted">{{ t('focus.action') }}</p>
    <CardDisplay
      v-if="point.chosen_action.cards.length"
      :cards="point.chosen_action.cards"
      :show-count="false"
      size="table"
    />
    <p class="text-title text-ink-text">
      {{
        bidPoints
          ? t('paired.bidPoints', { n: bidPoints })
          : actionTypeLabel(point.chosen_action.action_type)
      }}
    </p>
    <p
      v-if="actionId && point.chosen_action.action_type === 'BID' && !bidPoints"
      class="break-all text-caption text-ink-text-secondary"
    >
      {{ t('paired.actionId') }}: {{ actionId }}
    </p>
    <details class="space-y-ink-3 text-caption">
      <summary class="cursor-pointer text-ink-text-secondary">{{ t('decision.hand') }}</summary>
      <CardDisplay :cards="point.hand_cards" :show-count="false" size="mini" />
    </details>
  </div>
</template>
