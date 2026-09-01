export type CompareMetricKind = 'higher' | 'lower'

export type CompareMetricDef = {
  id: string
  /** Core metrics stay visible below xl; others use xl:table-cell */
  core?: boolean
  kind: CompareMetricKind
}

export const COMPARE_METRICS: CompareMetricDef[] = [
  { id: 'finished', kind: 'higher', core: true },
  { id: 'landlord', kind: 'higher', core: true },
  { id: 'pairedLandlord', kind: 'higher' },
  { id: 'p50', kind: 'lower' },
  { id: 'p95', kind: 'lower' },
  { id: 'tokens', kind: 'lower' },
  { id: 'train', kind: 'higher', core: true },
  { id: 'parser', kind: 'higher' },
]

/** Map compare UI metric ids to engine capability eval_metric_ids. */
const METRIC_CAPABILITY_REQUIREMENT: Partial<Record<string, string>> = {
  landlord: 'role:landlord',
  pairedLandlord: 'role:landlord',
  parser: 'parser_success',
  train: 'train_usable',
  p50: 'latency_p50_p95',
  p95: 'latency_p50_p95',
}

/** Filter compare columns by engine eval_metric_ids. Ungated metrics always show. */
export function compareMetricsForEngine(evalMetricIds: string[]): CompareMetricDef[] {
  const set = new Set(evalMetricIds)
  return COMPARE_METRICS.filter((m) => {
    const req = METRIC_CAPABILITY_REQUIREMENT[m.id]
    return req == null || set.has(req)
  })
}

export type NumericCell = {
  value: number | null
  display: string
}

/** Pick best index: higher kind prefers max, lower prefers min. Nulls ignored. */
export function bestIndex(
  values: Array<number | null>,
  kind: CompareMetricKind,
): number | null {
  let best: number | null = null
  let bestVal: number | null = null
  for (let i = 0; i < values.length; i++) {
    const v = values[i]
    if (v == null || Number.isNaN(v)) continue
    if (
      bestVal == null ||
      (kind === 'higher' ? v > bestVal : v < bestVal)
    ) {
      bestVal = v
      best = i
    }
  }
  return best
}

/** Format delta vs best. Rates use pp; ms use s/ms; counts use raw. */
export function formatDelta(
  value: number | null,
  best: number | null,
  unit: 'rate' | 'ms' | 'count',
): string | null {
  if (value == null || best == null) return null
  const delta = value - best
  if (Math.abs(delta) < 1e-9) return null
  if (unit === 'rate') {
    const pp = delta * 100
    if (Math.abs(pp) < 0.5) return null
    const sign = pp > 0 ? '+' : '−'
    return `${sign}${Math.abs(pp).toFixed(0)}pp`
  }
  if (unit === 'ms') {
    const abs = Math.abs(delta)
    const sign = delta > 0 ? '+' : '−'
    if (abs >= 1000) {
      return `${sign}${(abs / 1000).toFixed(1)}s`
    }
    return `${sign}${Math.round(abs)}ms`
  }
  const sign = delta > 0 ? '+' : '−'
  return `${sign}${Math.abs(Math.round(delta))}`
}

export function metricUnit(id: string): 'rate' | 'ms' | 'count' {
  if (id === 'p50' || id === 'p95') return 'ms'
  if (id === 'finished' || id === 'tokens') return 'count'
  return 'rate'
}
