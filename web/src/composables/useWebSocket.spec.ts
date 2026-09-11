import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, ref, nextTick } from 'vue'
import { useWebSocket } from './useWebSocket'

vi.mock('vue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue')>()),
  onUnmounted: vi.fn(),
}))

class FakeWebSocket {
  static OPEN = 1
  static CONNECTING = 0
  static instances: FakeWebSocket[] = []
  readyState = 0
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  send = vi.fn()
  close = vi.fn(() => { this.readyState = 3; this.onclose?.() })
  constructor(public url: string) { FakeWebSocket.instances.push(this) }
}

function latest(): FakeWebSocket {
  return FakeWebSocket.instances[FakeWebSocket.instances.length - 1]!
}

describe('WebSocket connection lifecycle', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
    vi.stubGlobal('window', { location: { protocol: 'http:', host: 'localhost' } })
  })
  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('stops after five retries and allows an explicit fresh connection', () => {
    const socket = useWebSocket('game')
    socket.connect()
    for (let i = 0; i < 8; i++) {
      latest().close()
      vi.advanceTimersByTime(3000)
    }
    expect(FakeWebSocket.instances).toHaveLength(6)
    socket.connect()
    latest().close()
    vi.advanceTimersByTime(3000)
    expect(FakeWebSocket.instances).toHaveLength(8)
    socket.disconnect()
  })

  it('resets the failure budget after a successful connection', () => {
    const socket = useWebSocket('game')
    socket.connect()
    for (let i = 0; i < 4; i++) {
      latest().close()
      vi.advanceTimersByTime(3000)
    }
    latest().readyState = FakeWebSocket.OPEN
    latest().onopen?.()
    expect(socket.isConnected.value).toBe(true)
    for (let i = 0; i < 6; i++) {
      latest().close()
      vi.advanceTimersByTime(3000)
    }
    expect(FakeWebSocket.instances).toHaveLength(10)
    socket.disconnect()
  })

  it('cancels pending retries and ignores callbacks from an obsolete socket', () => {
    const socket = useWebSocket('game')
    socket.connect()
    const old = latest()
    old.close()
    socket.disconnect()
    old.onopen?.()
    vi.advanceTimersByTime(6000)
    expect(socket.isConnected.value).toBe(false)
    expect(FakeWebSocket.instances).toHaveLength(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('switches games and disconnects when the game id becomes empty', async () => {
    const scope = effectScope()
    const game = ref('first')
    const socket = scope.run(() => useWebSocket(game))!
    socket.connect()
    const old = latest()
    game.value = 'second'
    await nextTick()
    expect(old.close).toHaveBeenCalled()
    expect(latest().url).toContain('/second')
    game.value = ''
    await nextTick()
    expect(latest().close).toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
    scope.stop()
  })
})
