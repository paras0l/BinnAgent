export interface Learner {
  id: string
  nickname: string
  email?: string | null
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

export interface ConversationThread {
  thread_id: string
  title: string
  last_message?: string | null
  message_count: number
  created_at: string
  updated_at: string
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
}
