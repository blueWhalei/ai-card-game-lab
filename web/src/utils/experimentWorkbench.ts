import { tt } from '@/i18n'

export function sanitizeNamePart(raw: string): string {
  return raw.trim().replace(/[\\/:*?"<>|]+/g, '-').slice(0, 60) || 'experiment'
}

export function remainingCollectCount(target: number, finished: number): number {
  return Math.max(1, Math.min(50, target - finished))
}

export function uniqueFilledIds(ids: string[]): boolean {
  const filled = ids.filter((id) => id.trim().length > 0)
  return filled.length === ids.length && new Set(filled).size === ids.length
}

/** Seat labels for a control experiment: challenger + remaining baselines. */
export function controlSlotLabels(seatCount: number): string[] {
  if (seatCount < 2) return []
  const labels = [tt('control.newPlayer')]
  const baselineCount = seatCount - 1
  if (baselineCount === 1) {
    labels.push(tt('control.baseline'))
    return labels
  }
  for (let i = 0; i < baselineCount; i++) {
    labels.push(tt('control.baselineN', { letter: String.fromCharCode(65 + i) }))
  }
  return labels
}

/** Prefill seats: first slot is challenger, remaining unique baselines from the source experiment. */
export function initialControlPlayerIds(
  seatCount: number,
  challengerId: string,
  baselinePool: string[],
): string[] {
  const seats = Array.from({ length: Math.max(0, seatCount) }, () => '')
  if (seats.length === 0) return seats
  seats[0] = challengerId
  const used = new Set<string>()
  if (challengerId) used.add(challengerId)
  let poolIdx = 0
  for (let i = 1; i < seats.length; i++) {
    while (poolIdx < baselinePool.length && used.has(baselinePool[poolIdx] ?? '')) {
      poolIdx += 1
    }
    const next = baselinePool[poolIdx] ?? ''
    seats[i] = next
    if (next) used.add(next)
    poolIdx += 1
  }
  return seats
}

export function formatWinRate(rate: number): string {
  return `${(rate * 100).toFixed(0)}%`
}

export function formatWinRateCi(ci: [number, number] | undefined): string {
  if (!ci) return '—'
  return `${(ci[0] * 100).toFixed(0)}–${(ci[1] * 100).toFixed(0)}%`
}

/** Signed percentage-point delta, e.g. 0.04 → "+4.0pp". */
export function formatDeltaPp(diff: number | null | undefined): string {
  if (diff == null || Number.isNaN(diff)) return '—'
  const pp = diff * 100
  const abs = Math.abs(pp)
  const body = abs >= 10 ? abs.toFixed(0) : abs.toFixed(1)
  if (pp > 0) return `+${body}pp`
  if (pp < 0) return `−${body}pp`
  return '0pp'
}

export const EXPERIMENT_SCENARIO_IDS = ['bidding', 'playing', 'endgame', 'bomb'] as const

export type ExperimentScenarioId = (typeof EXPERIMENT_SCENARIO_IDS)[number]

export function scenarioHasDecisions(
  scores: Record<string, { n?: number }> | undefined,
): boolean {
  if (!scores) return false
  return EXPERIMENT_SCENARIO_IDS.some((id) => (scores[id]?.n ?? 0) > 0)
}
