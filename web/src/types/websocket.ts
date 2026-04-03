export interface WsMessage<T = unknown> {
  type: string
  data: T
}

export interface ThinkingData {
  playerId: string
  playerName: string
  content: string
  done: boolean
}

export interface ActionData {
  playerId: string
  playerName: string
  actionType: string
  cards: string[]
  round: number
}

export interface StateUpdateData {
  round: number
  currentPlayer: string
  players: Record<
    string,
    {
      cardsLeft: number
      role: string
    }
  >
  lastAction: {
    playerId: string
    actionType: string
    cards: string[]
  } | null
}

export interface GameEndedData {
  winnerId: string
  winnerName: string
  winnerRole: string
  totalRounds: number
  durationMs: number
  summary: Record<
    string,
    {
      role: string
      result: string
    }
  >
}

// Server-sent WebSocket event payload types (snake_case from backend)
export interface GameStartedPayload {
  players?: Record<string, { cardsLeft: number; role: string }>
  hands?: Record<string, string[]>
  landlord_cards?: string[]
  current_player?: string
}

export interface ThinkingPayload {
  player_id: string
  player_name?: string
}

/** Streaming chunk payload - sent for each LLM output chunk */
export interface ThinkingChunkPayload {
  player_id: string
  chunk: string
  chunk_type?: "reasoning" | "content"  // 新增：区分推理和最终答案
}

/** 思考历史条目，包含分开的推理和答案 */
export interface ThinkingHistoryEntry {
  playerId: string
  round: number
  reasoning?: string  // 推理过程
  answer?: string     // 最终答案
  thinking: string    // 完整思考（向后兼容）
  responseTimeMs: number
  promptTokens?: number | null
  completionTokens?: number | null
  totalTokens?: number | null
  modelProvider?: string
  modelName?: string
  actionType?: string
  cards?: string[]
  promptPreview?: string
  rawResponsePreview?: string
  promptMessages?: Array<{ role: string; content: string }>
  rawResponseFull?: string
}

/** Complete thinking payload - sent when LLM finishes */
export interface ThinkingCompletePayload {
  player_id?: string
  thinking?: string
  round?: number
  response_time_ms?: number
  prompt_tokens?: number | null
  completion_tokens?: number | null
  total_tokens?: number | null
  model_provider?: string
  model_name?: string
  action_preview?: {
    action_type?: string
    cards?: string[]
    target?: string
  }
  prompt_preview?: string
  raw_response_preview?: string
  prompt_messages?: Array<{ role: string; content: string }>
  raw_response_full?: string
}

/** @deprecated Use ThinkingCompletePayload instead */
export interface ThinkingContentPayload {
  thinking?: string
  round?: number
  player_id?: string
  response_time_ms?: number
  prompt_tokens?: number | null
  completion_tokens?: number | null
  total_tokens?: number | null
  model_provider?: string
  model_name?: string
  action_preview?: {
    action_type?: string
    cards?: string[]
  }
  prompt_preview?: string
  raw_response_preview?: string
  prompt_messages?: Array<{ role: string; content: string }>
  raw_response_full?: string
}

export interface ActionPayload {
  player_id?: string
  action_type?: string
  cards?: string[]
  round?: number
}

export interface StateUpdatePayload {
  players?: Record<string, { cardsLeft: number; role: string }>
  hands?: Record<string, string[]>
  current_player?: string
  landlord_cards?: string[]
}

export interface GameEndedPayload {
  winner_id?: string
  winner_name?: string
  winner_role?: string
  total_rounds?: number
}

export interface ErrorPayload {
  message?: string
}
