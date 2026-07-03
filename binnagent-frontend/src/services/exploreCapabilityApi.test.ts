import { describe, expect, it } from 'vitest'
import {
  FEATURE_CAPABILITY_MAP,
  exploreCapabilitiesUrl,
  exploreCapabilityEventUrl,
  exploreCapabilityStartUrl,
  learnerExploreRecommendationsUrl,
} from './exploreCapabilityApi'

describe('exploreCapabilityApi', () => {
  it('keeps the feature to capability map populated', () => {
    expect(Object.keys(FEATURE_CAPABILITY_MAP).length).toBeGreaterThan(0)
    expect(FEATURE_CAPABILITY_MAP['grammar-explain']).toBe('grammar-explain')
  })

  it('builds capability endpoints and never the removed skills endpoint', () => {
    const urls = [
      exploreCapabilitiesUrl(),
      exploreCapabilityStartUrl('grammar-explain'),
      learnerExploreRecommendationsUrl('learner-1'),
      exploreCapabilityEventUrl('learner-1', 'grammar-explain'),
    ]

    expect(urls).toContain('/api/explore/capabilities/grammar-explain/start')
    expect(urls).toContain('/api/learners/learner-1/explore/recommendations')
    expect(urls).toContain('/api/learners/learner-1/explore/capabilities/grammar-explain/events')
    expect(urls.join('\n')).not.toContain('/api/explore/skills')
  })
})
