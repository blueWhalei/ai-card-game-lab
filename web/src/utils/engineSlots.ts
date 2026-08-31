export type EngineInfo = {
  id: string
  min_players: number
  max_players: number
}

export function engineById(engines: EngineInfo[], id: string): EngineInfo | undefined {
  return engines.find((e) => e.id === id)
}

export function playerCountLabel(engine: EngineInfo | undefined): string {
  if (!engine) return '3'
  if (engine.min_players === engine.max_players) return String(engine.min_players)
  return `${engine.min_players}–${engine.max_players}`
}

export function maxSelectable(engine: EngineInfo | undefined): number {
  return engine?.max_players ?? 3
}

export function isValidPlayerSelection(
  count: number,
  engine: EngineInfo | undefined,
): boolean {
  const min = engine?.min_players ?? 3
  const max = engine?.max_players ?? 3
  return count >= min && count <= max
}
