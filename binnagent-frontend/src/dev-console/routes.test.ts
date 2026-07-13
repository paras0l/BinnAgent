import { describe, expect, it } from 'vitest'
import { devConsoleRoutes, findDevConsoleRoute } from './routes'

describe('devConsoleRoutes', () => {
  it('exposes internal debug pages in the Dev Console only', () => {
    expect(devConsoleRoutes.map((route) => route.id)).toEqual(
      expect.arrayContaining([
        'memory',
        'model-provider',
        'episodes',
        'learners',
        'textbooks',
        'tools',
        'sandbox',
        'tool-call-records',
        'evidence',
        'rag',
        'prompt',
        'verification',
        'simulation',
      ])
    )
    expect(devConsoleRoutes.map((route) => route.label)).toEqual(
      expect.arrayContaining([
        'Memory Debug',
        'Model Provider',
        'Learners',
        'Textbook Parsing',
        'Recent Episodes',
        'Tool Registry',
        'Sandbox Permissions',
        'Tool Call Records',
        'Evidence Debug',
        'RAG Debug',
        'Prompt Debug',
        'VerificationReport',
        'Simulation Report',
      ])
    )
  })

  it('routes runtime episode URLs to Episode Debug', () => {
    expect(findDevConsoleRoute('/runtime/episodes/episode-1').id).toBe('graph-runs')
  })

  it('keeps Tool Registry and Tool Call Records as separate routes', () => {
    expect(findDevConsoleRoute('/dev/tools').id).toBe('tools')
    expect(findDevConsoleRoute('/dev/sandbox').id).toBe('sandbox')
    expect(findDevConsoleRoute('/dev/tool-calls').id).toBe('tool-call-records')
  })

  it('routes learners and recent episodes pages', () => {
    expect(findDevConsoleRoute('/dev/learners').id).toBe('learners')
    expect(findDevConsoleRoute('/dev/model-provider').id).toBe('model-provider')
    expect(findDevConsoleRoute('/dev/episodes').id).toBe('episodes')
  })
})
