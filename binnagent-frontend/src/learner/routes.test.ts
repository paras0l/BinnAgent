import { describe, expect, it } from 'vitest'
import { learnerRoutes } from './routes'

describe('learnerRoutes', () => {
  it('only exposes learner-facing routes', () => {
    const routeText = learnerRoutes
      .flatMap((route) => [route.id, route.label, route.path])
      .join(' ')
      .toLowerCase()

    expect(routeText).not.toMatch(/learners|episodes|memory|runtime|debug|prompt|tool|evidence|trace/)
  })

  it('does not include MemoryCenterPage access', () => {
    expect(learnerRoutes.map((route) => route.id)).not.toContain('memory')
    expect(learnerRoutes.some((route) => route.path.includes('memory'))).toBe(false)
  })
})
