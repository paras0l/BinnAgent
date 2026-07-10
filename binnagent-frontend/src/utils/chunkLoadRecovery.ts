const CHUNK_RELOAD_STORAGE_KEY = 'binnagent:chunk-reload-at'
const CHUNK_RELOAD_COOLDOWN_MS = 10_000

interface ChunkLoadRecoveryOptions {
  eventTarget?: {
    addEventListener: (type: string, listener: EventListener) => void
  }
  storage?: Pick<Storage, 'getItem' | 'setItem'>
  reload?: () => void
  now?: () => number
}

export function installChunkLoadRecovery({
  eventTarget = window,
  storage = window.sessionStorage,
  reload = () => window.location.reload(),
  now = Date.now,
}: ChunkLoadRecoveryOptions = {}) {
  let isReloading = false

  eventTarget.addEventListener('vite:preloadError', (event) => {
    if (isReloading) return

    const currentTime = now()

    try {
      const lastReloadAt = Number(storage.getItem(CHUNK_RELOAD_STORAGE_KEY)) || 0
      if (currentTime - lastReloadAt < CHUNK_RELOAD_COOLDOWN_MS) return
      storage.setItem(CHUNK_RELOAD_STORAGE_KEY, String(currentTime))
    } catch {
      // If session storage is unavailable, let the route error boundary handle it.
      return
    }

    event.preventDefault()
    isReloading = true
    reload()
  })
}
