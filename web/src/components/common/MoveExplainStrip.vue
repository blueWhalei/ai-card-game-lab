<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import UiBadge from '@/components/ui/Badge.vue'
import {
  formatPlayAction,
  parseHandAnalysis,
  parseLegalActions,
  parseWinProbability,
  samePlayAction,
  type PlayAction,
} from '@/utils/traceOutput'
import { formatWinRate } from '@/utils/experimentWorkbench'
import { cn } from '@/lib/cn'

const LEGAL_PREVIEW = 8

const props = withDefaults(
  defineProps<{
    legalActions?: unknown
    chosen?: PlayAction | null
    parserOk?: boolean | null
    winProbability?: unknown
    handAnalysis?: unknown
    tone?: 'lab' | 'observer'
  }>(),
  {
    parserOk: null,
    tone: 'lab',
  },
)

const { t } = useI18n()
const expanded = ref(false)
const observer = computed(() => props.tone === 'observer')

const legal = computed(() => parseLegalActions(props.legalActions))
const win = computed(() => parseWinProbability(props.winProbability))
const hand = computed(() => parseHandAnalysis(props.handAnalysis))

const orderedLegal = computed(() => {
  const chosen = props.chosen
  if (!chosen) return legal.value
  const matched = legal.value.filter((item) => samePlayAction(item, chosen))
  const rest = legal.value.filter((item) => !samePlayAction(item, chosen))
  return [...matched, ...rest]
})

const visibleLegal = computed(() =>
  expanded.value ? orderedLegal.value : orderedLegal.value.slice(0, LEGAL_PREVIEW),
)

const hiddenCount = computed(() =>
  Math.max(0, orderedLegal.value.length - visibleLegal.value.length),
)

const hasContent = computed(
  () =>
    legal.value.length > 0 ||
    props.parserOk != null ||
    win.value != null ||
    hand.value != null,
)

function confidenceLabel(raw: string): string {
  if (raw === '高' || raw.toLowerCase() === 'high') return t('explain.confidenceHigh')
  if (raw === '中' || raw.toLowerCase() === 'medium') return t('explain.confidenceMid')
  if (raw === '低' || raw.toLowerCase() === 'low') return t('explain.confidenceLow')
  return raw
}

const chipClass = computed(() =>
  observer.value
    ? 'rounded-ink bg-ink-obs-bg px-2 py-1 text-xs text-ink-obs-muted'
    : 'rounded-ink bg-ink-surface-muted px-2 py-1 text-xs text-ink-text-secondary',
)

const chosenChipClass = computed(() =>
  observer.value
    ? 'rounded-ink border border-ink-obs-accent/50 bg-ink-obs-bg px-2 py-1 text-xs text-ink-obs-accent'
    : 'rounded-ink border border-ink-primary/40 bg-ink-primary-muted px-2 py-1 text-xs text-ink-text',
)
</script>

<template>
  <div v-if="hasContent" class="space-y-2">
    <div class="flex flex-wrap items-center gap-2">
      <UiBadge
        v-if="parserOk != null"
        :variant="parserOk ? 'success' : 'warning'"
        size="xs"
      >
        {{ parserOk ? t('filter.parseOk') : t('filter.ruleFallback') }}
      </UiBadge>
      <span
        v-if="win"
        class="text-xs"
        :class="observer ? 'text-ink-obs-muted' : 'text-ink-text-secondary'"
        :title="win.reasoning"
      >
        {{ t('explain.winProb', { rate: formatWinRate(win.probability) }) }}
        <template v-if="win.confidence">
          · {{ t('explain.confidence', { level: confidenceLabel(win.confidence) }) }}
        </template>
      </span>
      <span
        v-if="hand"
        class="text-xs"
        :class="observer ? 'text-ink-obs-muted' : 'text-ink-text-muted'"
      >
        {{
          t('explain.handShort', {
            bombs: hand.bomb_count,
            score: hand.strength_score.toFixed(2),
          })
        }}
        <template v-if="hand.rocket"> · {{ t('explain.rocket') }}</template>
      </span>
    </div>

    <div v-if="legal.length > 0">
      <p
        class="mb-1 text-xs font-medium"
        :class="observer ? 'text-ink-obs-muted' : 'text-ink-text-muted'"
      >
        {{ t('explain.legal', { n: legal.length }) }}
      </p>
      <div class="flex flex-wrap gap-1.5">
        <span
          v-for="(action, idx) in visibleLegal"
          :key="`${action.action_type}-${idx}`"
          :class="cn(samePlayAction(action, chosen) ? chosenChipClass : chipClass)"
        >
          {{ formatPlayAction(action) }}
        </span>
        <button
          v-if="hiddenCount > 0 || expanded"
          type="button"
          class="text-xs"
          :class="observer ? 'text-ink-obs-accent' : 'text-ink-primary'"
          @click="expanded = !expanded"
        >
          {{
            expanded
              ? t('explain.collapseLegal')
              : t('explain.moreLegal', { n: hiddenCount })
          }}
        </button>
      </div>
    </div>
  </div>
</template>
