import { ref, computed, nextTick } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'
import type {
  GameStartedPayload,
  ThinkingPayload,
  ThinkingChunkPayload,
  ThinkingCompletePayload,
  ThinkingContentPayload,
  ActionPayload,
  StateUpdatePayload,
  GameEndedPayload,
  ErrorPayload,
} from '@/types/websocket'

export interface PlayerInfo {
  cardsLeft: number
  role: string
}

export interface HistoryEntry {
  round: number
  playerId: string
  actionType: string
  cards: string[]
  thinking?: string
  responseTimeMs?: number
}

export interface ThinkingEntry {
  playerId: string
  round: number
  thinking: string
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
  reasoning?: string
  answer?: string
}

interface PendingThinkingEntry {
  text: string
  ms: number
  round?: number
  actionType?: string
  cards?: string[]
  promptTokens?: number | null
  completionTokens?: number | null
  totalTokens?: number | null
  modelProvider?: string
  modelName?: string
  promptPreview?: string
  rawResponsePreview?: string
  promptMessages?: Array<{ role: string; content: string }>
  rawResponseFull?: string
  reasoning?: string
  answer?: string
}

export function useGameWebSocket(gameId: string) {
  const { isConnected, connect, disconnect, onMessage } = useWebSocket(gameId)

  const playerHands = ref<Record<string, string[]>>({})
  const players = ref<Record<string, PlayerInfo>>({})
  const currentPlayer = ref('')
  const lastAction = ref<{ playerId: string; actionType: string; cards: string[] } | null>(null)
  const thinkingPlayer = ref('')
  const thinkingContent = ref('')
  // 新增：分开存储推理内容和最终答案
  const reasoningContent = ref('')
  const answerContent = ref('')
  const currentThinkingRound = ref<number | undefined>(undefined)
  const currentThinkingActionType = ref('')
  const currentThinkingCards = ref<string[]>([])
  const currentPromptPreview = ref('')
  const currentRawResponsePreview = ref('')
  const currentPromptMessages = ref<Array<{ role: string; content: string }>>([])
  const currentRawResponseFull = ref('')
  const pendingThinking = ref<Record<string, PendingThinkingEntry>>({})
  const lastResponseTimeMs = ref<Record<string, number>>({})
  const playerTokenTotals = ref<Record<string, number>>({})
  const playerLastRoundTokens = ref<Record<string, number>>({})
  const actionHistory = ref<HistoryEntry[]>([])
  const thinkingHistory = ref<ThinkingEntry[]>([])
  const landlordCards = ref<string[]>([])
  const isPaused = ref(false)
  const isStarted = ref(false)
  const isFinished = ref(false)
  const lastError = ref('')
  const winner = ref<{ id: string; name: string; role: string; totalRounds: number } | null>(null)
  const historyPanel = ref<HTMLElement | null>(null)

  // Per-player last action derived from actionHistory
  const playerLastActions = computed<Record<string, { actionType: string; cards: string[] }>>(
    () => {
      const map: Record<string, { actionType: string; cards: string[] }> = {}
      for (const entry of actionHistory.value) {
        map[entry.playerId] = { actionType: entry.actionType, cards: entry.cards }
      }
      return map
    },
  )

  function normalizePlayers(
    raw: Record<string, Record<string, unknown>> | undefined,
  ): Record<string, PlayerInfo> | undefined {
    if (!raw) return undefined
    const result: Record<string, PlayerInfo> = {}
    for (const [pid, info] of Object.entries(raw)) {
      result[pid] = {
        cardsLeft: (info.cardsLeft ?? info.cards_left ?? 0) as number,
        role: (info.role ?? 'unknown') as string,
      }
    }
    return result
  }

  function setupMessageHandlers(): void {
    onMessage('game_started', (d: unknown) => {
      const data = d as GameStartedPayload
      isStarted.value = true
      const normalized = normalizePlayers(
        data.players as Record<string, Record<string, unknown>> | undefined,
      )
      if (normalized) players.value = normalized
      if (data.hands) playerHands.value = data.hands
      if (data.landlord_cards) landlordCards.value = data.landlord_cards
      currentPlayer.value = data.current_player || ''
    })

    onMessage('thinking', (d: unknown) => {
      const data = d as ThinkingPayload
      thinkingPlayer.value = data.player_id || ''
      thinkingContent.value = '' // Reset for streaming
      reasoningContent.value = '' // 新增
      answerContent.value = '' // 新增
      currentThinkingRound.value = undefined
      currentThinkingActionType.value = ''
      currentThinkingCards.value = []
      currentPromptPreview.value = ''
      currentRawResponsePreview.value = ''
      currentPromptMessages.value = []
      currentRawResponseFull.value = ''
    })

    // Handle streaming chunks
    onMessage('thinking_chunk', (d: unknown) => {
      const data = d as ThinkingChunkPayload
      // 根据类型分别存储
      if (data.chunk_type === 'reasoning') {
        reasoningContent.value += data.chunk
      } else {
        answerContent.value += data.chunk
      }
      // 保持 thinkingContent 向后兼容
      thinkingContent.value += data.chunk
    })

    // Handle streaming complete
    onMessage('thinking_complete', (d: unknown) => {
      const data = d as ThinkingCompletePayload
      // Update with final thinking content
      if (data.thinking) {
        thinkingContent.value = data.thinking
      }
      currentThinkingRound.value = data.round
      currentThinkingActionType.value = data.action_preview?.action_type || ''
      currentThinkingCards.value = data.action_preview?.cards || []
      currentPromptPreview.value = data.prompt_preview || ''
      currentRawResponsePreview.value = data.raw_response_preview || ''
      currentPromptMessages.value = data.prompt_messages || []
      currentRawResponseFull.value = data.raw_response_full || ''

      const pid = data.player_id || thinkingPlayer.value
      pendingThinking.value[pid] = {
        text: data.thinking || thinkingContent.value,
        ms: data.response_time_ms || 0,
        round: data.round,
        actionType: data.action_preview?.action_type || '',
        cards: data.action_preview?.cards || [],
        promptTokens: data.prompt_tokens,
        completionTokens: data.completion_tokens,
        totalTokens: data.total_tokens,
        modelProvider: data.model_provider,
        modelName: data.model_name,
        promptPreview: data.prompt_preview || '',
        rawResponsePreview: data.raw_response_preview || '',
        promptMessages: data.prompt_messages || [],
        rawResponseFull: data.raw_response_full || '',
        reasoning: reasoningContent.value,
        answer: answerContent.value,
      }
      if (data.response_time_ms) {
        lastResponseTimeMs.value[pid] = data.response_time_ms
      }
      // 重置推理和答案内容
      reasoningContent.value = ''
      answerContent.value = ''
    })

    // Legacy handler for backward compatibility
    onMessage('thinking_content', (d: unknown) => {
      const data = d as ThinkingContentPayload
      thinkingContent.value = data.thinking || ''
      currentThinkingRound.value = data.round
      currentThinkingActionType.value = data.action_preview?.action_type || ''
      currentThinkingCards.value = data.action_preview?.cards || []
      currentPromptPreview.value = data.prompt_preview || ''
      currentRawResponsePreview.value = data.raw_response_preview || ''
      currentPromptMessages.value = data.prompt_messages || []
      currentRawResponseFull.value = data.raw_response_full || ''
      const pid = data.player_id || thinkingPlayer.value
      pendingThinking.value[pid] = {
        text: data.thinking || '',
        ms: data.response_time_ms || 0,
        round: data.round,
        actionType: data.action_preview?.action_type || '',
        cards: data.action_preview?.cards || [],
        promptTokens: data.prompt_tokens,
        completionTokens: data.completion_tokens,
        totalTokens: data.total_tokens,
        modelProvider: data.model_provider,
        modelName: data.model_name,
        promptPreview: data.prompt_preview || '',
        rawResponsePreview: data.raw_response_preview || '',
        promptMessages: data.prompt_messages || [],
        rawResponseFull: data.raw_response_full || '',
      }
      if (data.response_time_ms) {
        lastResponseTimeMs.value[pid] = data.response_time_ms
      }
    })

    onMessage('action', (d: unknown) => {
      const data = d as ActionPayload
      const actionPlayerId = data.player_id || ''
      const pending = pendingThinking.value[actionPlayerId]
      lastAction.value = {
        playerId: actionPlayerId,
        actionType: data.action_type || '',
        cards: data.cards || [],
      }
      actionHistory.value.push({
        round: data.round || 0,
        playerId: actionPlayerId,
        actionType: data.action_type || '',
        cards: data.cards || [],
        thinking: pending?.text,
        responseTimeMs: pending?.ms,
      })
      if (pending?.text) {
        thinkingHistory.value.push({
          playerId: actionPlayerId,
          round: pending.round ?? (data.round || 0),
          thinking: pending.text,
          responseTimeMs: pending.ms,
          promptTokens: pending.promptTokens,
          completionTokens: pending.completionTokens,
          totalTokens: pending.totalTokens,
          modelProvider: pending.modelProvider,
          modelName: pending.modelName,
          actionType: pending.actionType,
          cards: pending.cards,
          promptPreview: pending.promptPreview,
          rawResponsePreview: pending.rawResponsePreview,
          promptMessages: pending.promptMessages,
          rawResponseFull: pending.rawResponseFull,
          reasoning: pending.reasoning,
          answer: pending.answer,
        })
      }
      if (typeof pending?.totalTokens === 'number') {
        playerLastRoundTokens.value[actionPlayerId] = pending.totalTokens
        playerTokenTotals.value[actionPlayerId] =
          (playerTokenTotals.value[actionPlayerId] || 0) + pending.totalTokens
      }
      delete pendingThinking.value[actionPlayerId]
      thinkingPlayer.value = ''
      thinkingContent.value = ''
      currentThinkingRound.value = undefined
      currentThinkingActionType.value = ''
      currentThinkingCards.value = []
      currentPromptPreview.value = ''
      currentRawResponsePreview.value = ''
      currentPromptMessages.value = []
      currentRawResponseFull.value = ''
      nextTick(() => {
        if (historyPanel.value) {
          historyPanel.value.scrollTop = historyPanel.value.scrollHeight
        }
      })
    })

    onMessage('state_update', (d: unknown) => {
      const data = d as StateUpdatePayload
      isStarted.value = true
      const normalized = normalizePlayers(
        data.players as Record<string, Record<string, unknown>> | undefined,
      )
      if (normalized) players.value = normalized
      if (data.hands) playerHands.value = data.hands
      currentPlayer.value = data.current_player || ''
      if (data.landlord_cards) landlordCards.value = data.landlord_cards
    })

    onMessage('game_ended', (d: unknown) => {
      const data = d as GameEndedPayload
      isFinished.value = true
      winner.value = {
        id: data.winner_id || '',
        name: data.winner_name || '',
        role: data.winner_role || '',
        totalRounds: data.total_rounds || 0,
      }
    })

    onMessage('game_paused', () => {
      isPaused.value = true
    })

    onMessage('game_resumed', () => {
      isPaused.value = false
    })

    onMessage('error', (d: unknown) => {
      const data = d as ErrorPayload
      const msg = data.message || '对局出错'
      lastError.value = msg
      console.error('Game error:', msg)
    })
  }

  setupMessageHandlers()

  return {
    isConnected,
    connect,
    disconnect,
    playerHands,
    players,
    currentPlayer,
    lastAction,
    thinkingPlayer,
    thinkingContent,
    reasoningContent,
    answerContent,
    currentThinkingRound,
    currentThinkingActionType,
    currentThinkingCards,
    currentPromptPreview,
    currentRawResponsePreview,
    currentPromptMessages,
    currentRawResponseFull,
    pendingThinking,
    lastResponseTimeMs,
    playerTokenTotals,
    playerLastRoundTokens,
    actionHistory,
    thinkingHistory,
    landlordCards,
    playerLastActions,
    isPaused,
    isStarted,
    isFinished,
    lastError,
    winner,
    historyPanel,
  }
}
