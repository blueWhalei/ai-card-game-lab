import type { ExperimentSummary } from '@/api/experimentApi'
import { tt } from '@/i18n'

export function experimentOutcomeText(
  summary: Pick<ExperimentSummary, 'status_counts' | 'games_with_winner'>,
): string {
  const counts = summary.status_counts
  const parts = (['finished', 'no_bid', 'cancelled', 'failed', 'interrupted'] as const)
    .filter((status) => (counts?.[status] ?? 0) > 0)
    .map((status) => tt(`experiment.outcomeCounts.${status}`, { n: counts![status]! }))
  parts.push(tt('experiment.decidedCount', { n: summary.games_with_winner }))
  return parts.join(' · ')
}
