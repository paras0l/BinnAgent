import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DEBUG_TOKEN_STORAGE_KEY, debugFetch, saveDebugToken } from './debugClient'

describe('debugClient', () => {
  beforeEach(() => {
    const store = new Map<string, string>()
    vi.stubGlobal('localStorage', {
      getItem: vi.fn((key: string) => store.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => store.set(key, value)),
      removeItem: vi.fn((key: string) => store.delete(key)),
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('saveDebugToken writes BINNAGENT_DEBUG_TOKEN', () => {
    saveDebugToken(' dev ')

    expect(globalThis.localStorage.getItem(DEBUG_TOKEN_STORAGE_KEY)).toBe('dev')
  })

  it('debugFetch sends X-Debug-Token', async () => {
    const fetchMock = vi.fn(async (...args: [RequestInfo | URL, RequestInit?]) => {
      void args
      return new Response('{}', { status: 200 })
    })
    vi.stubGlobal('fetch', fetchMock)
    saveDebugToken('dev')

    await debugFetch('/api/debug/rag/search?query=test')

    const init = fetchMock.mock.calls[0][1]
    expect(init).toBeDefined()
    const headers = (init as RequestInit).headers as Headers
    expect(headers.get('X-Debug-Token')).toBe('dev')
  })
})
