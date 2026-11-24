<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { batchPuzzleExtract, type PuzzlePackSummary } from '@/api/puzzleApi'

const props = defineProps<{ manifest: PuzzlePackSummary; frozen?: boolean }>()
const { t } = useI18n()
const batch = computed(() => batchPuzzleExtract(props.manifest))
const counts = computed(() => {
  const value = batch.value
  if (!value) return null
  return {
    games: value.selection.source_game_ids.length,
    candidates: value.selection.candidates.length,
    eligible: value.selection.candidates.filter((p) => p.spread >= value.min_spread).length,
    selected: props.manifest.puzzle_count,
    selectedGames: value.selection.selected_game_ids.length,
    checked: Object.values(value.source_checks).filter(
      (p) =>
        /^[a-f0-9]{64}$/.test(p.decision_hash ?? '') && /^[a-f0-9]{64}$/.test(p.puzzle_hash ?? ''),
    ).length,
  }
})
const evaluation = computed(() => {
  const params = batch.value?.evaluator_params ?? {}
  const count = (key: string) =>
    typeof params[key] === 'number' && Number.isSafeInteger(params[key]) ? params[key] : '—'
  return {
    worlds: count('determinizations'),
    repeats: count('rollouts_per_world'),
    candidates: count('max_candidates'),
    steps: count('max_steps'),
    seed: count('seed'),
    policy:
      params.opponent_kind_effective === 'heuristic'
        ? t('puzzleBatch.heuristic')
        : typeof params.opponent_kind_effective === 'string'
          ? params.opponent_kind_effective
          : '—',
  }
})
</script>

<template>
  <section v-if="batch && counts" class="space-y-ink-2" :aria-label="t('puzzleBatch.title')">
    <p class="font-semibold">{{ t('puzzleBatch.title') }}</p>
    <p>{{ t('puzzleBatch.counts', counts) }}</p>
    <p>
      {{
        t('puzzleBatch.rule', {
          threshold: batch.min_spread,
          perGame: batch.max_per_game,
          total: batch.max_total,
        })
      }}
    </p>
    <p>{{ t('puzzleBatch.estimates') }}</p>
    <p>{{ t('puzzleBatch.evaluation', evaluation) }}</p>
    <p>{{ t(frozen ? 'puzzleBatch.publishedChecks' : 'puzzleBatch.checks', counts) }}</p>
    <p class="text-caption">{{ t('puzzleBatch.limits') }}</p>
  </section>
</template>
