import { renderToString } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { openEpisodeTrace } from './actions'
import { RecentEpisodesList } from './RecentEpisodesPage'
import type { EpisodeSummary } from './types'

const episode: EpisodeSummary = {
  id: 'episode-1',
  learner_id: 'learner-1',
  learner_nickname: 'Alice',
  source: 'daily_lesson',
  entrypoint: 'daily.start',
  status: 'completed',
  task_type: 'knowledge_practice',
  task_objective: 'Practice present perfect',
  target_type: 'curriculum_node',
  target_id: 'node-1',
  started_at: '2026-07-02T10:00:00Z',
  completed_at: '2026-07-02T10:05:00Z',
  created_at: '2026-07-02T10:00:00Z',
  event_count: 7,
  tool_call_count: 2,
  verification_status: 'passed',
  failure_type: null,
  error_message: null,
}

describe('RecentEpisodesPage', () => {
  it('renders episode list mock data', () => {
    const html = renderToString(
      <RecentEpisodesList episodes={[episode]} onOpenTrace={() => undefined} />
    ).replaceAll('<!-- -->', '')

    expect(html).toContain('daily_lesson')
    expect(html).toContain('knowledge_practice')
    expect(html).toContain('Practice present perfect')
    expect(html).toContain('events 7')
    expect(html).toContain('tools 2')
    expect(html).toContain('passed')
  })

  it('openEpisodeTrace updates episode context and navigates', () => {
    const onEpisodeIdChange = vi.fn()
    const navigate = vi.fn()

    openEpisodeTrace(episode, onEpisodeIdChange, navigate)

    expect(onEpisodeIdChange).toHaveBeenCalledWith('episode-1')
    expect(navigate).toHaveBeenCalledWith('/runtime/episodes/episode-1')
  })
})
