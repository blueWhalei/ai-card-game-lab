/** Retain a submission key after an uncertain response, including page reloads. */
export function createCollectRequestCache() {
  const pending = new Map<string, { count: number; key: string }>()

  function storage(): Storage | null {
    try {
      return window.sessionStorage
    } catch {
      return null // Storage may be disabled; the in-memory key still protects retries.
    }
  }

  function get(experimentId: string, count: number): string {
    const name = `cardlab:collect:${experimentId}`
    let entry = pending.get(experimentId)
    if (!entry) {
      try {
        const saved: unknown = JSON.parse(storage()?.getItem(name) ?? 'null')
        if (
          saved &&
          typeof saved === 'object' &&
          'count' in saved &&
          'key' in saved &&
          typeof saved.count === 'number' &&
          typeof saved.key === 'string'
        ) {
          entry = { count: saved.count, key: saved.key }
        }
      } catch {
        // A malformed storage entry does not prevent a new submission.
      }
    }
    if (!entry || entry.count !== count) entry = { count, key: crypto.randomUUID() }
    pending.set(experimentId, entry)
    try {
      storage()?.setItem(name, JSON.stringify(entry))
    } catch {
      /* Use memory fallback. */
    }
    return entry.key
  }

  function complete(experimentId: string): void {
    pending.delete(experimentId)
    try {
      storage()?.removeItem(`cardlab:collect:${experimentId}`)
    } catch {
      /* Storage is optional. */
    }
  }

  return { get, complete }
}
