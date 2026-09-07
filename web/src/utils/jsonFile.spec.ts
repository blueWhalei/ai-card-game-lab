import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { pickJsonFile } from './jsonFile'

beforeEach(() => {
  vi.stubGlobal('document', {
    createElement: vi.fn(),
  })
  vi.stubGlobal('window', {
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    setTimeout: globalThis.setTimeout.bind(globalThis),
    dispatchEvent: vi.fn(),
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('pickJsonFile', () => {
  it('resolves null when the system dialog is cancelled', async () => {
    vi.useFakeTimers()

    const focusListeners: Array<() => void> = []
    const click = vi.fn()
    vi.mocked(document.createElement).mockReturnValue({
      type: '',
      accept: '',
      files: null,
      addEventListener: vi.fn(),
      click,
    } as unknown as HTMLInputElement)

    vi.mocked(window.addEventListener).mockImplementation((type, listener) => {
      if (type === 'focus' && typeof listener === 'function') {
        focusListeners.push(listener as () => void)
      }
    })

    const pending = pickJsonFile()
    expect(click).toHaveBeenCalledOnce()
    expect(focusListeners).toHaveLength(1)

    focusListeners[0]!()
    await vi.runAllTimersAsync()

    await expect(pending).resolves.toBeNull()
  })

  it('parses the chosen file', async () => {
    const listeners = new Map<string, EventListener>()
    const file = {
      text: async () => '{"ok":true}',
    }

    vi.mocked(document.createElement).mockReturnValue({
      type: '',
      accept: '',
      get files() {
        return { 0: file, length: 1, item: () => file }
      },
      addEventListener: (type: string, listener: EventListener) => {
        listeners.set(type, listener)
      },
      click: () => {
        listeners.get('change')?.(new Event('change'))
      },
    } as unknown as HTMLInputElement)

    await expect(pickJsonFile()).resolves.toEqual({ ok: true })
  })
})
