import { describe, expect, it } from 'vitest'
import { devConsoleRoutes, findDevConsoleRoute } from './routes'

describe('devConsoleRoutes', () => {
  it('exposes internal debug pages in the Dev Console only', () => {
    expect(devConsoleRoutes.map((route) => route.id)).toEqual(
      expect.arrayContaining(['memory', 'episode', 'tools', 'evidence', 'rag', 'prompt'])
    )
    expect(devConsoleRoutes.map((route) => route.label)).toEqual(
      expect.arrayContaining(['Memory Debug', 'Episode Debug'])
    )
  })

  it('routes runtime episode URLs to Episode Debug', () => {
    expect(findDevConsoleRoute('/runtime/episodes/episode-1').id).toBe('episode')
  })
})
