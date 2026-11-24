export function recordedProgress(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1
    ? Math.round(value * 100)
    : null
}

export function trainingError(result: unknown): string | null {
  if (!result || typeof result !== 'object' || Array.isArray(result)) return null
  const error = (result as Record<string, unknown>).error
  return typeof error === 'string' && error.trim() ? error : null
}
