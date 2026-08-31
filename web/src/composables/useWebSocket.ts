import { ref, onUnmounted, toValue, watch, type MaybeRefOrGetter } from 'vue'
import type { WsMessage } from '@/types/websocket'

const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_DELAY_MS = 3000
const HEARTBEAT_INTERVAL_MS = 30000

type MessageHandler = (data: unknown) => void

export function useWebSocket(gameIdSource: MaybeRefOrGetter<string>) {
  const isConnected = ref(false)
  const lastMessage = ref<WsMessage | null>(null)
  let ws: WebSocket | null = null
  let reconnectAttempts = 0
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null
  let socketGeneration = 0
  const handlers = new Map<string, MessageHandler[]>()

  function currentGameId(): string {
    return String(toValue(gameIdSource) ?? '')
  }

  function onMessage(type: string, handler: MessageHandler): void {
    const list = handlers.get(type) || []
    list.push(handler)
    handlers.set(type, list)
  }

  function startHeartbeat(): void {
    stopHeartbeat()
    heartbeatTimer = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, HEARTBEAT_INTERVAL_MS)
  }

  function stopHeartbeat(): void {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function connect(): void {
    const gameId = currentGameId()
    if (!gameId) return

    const generation = ++socketGeneration
    reconnectAttempts = 0
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    ws = new WebSocket(`${protocol}//${host}/api/v1/games/ws/${gameId}`)

    ws.onopen = () => {
      if (generation !== socketGeneration) return
      isConnected.value = true
      reconnectAttempts = 0
      startHeartbeat()
    }

    ws.onmessage = (event: MessageEvent) => {
      if (generation !== socketGeneration) return
      try {
        const msg = JSON.parse(event.data as string) as WsMessage
        lastMessage.value = msg
        const typeHandlers = handlers.get(msg.type)
        if (typeHandlers) {
          for (const h of typeHandlers) {
            h(msg.data)
          }
        }
        const wildcardHandlers = handlers.get('*')
        if (wildcardHandlers) {
          for (const h of wildcardHandlers) {
            h(msg)
          }
        }
      } catch (error) {
        console.warn('WebSocket message parse failed:', {
          data: event.data,
          error: error instanceof Error ? error.message : String(error),
        })
      }
    }

    ws.onclose = () => {
      if (generation !== socketGeneration) return
      isConnected.value = false
      stopHeartbeat()
      if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++
        reconnectTimer = setTimeout(() => {
          if (generation !== socketGeneration) return
          connect()
        }, RECONNECT_DELAY_MS)
      }
    }

    ws.onerror = () => {
      if (generation !== socketGeneration) return
      ws?.close()
    }
  }

  function disconnect(): void {
    socketGeneration++
    reconnectAttempts = MAX_RECONNECT_ATTEMPTS
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    stopHeartbeat()
    if (ws) {
      try {
        if (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN) {
          ws.close(1000, 'Component unmounted')
        }
      } catch (error) {
        console.warn('WebSocket close failed:', error)
      } finally {
        ws = null
        isConnected.value = false
      }
    } else {
      isConnected.value = false
    }
  }

  function send(message: WsMessage): void {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message))
    }
  }

  watch(
    () => currentGameId(),
    (next, prev) => {
      if (!next || next === prev) return
      disconnect()
      connect()
    },
  )

  onUnmounted(disconnect)

  return { isConnected, lastMessage, connect, disconnect, send, onMessage }
}
