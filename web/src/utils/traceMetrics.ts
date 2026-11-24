/** Same validity rules as the trace aggregate API. Missing values stay unknown. */
export function traceLatency(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null
}

export function traceParserStatus(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null
}
