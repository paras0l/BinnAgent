export interface Learner {
  id: string
  nickname: string
  email?: string | null
}

export type AppTab =
  | 'chat'
  | 'explore'
  | 'dashboard'
  | 'pronunciation'
  | 'grammar'

export type KnowledgeType =
  | 'vocabulary'
  | 'grammar'
  | 'phrase'
  | 'sentence_pattern'

export interface CurriculumNode {
  id: string
  parent_id?: string | null
  node_type: 'textbook' | 'unit' | 'section' | 'lesson'
  title: string
  subtitle?: string | null
  ordinal: number
  status: 'locked' | 'available' | 'in_progress' | 'completed'
  progress: number
  estimated_minutes?: number | null
}

export interface KnowledgePointSummary {
  id: string
  title: string
  type: KnowledgeType
  summary: string
  source_page: string
  mastery: number
}

export interface DailyLessonPart {
  id: string
  title: string
  estimated_minutes: number
  completed: boolean
}

export interface KnowledgeBaseOverview {
  source: {
    id: string
    title: string
    publisher: string
    edition: string
    status: 'draft' | 'processing' | 'review_required' | 'published' | 'failed'
    unit_count: number
    knowledge_count: number
    progress: number
  }
  curriculum: CurriculumNode[]
  current_node_id: string
  current_unit: {
    id: string
    title: string
    subtitle: string
    estimated_minutes: number
  }
  daily_lesson: {
    id: string
    title: string
    estimated_minutes: number
    parts: DailyLessonPart[]
  }
  knowledge_points: KnowledgePointSummary[]
  path: Array<{
    id: string
    ordinal: number
    title: string
    subtitle: string
    status: 'current' | 'next' | 'locked' | 'completed'
    estimated_minutes?: number | null
  }>
  recommendation_reason: string
}

export interface KnowledgeUploadResult {
  source_id: string
  filename: string
  status: 'uploaded' | 'processing'
  message: string
}

export interface KnowledgeLessonSession {
  session_id: string
  title: string
  parts: DailyLessonPart[]
  knowledge_points: Array<{
    id: string
    title: string
    summary: string
    type: KnowledgeType
  }>
  vocabulary_enrollment?: {
    total: number
    newly_added: number
    source_linked: number
    already_known: number
  }
}

export interface KnowledgeAttemptResult {
  knowledge_point_id: string
  status: string
  mastery_score: number
  exposure_count: number
  next_review_at: string
}

export interface KnowledgeLessonCompleteResult {
  session_id: string
  completed_node_id: string
  next_node_id?: string | null
  next_unit_title?: string | null
  all_completed: boolean
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

export interface ChatSkillEvent {
  name: string
  skill_id?: string | null
  skill_name?: string | null
  status: 'started' | 'completed' | 'skipped' | 'failed'
  saved_count?: number
  message?: string
}

export interface ConversationThread {
  thread_id: string
  title: string
  last_message?: string | null
  message_count: number
  created_at: string
  updated_at: string
  skill_id?: string | null
  skill_name?: string | null
}

export interface MemorySummary {
  learner: Learner
  stats: {
    conversation_count: number
    message_count: number
    total_vocab: number
    due_reviews: number
    mastered_vocab: number
  }
  latest_thread_id?: string | null
  latest_thread_title?: string | null
  latest_thread_summary?: string | null
  error_patterns: Array<{
    id: string
    name: string
    count: number
    severity?: string | null
  }>
  recent_sessions: Array<{
    id: string
    summary?: string | null
    active_skill?: string | null
    completed_at?: string | null
  }>
}

export interface DashboardSummary {
  stats: {
    today_reviews: number
    today_completed_reviews: number
    streak_days: number
    accuracy: number
    total_vocab: number
  }
  review_items: Array<{
    id: string
    word: string
    phonetic?: string | null
    definition?: string | null
    example?: string | null
    confidence: number
  }>
  error_patterns: Array<{
    id: string
    name: string
    count: number
    example?: string | null
    severity?: string | null
  }>
  today_goal: {
    label: string
    completed: number
    total: number
  }
  weekly_goal: {
    label: string
    completed: number
    total: number
  }
  daily_activity: Array<{
    date: string
    count: number
  }>
}

export interface VocabularyListItem {
  id: string
  word: string
  phonetic?: string | null
  status: string
  confidence: number
  review_count: number
  meaning?: string | null
  last_reviewed_at?: string | null
  next_review_at?: string | null
  sources: Array<{
    type: string
    label: string
    context: Record<string, unknown>
  }>
}

export interface ExplorePreference {
  id: string
  learner_id: string
  feature_id: string
  is_favorite: boolean
  priority: number
  last_used_at?: string | null
  created_at: string
  updated_at: string
}

export interface LearningProgressItem {
  id: string
  learner_id: string
  skill: 'grammar' | 'pronunciation' | string
  item_id: string
  title: string
  status: 'opened' | 'learned' | string
  is_favorite: boolean
  opened_count: number
  last_opened_at?: string | null
  learned_at?: string | null
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface GrammarHtmlCacheResponse {
  topic_id: string
  prompt_hash: string
  prompt_version: string
  cached: boolean
  html?: string | null
  source?: string | null
  stored_at?: string | null
}
