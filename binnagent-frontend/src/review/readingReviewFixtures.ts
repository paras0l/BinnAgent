import type { ReadingMaterialHistoryItem } from '@/data/readingWorkshop'
import type { Learner, LearnerProfile } from '@/types'

export const READING_REVIEW_LEARNER: Learner = {
  id: 'sites-reading-review',
  nickname: '团队验收员',
  email: 'review@binnagent.local',
}

export const READING_REVIEW_PROFILE: LearnerProfile = {
  learner_id: READING_REVIEW_LEARNER.id,
  learning_track: 'reading',
  target_exam: 'CET-4',
  current_level: 'b1',
  daily_time_budget_minutes: 20,
  interest_topics: ['城市与自然', '学习方法'],
}

export const READING_REVIEW_MATERIAL: ReadingMaterialHistoryItem = {
  id: 'review-material-city-trees',
  learner_id: READING_REVIEW_LEARNER.id,
  curriculum_node_id: null,
  title: 'Why City Trees Matter',
  text: 'City trees do more than make streets look attractive. They lower summer temperatures by giving shade, which can reduce the need for air conditioning. Their roots also slow rainwater, so city drains are less likely to overflow during storms. However, a healthy urban forest requires long-term care because young trees need water, space, and protection. When residents understand these benefits, they are more willing to support planting projects that improve everyday life.',
  level: 'general',
  goal: 'mixed',
  material_type: 'passage',
  word_count: 76,
  sentence_count: 5,
  source: 'team_review_fixture',
  generation_context: {
    source_title: 'BinnAgent 团队验收示例',
    unit_title: '城市与自然',
    grammar_focus: ['定语从句', '连接词与句间逻辑'],
    vocabulary_used: ['shade', 'overflow', 'urban forest'],
    level_rationale: '适合 B1 学习者验证主旨、结构和逐句分析流程。',
    confidence: 1,
  },
  created_at: '2026-07-14T12:00:00.000Z',
  updated_at: '2026-07-14T12:00:00.000Z',
}
