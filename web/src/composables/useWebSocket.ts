import { ref, onUnmounted } from 'vue'
import type { WsMessage } from '@/types/websocket'

const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_DELAY_MS = 3000
const HEARTBEAT_INTERVAL_MS = 30000

type MessageHandler = (data: unknown) => void

export function useWebSocket(gameId: string) {
  const isConnected = ref(false)
  const lastMessage = ref<WsMessage | null>(null)
  let ws: WebSocket | null = null
  let reconnectAttempts = 0
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null
  const handlers = new Map<string, MessageHandler[]>()

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
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    ws = new WebSocket(`${protocol}//${host}/api/v1/games/ws/${gameId}`)

    ws.onopen = () => {
      isConnected.value = true
      reconnectAttempts = 0
      startHeartbeat()
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string) as WsMessage
        lastMessage.value = msg
        // Dispatch to typed handlers
        const typeHandlers = handlers.get(msg.type)
        if (typeHandlers) {
          for (const h of typeHandlers) {
            h(msg.data)
          }
        }
        // Also dispatch to wildcard handlers
        const wildcardHandlers = handlers.get('*')
        if (wildcardHandlers) {
          for (const h of wildcardHandlers) {
            h(msg)
          }
        }
      } catch (error) {
        // Log malformed messages for debugging
        console.warn('WebSocket message parse failed:', {
          data: event.data,
          error: error instanceof Error ? error.message : String(error),
        })
      }
    }

    ws.onclose = () => {
      isConnected.value = false
      stopHeartbeat()
      // Auto-reconnect
      if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++
        reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS)
      }
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function disconnect(): void {
    reconnectAttempts = MAX_RECONNECT_ATTEMPTS // prevent reconnect
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    stopHeartbeat()
    // Close WebSocket with proper cleanup
    if (ws) {
      try {
        // Only close if still connecting or open
        if (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN) {
          ws.close(1000, 'Component unmounted') // 1000 = Normal Closure
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

  onUnmounted(disconnect)

  return { isConnected, lastMessage, connect, disconnect, send, onMessage }
}
