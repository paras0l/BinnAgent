import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

describe('reading review API mock', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.stubGlobal('window', {
      fetch: vi.fn(),
      location: { origin: 'https://review.example.test' },
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('serves the seeded reading material and coach response', async () => {
    const { installReadingReviewApiMock } = await import('./readingReviewApiMock')
    installReadingReviewApiMock()

    const materialsResponse = await window.fetch(
      '/api/learners/sites-reading-review/reading-workshop/materials',
    )
    const materials = await materialsResponse.json() as Array<{ id: string; title: string }>
    expect(materialsResponse.status).toBe(200)
    expect(materials[0]).toMatchObject({
      id: 'review-material-city-trees',
      title: 'Why City Trees Matter',
    })

    const coachResponse = await window.fetch('/api/chat/send', {
      method: 'POST',
      body: JSON.stringify({ message: '这一段的转折在哪里？' }),
    })
    const coach = await coachResponse.json() as { reply: string; thread_id: string }
    expect(coach.thread_id).toBe('review-reading-coach-thread')
    expect(coach.reply).toContain('However')
  })

  it('records a review completion without calling a remote backend', async () => {
    const { installReadingReviewApiMock } = await import('./readingReviewApiMock')
    installReadingReviewApiMock()

    const response = await window.fetch(
      '/api/learners/sites-reading-review/reading-workshop/materials/review-material-city-trees/complete',
      { method: 'POST', body: JSON.stringify({ client_attempt_id: 'review-attempt-client' }) },
    )
    const result = await response.json() as {
      material_id: string
      attempt_id: string
      reading_value: number
    }

    expect(response.status).toBe(200)
    expect(result.material_id).toBe('review-material-city-trees')
    expect(result.attempt_id).toMatch(/^review-attempt-/)
    expect(result.reading_value).toBe(18)
  })
})
