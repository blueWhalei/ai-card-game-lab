/** Engine capability as returned by GET /system/engines (seeds as count only). */
export type EngineInfo = {
  id: string
  game_type: string
  min_players: number
  max_players: number
  engine_version: string
  phases: string[]
  prompt_keys: Record<string, string>
  supports_deal_seed: boolean
  benchmark_seed_count: number
  roles: string[]
  eval_metric_ids: string[]
  decision_schema_version: number
  rules_ref: string | null
}

export function engineById(engines: EngineInfo[], id: string): EngineInfo | undefined {
  return engines.find((e) => e.id === id)
}

export function defaultEngineId(engines: EngineInfo[]): string {
  return engines[0]?.id ?? ''
}

export function supportsBenchmark(engine: EngineInfo | undefined): boolean {
  return Boolean(engine?.supports_deal_seed && engine.benchmark_seed_count > 0)
}

export function hasEvalMetric(engine: EngineInfo | undefined, metricId: string): boolean {
  return Boolean(engine?.eval_metric_ids.includes(metricId))
}

export function playerCountLabel(engine: EngineInfo | undefined): string {
  if (!engine) return '—'
  if (engine.min_players === engine.max_players) return String(engine.min_players)
  return `${engine.min_players}–${engine.max_players}`
}

export function maxSelectable(engine: EngineInfo | undefined): number {
  return engine?.max_players ?? 0
}

export function isValidPlayerSelection(
  count: number,
  engine: EngineInfo | undefined,
): boolean {
  if (!engine) return false
  return count >= engine.min_players && count <= engine.max_players
}
