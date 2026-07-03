export const FEATURE_CAPABILITY_MAP: Record<string, string> = {
  'daily-lesson': 'daily-lesson',
  'vocab-review': 'vocab-review',
  'vocabulary-detail': 'vocabulary-detail',
  'word-roots-affixes': 'word-roots-affixes',
  'add-vocabulary': 'add-vocabulary',
  'vocabulary-manager': 'vocabulary-manager',
  'cet-reading': 'cet-reading',
  'reading-intensive-extensive': 'reading-intensive-extensive',
  'essay-review': 'essay-review',
  'writing-phrasebook': 'writing-phrasebook',
  'grammar-explain': 'grammar-explain',
  'translation-practice': 'translation-practice',
  'speaking-roleplay': 'speaking-roleplay',
  'phonetic-association': 'phonetic-association',
  shadowing: 'shadowing',
}

export function exploreCapabilitiesUrl() {
  return '/api/explore/capabilities'
}

export function exploreCapabilityStartUrl(capabilityId: string) {
  return `/api/explore/capabilities/${capabilityId}/start`
}

export function learnerExploreRecommendationsUrl(learnerId: string) {
  return `/api/learners/${learnerId}/explore/recommendations`
}

export function exploreCapabilityEventUrl(learnerId: string, capabilityId: string) {
  return `/api/learners/${learnerId}/explore/capabilities/${capabilityId}/events`
}
