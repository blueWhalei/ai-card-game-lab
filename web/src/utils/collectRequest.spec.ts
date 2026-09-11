import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createCollectRequestCache } from './collectRequest'

describe('collection request identity', () => {
  beforeEach(() => {
    const values = new Map<string, string>()
    vi.stubGlobal('window', {
      sessionStorage: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key, value),
        removeItem: (key: string) => values.delete(key),
      },
    })
  })
  afterEach(() => vi.unstubAllGlobals())

  it('reuses the key after an uncertain response and page reload', () => {
    const first = createCollectRequestCache()
    const key = first.get('experiment', 2)
    expect(first.get('experiment', 2)).toBe(key)
    expect(createCollectRequestCache().get('experiment', 2)).toBe(key)
  })

  it('creates a new key only for a changed request or confirmed success', () => {
    const cache = createCollectRequestCache()
    const key = cache.get('experiment', 2)
    expect(cache.get('experiment', 3)).not.toBe(key)
    const changed = cache.get('experiment', 3)
    cache.complete('experiment')
    expect(createCollectRequestCache().get('experiment', 3)).not.toBe(changed)
  })

  it('keeps experiments separate and tolerates disabled storage', () => {
    const cache = createCollectRequestCache()
    expect(cache.get('first', 1)).not.toBe(cache.get('second', 1))
    vi.stubGlobal('window', {
      get sessionStorage() {
        throw new Error('disabled')
      },
    })
    const key = cache.get('disabled', 1)
    expect(cache.get('disabled', 1)).toBe(key)
    cache.complete('disabled')
    expect(cache.get('disabled', 1)).not.toBe(key)
  })
})
