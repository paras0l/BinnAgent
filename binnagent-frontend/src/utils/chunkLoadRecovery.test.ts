import { describe, expect, it, vi } from 'vitest'
import { installChunkLoadRecovery } from './chunkLoadRecovery'

function createHarness(lastReloadAt: string | null = null) {
  let listener: EventListener | undefined
  let storedReloadAt = lastReloadAt
  const reload = vi.fn()

  installChunkLoadRecovery({
    eventTarget: {
      addEventListener: (_type, nextListener) => {
        listener = nextListener
      },
    },
    storage: {
      getItem: vi.fn(() => storedReloadAt),
      setItem: vi.fn((_key, value) => {
        storedReloadAt = value
      }),
    },
    reload,
    now: () => 20_000,
  })

  return {
    dispatch: () => {
      const event = new Event('vite:preloadError', { cancelable: true })
      listener?.(event)
      return event
    },
    reload,
    storedReloadAt: () => storedReloadAt,
  }
}

describe('installChunkLoadRecovery', () => {
  it('reloads once and prevents Vite from surfacing a stale chunk error', () => {
    const harness = createHarness()

    const firstEvent = harness.dispatch()
    const secondEvent = harness.dispatch()

    expect(firstEvent.defaultPrevented).toBe(true)
    expect(secondEvent.defaultPrevented).toBe(false)
    expect(harness.reload).toHaveBeenCalledOnce()
    expect(harness.storedReloadAt()).toBe('20000')
  })

  it('does not enter a reload loop during the cooldown window', () => {
    const harness = createHarness('15000')

    const event = harness.dispatch()

    expect(event.defaultPrevented).toBe(false)
    expect(harness.reload).not.toHaveBeenCalled()
  })

  it('retries recovery after the cooldown window expires', () => {
    const harness = createHarness('5000')

    const event = harness.dispatch()

    expect(event.defaultPrevented).toBe(true)
    expect(harness.reload).toHaveBeenCalledOnce()
  })
})
