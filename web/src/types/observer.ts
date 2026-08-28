/** ObserverSnapshot — universal board protocol for GenericBoard. */

export type ObserverLastAction = {
  type: string
  cards?: string[]
  label?: string
}

export type ObserverPlayer = {
  id: string
  name?: string
  role?: string
  is_active: boolean
  hand_count: number
  hand_cards?: string[]
  badges?: string[]
  last_action?: ObserverLastAction
}

export type ObserverTableSlot = {
  key: string
  label: string
  cards?: string[]
}

export type ObserverSnapshot = {
  game_type: string
  phase: string
  round: number
  current_player_id: string | null
  players: ObserverPlayer[]
  table?: {
    slots?: ObserverTableSlot[]
  }
  extras?: Record<string, unknown>
}

export function isObserverSnapshot(data: unknown): data is ObserverSnapshot {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>
  return Array.isArray(d.players) && typeof d.phase === 'string'
}

/** Adapt legacy dict-shaped payloads during rollout / replay. */
export function coerceObserverSnapshot(
  data: unknown,
  fallbackGameType = 'unknown',
): ObserverSnapshot | null {
  if (!data || typeof data !== 'object') return null
  if (isObserverSnapshot(data)) {
    return {
      ...data,
      game_type: data.game_type || fallbackGameType,
      current_player_id: data.current_player_id ?? null,
      players: data.players.map((p) => ({
        ...p,
        is_active: Boolean(p.is_active),
        hand_count: p.hand_count ?? p.hand_cards?.length ?? 0,
      })),
    }
  }

  const d = data as Record<string, unknown>
  const rawPlayers = d.players
  const hands = (d.hands as Record<string, string[]> | undefined) ?? {}
  const current =
    (d.current_player_id as string | undefined) ??
    (d.current_player as string | undefined) ??
    null

  const players: ObserverPlayer[] = []
  if (rawPlayers && typeof rawPlayers === 'object' && !Array.isArray(rawPlayers)) {
    for (const [id, info] of Object.entries(rawPlayers as Record<string, Record<string, unknown>>)) {
      const hand = hands[id]
      players.push({
        id,
        role: String(info.role ?? 'unknown'),
        is_active: current === id,
        hand_count: Number(info.hand_count ?? info.cards_left ?? info.cardsLeft ?? hand?.length ?? 0),
        hand_cards: hand,
        badges: info.role ? [String(info.role)] : [],
      })
    }
  }

  const slots: ObserverTableSlot[] = []
  const landlord = d.landlord_cards as string[] | undefined
  if (landlord?.length) {
    slots.push({ key: 'landlord', label: '底牌', cards: landlord })
  }

  return {
    game_type: String(d.game_type ?? fallbackGameType),
    phase: String(d.phase ?? 'playing'),
    round: Number(d.round ?? 0),
    current_player_id: current,
    players,
    table: { slots },
    extras: {
      is_terminal: d.is_terminal,
      winner: d.winner,
      winner_role: d.winner_role,
    },
  }
}
