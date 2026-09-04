import type { Experiment, ExperimentVerdictKey } from '@/api/experimentApi'

/**
 * The five phases of the experiment workbench. Each one answers a single
 * question and offers a single next step, so the detail page renders one
 * phase at a time instead of stacking every strip and hiding parts with `v-if`.
 */
export type ExperimentStageId = 'empty' | 'collecting' | 'harvest' | 'control' | 'verdict'

/** Semantic actions a phase can ask the page to perform. */
export type ExperimentStageAction =
  | 'collect'
  | 'watch'
  | 'review-decisions'
  | 'train'
  | 'register-player'
  | 'open-control'
  | 'collect-control'
  | 'compare'
  | 'settings'

export function resolveStageId(experiment: Experiment): ExperimentStageId {
  const status = experiment.summary.status
  if (status === 'pending_collect') return 'empty'
  if (status === 'collecting') return 'collecting'
  if (experiment.delta) return 'verdict'
  if (experiment.next_step?.id === 'open_control') return 'control'
  return 'harvest'
}

/**
 * Games still to run before the target is met. Collecting past the target is
 * allowed, so this can be zero while the experiment stays usable.
 */
export function remainingGames(experiment: Experiment): number {
  const { target_games: target, finished_games: finished } = experiment.summary
  return Math.max(0, target - finished)
}

export function verdictKeyOf(experiment: Experiment): ExperimentVerdictKey {
  const delta = experiment.delta
  if (!delta) return 'no_data'
  if (delta.verdict_key) return delta.verdict_key
  // Older payloads predate `verdict_key`; derive the same claim client-side.
  if (delta.inconclusive_reason === 'no_games') return 'no_data'
  if (delta.inconclusive_reason === 'peer_not_ready') return 'peer_pending'
  const diff = delta.landlord_win_rate_diff
  if (diff == null) return 'no_data'
  if (Math.abs(diff) < 0.02) return 'even'
  return diff > 0 ? 'stronger' : 'weaker'
}

/**
 * Roughly how many more decisive games would lift the pair out of low power.
 * Used to turn "not enough evidence" into an actionable number.
 */
export function gamesNeededForPower(experiment: Experiment, minDecisive = 20): number {
  const delta = experiment.delta
  if (!delta) return minDecisive
  const decisive = Math.min(delta.this_decisive_n, delta.peer_decisive_n)
  return Math.max(0, minDecisive - decisive)
}
