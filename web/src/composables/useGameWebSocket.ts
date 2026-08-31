import { ref, computed, nextTick, toValue, watch, type MaybeRefOrGetter } from 'vue'
import { tt } from '@/i18n'
import { useWebSocket } from '@/composables/useWebSocket'
import { coerceObserverSnapshot, type ObserverSnapshot } from '@/types/observer'
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

export function useGameWebSocket(gameIdSource: MaybeRefOrGetter<string>) {
  const { isConnected, connect, disconnect, onMessage } = useWebSocket(gameIdSource)

  const snapshot = ref<ObserverSnapshot | null>(null)
  const playerHands = ref<Record<string, string[]>>({})
  const players = ref<Record<string, PlayerInfo>>({})
  const currentPlayer = ref('')
  const lastAction = ref<{ playerId: string; actionType: string; cards: string[] } | null>(null)
  const thinkingPlayer = ref('')
  const thinkingContent = ref('')
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

  const playerLastActions = computed<Record<string, { actionType: string; cards: string[] }>>(
    () => {
      const map: Record<string, { actionType: string; cards: string[] }> = {}
      for (const entry of actionHistory.value) {
        map[entry.playerId] = { actionType: entry.actionType, cards: entry.cards }
      }
      return map
    },
  )

  function applySnapshot(raw: unknown, gameTypeHint = 'doudizhu'): void {
    const next = coerceObserverSnapshot(raw, gameTypeHint)
    if (!next) return
    snapshot.value = next
    currentPlayer.value = next.current_player_id || ''
    const hands: Record<string, string[]> = {}
    const info: Record<string, PlayerInfo> = {}
    for (const p of next.players) {
      info[p.id] = { cardsLeft: p.hand_count, role: p.role || 'unknown' }
      if (p.hand_cards) hands[p.id] = p.hand_cards
    }
    players.value = info
    if (Object.keys(hands).length > 0) playerHands.value = hands
    const landlord = next.table?.slots?.find((s) => s.key === 'landlord')
    if (landlord?.cards) landlordCards.value = landlord.cards
  }

  function setupMessageHandlers(): void {
    onMessage('game_started', (d: unknown) => {
      isStarted.value = true
      applySnapshot(d as GameStartedPayload)
    })

    onMessage('thinking', (d: unknown) => {
      const data = d as ThinkingPayload
      thinkingPlayer.value = data.player_id || ''
      thinkingContent.value = ''
      reasoningContent.value = ''
      answerContent.value = ''
      currentThinkingRound.value = undefined
      currentThinkingActionType.value = ''
      currentThinkingCards.value = []
      currentPromptPreview.value = ''
      currentRawResponsePreview.value = ''
      currentPromptMessages.value = []
      currentRawResponseFull.value = ''
    })

    onMessage('thinking_chunk', (d: unknown) => {
      const data = d as ThinkingChunkPayload
      if (data.chunk_type === 'reasoning') {
        reasoningContent.value += data.chunk
      } else {
        answerContent.value += data.chunk
      }
      thinkingContent.value += data.chunk
    })

    onMessage('thinking_complete', (d: unknown) => {
      const data = d as ThinkingCompletePayload
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
      reasoningContent.value = ''
      answerContent.value = ''
    })

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
      isStarted.value = true
      applySnapshot(d as StateUpdatePayload)
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
      const msg = data.message || tt('game.errorFallback')
      lastError.value = msg
      console.error('Game error:', msg)
    })
  }

  function resetBoardState(): void {
    snapshot.value = null
    playerHands.value = {}
    players.value = {}
    currentPlayer.value = ''
    lastAction.value = null
    thinkingPlayer.value = ''
    thinkingContent.value = ''
    reasoningContent.value = ''
    answerContent.value = ''
    currentThinkingRound.value = undefined
    currentThinkingActionType.value = ''
    currentThinkingCards.value = []
    currentPromptPreview.value = ''
    currentRawResponsePreview.value = ''
    currentPromptMessages.value = []
    currentRawResponseFull.value = ''
    pendingThinking.value = {}
    lastResponseTimeMs.value = {}
    playerTokenTotals.value = {}
    playerLastRoundTokens.value = {}
    actionHistory.value = []
    thinkingHistory.value = []
    landlordCards.value = []
    isPaused.value = false
    isStarted.value = false
    isFinished.value = false
    lastError.value = ''
    winner.value = null
  }

  setupMessageHandlers()

  watch(
    () => String(toValue(gameIdSource) ?? ''),
    (next, prev) => {
      if (!next || next === prev) return
      resetBoardState()
    },
  )

  return {
    isConnected,
    connect,
    disconnect,
    snapshot,
    applySnapshot,
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
