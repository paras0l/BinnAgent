export interface LearnerDebugSummary {
  id: string
  nickname: string
  email?: string | null
  created_at?: string | null
  updated_at?: string | null
  profile?: {
    target_exam?: string | null
    current_level?: string | null
    daily_time_budget_minutes?: number | null
  } | null
  counts: {
    episode_count: number
    memory_event_count: number
    exercise_attempt_count: number
    vocabulary_count: number
  }
}

export interface EpisodeSummary {
  id: string
  learner_id: string
  learner_nickname?: string | null
  source: string
  entrypoint: string
  status: string
  task_type?: string | null
  task_objective?: string | null
  target_type?: string | null
  target_id?: string | null
  started_at?: string | null
  completed_at?: string | null
  created_at?: string | null
  event_count: number
  tool_call_count: number
  verification_status?: string | null
  checkpoint_id?: string | null
  checkpoint_status?: string | null
  resume_from?: string | null
  answer_required?: boolean
  failure_type?: string | null
  error_message?: string | null
}
