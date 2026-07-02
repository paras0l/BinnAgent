import type { Learner } from '@/types'
import type { EpisodeSummary, LearnerDebugSummary } from './types'

export function selectDebugLearner(
  learner: LearnerDebugSummary,
  onLearnerChange: (learner: Learner | null) => void,
) {
  onLearnerChange({
    id: learner.id,
    nickname: learner.nickname,
    email: learner.email ?? null,
  })
}

export function openEpisodeTrace(
  episode: EpisodeSummary,
  onEpisodeIdChange: (episodeId: string | null) => void,
  navigate: (path: string) => void,
) {
  onEpisodeIdChange(episode.id)
  navigate(`/runtime/episodes/${encodeURIComponent(episode.id)}`)
}
