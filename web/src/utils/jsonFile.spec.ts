import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { downloadJson, pickJsonFile } from './jsonFile'
import { invoke, isTauri } from '@tauri-apps/api/core'
import { toast } from '@/components/ui/toast'

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn(), isTauri: vi.fn() }))
vi.mock('@/components/ui/toast', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), dismiss: vi.fn() },
}))
vi.mock('@/i18n', () => ({ tt: (key: string) => key }))

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(isTauri).mockReturnValue(true)
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

describe('downloadJson', () => {
  it('waits for native disk confirmation before reporting success', async () => {
    let complete!: (saved: string | null) => void
    vi.mocked(invoke).mockImplementation(
      () =>
        new Promise((resolve) => {
          complete = resolve as typeof complete
        }),
    )
    const pending = downloadJson('研究.json', { notes: '中文', revision: 2 })
    expect(invoke).toHaveBeenCalledWith('save_export', {
      filename: '研究.json',
      format: 'json',
      content: JSON.stringify({ notes: '中文', revision: 2 }, null, 2),
    })
    expect(toast.success).not.toHaveBeenCalled()
    expect(document.createElement).not.toHaveBeenCalled()
    complete('receipt-1')
    expect(await pending).toBe(true)
    expect(toast.success).toHaveBeenCalledWith('common.exportSaved', 0, {
      label: 'common.exportReveal',
      run: expect.any(Function),
      errorMessage: 'common.exportRevealFailed',
    })
    vi.mocked(invoke).mockResolvedValue(undefined)
    await vi.mocked(toast.success).mock.calls[0]![2]!.run()
    expect(invoke).toHaveBeenLastCalledWith('reveal_saved_export', { id: 'receipt-1' })
  })

  it('treats native cancellation as neither success nor error', async () => {
    vi.mocked(invoke).mockResolvedValue(null)
    expect(await downloadJson('report.json', {})).toBe(false)
    expect(toast.success).not.toHaveBeenCalled()
    expect(toast.error).not.toHaveBeenCalled()
    expect(document.createElement).not.toHaveBeenCalled()
  })

  it('replaces the previous saved-file action only after a new successful save', async () => {
    vi.mocked(toast.success).mockReturnValueOnce(10).mockReturnValueOnce(11)
    vi.mocked(invoke)
      .mockResolvedValueOnce('first')
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce('second')
    await downloadJson('first.json', {})
    vi.mocked(toast.dismiss).mockClear()
    await downloadJson('cancelled.json', {})
    expect(toast.dismiss).not.toHaveBeenCalled()
    await downloadJson('second.json', {})
    expect(toast.dismiss).toHaveBeenCalledWith(10)
    const latest = vi.mocked(toast.success).mock.calls[1]![2]!
    vi.mocked(invoke).mockResolvedValue(undefined)
    await latest.run()
    expect(invoke).toHaveBeenLastCalledWith('reveal_saved_export', { id: 'second' })
  })

  it('reports native errors without switching to a browser download', async () => {
    vi.mocked(invoke).mockRejectedValue(new Error('write failed'))
    expect(await downloadJson('report.json', {})).toBe(false)
    expect(toast.error).toHaveBeenCalledWith('common.exportSaveFailed')
    expect(toast.success).not.toHaveBeenCalled()
    expect(document.createElement).not.toHaveBeenCalled()
  })

  it('rejects serialization errors and payloads exceeding the UTF-8 limit before IPC', async () => {
    const circular: Record<string, unknown> = {}
    circular.self = circular
    expect(await downloadJson('report.json', circular)).toBe(false)
    expect(await downloadJson('report.json', undefined)).toBe(false)
    expect(await downloadJson('report.json', '中'.repeat(12 * 1024 * 1024))).toBe(false)
    expect(invoke).not.toHaveBeenCalled()
    expect(toast.error).toHaveBeenLastCalledWith('common.exportTooLarge')
  })

  it('hands the same JSON to a browser without claiming disk persistence', async () => {
    vi.mocked(isTauri).mockReturnValue(false)
    const anchor = { href: '', download: '', click: vi.fn() }
    vi.mocked(document.createElement).mockReturnValue(anchor as unknown as HTMLAnchorElement)
    const create = vi.fn().mockReturnValue('blob:export')
    const revoke = vi.fn()
    vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: revoke })
    expect(await downloadJson('report.json', { notes: '中文' })).toBe(true)
    expect(await (create.mock.calls[0]![0] as Blob).text()).toBe(
      JSON.stringify({ notes: '中文' }, null, 2),
    )
    expect(anchor.download).toBe('report.json')
    expect(anchor.click).toHaveBeenCalledOnce()
    expect(revoke).toHaveBeenCalledWith('blob:export')
    expect(invoke).not.toHaveBeenCalled()
    expect(toast.success).not.toHaveBeenCalled()
    expect(toast.info).toHaveBeenCalledWith('common.exportDownloadStarted')
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
