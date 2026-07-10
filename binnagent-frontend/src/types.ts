import type { ExerciseItem } from './types/exercises'

export interface Learner {
  id: string
  nickname: string
  email?: string | null
}

export interface LearnerProfile {
  learner_id: string
  target_exam?: string | null
  target_score?: number | null
  exam_date?: string | null
  current_level?: string | null
  daily_time_budget_minutes?: number | null
}

export type AppTab =
  | 'chat'
  | 'explore'
  | 'dashboard'
  | 'pronunciation'
  | 'grammar'

export type PronunciationWorkspace =
  | 'phonetic'
  | 'shadowing'
  | 'minimal-pairs'
  | 'records'

export type KnowledgeType =
  | 'vocabulary'
  | 'grammar'
  | 'phrase'
  | 'sentence_pattern'
  | 'pronunciation'
  | 'text_note'

export type WordPartKind = 'prefix' | 'root' | 'suffix'

export type MorphologyPartKind = WordPartKind | 'base' | 'connector'

export type WordPartLevel = 'junior' | 'cet4' | 'cet6' | 'common'

export interface WordPartExample {
  word: string
  breakdown: string
  meaning: string
}

export interface WordPart {
  id: string
  kind: WordPartKind
  form: string
  meaning: string
  simpleExplanation: string
  examples: WordPartExample[]
  tags: string[]
  level: WordPartLevel
  aliases?: string[]
}

export interface WordPartAnalysisPart {
  form: string
  kind: MorphologyPartKind
  meaning: string
  explanation?: string | null
  confidence?: number | null
}

export interface WordPartAnalysis {
  parts: WordPartAnalysisPart[]
  summary: string
  caution?: string | null
  related_word_part_ids?: string[]
}

export type WordPartProgressStatus = 'new' | 'learning' | 'familiar' | 'mastered'

export interface WordPartProgress {
  wordPartId: string
  status: WordPartProgressStatus
  practicedCount: number
  lastPracticedAt: string
}

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
  unit_order?: number | null
  requires_review?: boolean
  warnings?: string[]
  confidence?: number | null
  raw_line?: string | null
  evidence?: string[]
  mastery: number
}

export type UnitWorkspaceActionType =
  | 'daily_lesson'
  | 'exercise'
  | 'grammar'
  | 'pronunciation'
  | 'reading'
  | 'review'
  | 'vocabulary_new'
  | 'vocabulary_spelling'

export interface UnitWorkspaceItem {
  id: string
  title: string
  summary: string
  source_page: string
  mastery: number
  unit_order?: number | null
  meta?: Record<string, string | number | boolean | null>
}

export interface UnitWorkspaceAction {
  type: UnitWorkspaceActionType
  label: string
}

export interface UnitWorkspaceSection {
  id: 'vocabulary' | 'sentence_patterns' | 'grammar' | 'phrases' | 'pronunciation' | 'practice' | string
  title: string
  count: number
  items: UnitWorkspaceItem[]
  action: UnitWorkspaceAction
  empty: boolean
}

export interface UnitLearningWorkspace {
  unit: {
    id: string
    title: string
    subtitle: string
    estimated_minutes: number
    source_id: string
    source_title: string
  }
  overview: {
    title: string
    summary: string
    objectives: string[]
  }
  sections: UnitWorkspaceSection[]
  mastery_summary: {
    average: number
    mastered_count: number
    learning_count: number
    new_count: number
    total_count: number
  }
  recommended_next_action: UnitWorkspaceAction & {
    reason: string
    target?: string | null
  }
}

export interface KnowledgeReviewItem {
  id: string
  title: string
  type: KnowledgeType
  summary: string
  source_page: string
  unit_order?: number | null
  raw_line?: string | null
  confidence?: number | null
  warnings: string[]
  requires_review: boolean
  parser?: string | null
  status: 'draft' | 'published' | 'ignored' | string
  evidence: string[]
}

export interface KnowledgeParserEvidence {
  parser?: string | null
  parser_profile?: string | null
  book_manifest_id?: string | null
  vocabulary_parser?: string | null
  dictionary_enrichment?: string | null
  rag_chunk_count: number
  text_char_count: number
  toc_fallback: boolean
  warnings: string[]
  report: Record<string, unknown>
}

export interface ParserReportSummary {
  page_count?: number | null
  text_char_count?: number | null
  text_coverage_score?: number | null
  empty_page_ratio?: number | null
  block_count?: number | null
  heading_count?: number | null
  needs_ocr?: boolean | null
  needs_review?: boolean | null
  unit_count?: number | null
  rag_chunk_count?: number | null
  is_scanned_pdf_suspected?: boolean | null
  has_text_layer?: boolean | null
  [key: string]: unknown
}

export interface FailedKnowledgeSourceDetail {
  source_id?: string
  title?: string
  filename?: string
  status?: string
  quality_status?: string | null
  blocking_reasons?: string[]
  parser_report_summary?: ParserReportSummary
  can_delete?: boolean
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
    filename: string
    publisher: string
    edition: string
    grade: string
    volume?: string | null
    status: 'draft' | 'processing' | 'review_required' | 'published' | 'failed' | 'partial_indexed' | 'index_failed'
    unit_count: number
    knowledge_count: number
    progress: number
    requires_review?: boolean
    page_count?: number | null
    can_delete?: boolean
  }
  sources: Array<{
    id: string
    title: string
    filename: string
    publisher: string
    edition: string
    grade: string
    volume?: string | null
    status: 'draft' | 'processing' | 'review_required' | 'published' | 'failed' | 'partial_indexed' | 'index_failed'
    unit_count: number
    knowledge_count: number
    progress: number
    requires_review?: boolean
    page_count?: number | null
    can_delete?: boolean
  }>
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
  unit_workspace?: UnitLearningWorkspace
  review: {
    requires_review: boolean
    pending_count: number
    low_confidence_count: number
    warning_count: number
    items: KnowledgeReviewItem[]
  }
  parser_evidence: KnowledgeParserEvidence
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

export interface KnowledgeIngestResult {
  source_id: string
  parser_run_id?: string | null
  status: string
  processing_status?: string | null
  parse_quality_status?: string | null
  page_count: number
  unit_count: number
  knowledge_count: number
  message: string
  quality_status?: string | null
  availability_status?: string | null
  blocking_reasons?: string[]
  parser_report_summary?: ParserReportSummary
  quality_summary?: ParserReportSummary
  selected_engine?: string | null
  attempted_engines?: string[]
  fallback_used?: boolean
}

export interface KnowledgeIngestStatus {
  source_id: string
  parser_run_id?: string | null
  processing_status: string
  parse_quality_status?: string | null
  stage: string
  progress: number
  quality_status?: string | null
  availability_status: string
  blocking_reasons: string[]
  warnings: string[]
  parser_report_summary: ParserReportSummary
  quality_summary: ParserReportSummary
  selected_engine?: string | null
  attempted_engines: string[]
  fallback_used: boolean
  error_message?: string | null
  can_open_knowledge_base: boolean
  next_action: 'wait' | 'review' | 'upload_text_pdf' | 'open_knowledge_base'
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

export interface ExerciseSession {
  curriculum_node_id: string
  title: string
  pool?: {
    status: 'ready' | 'refreshing' | 'degraded' | 'generating'
    available_count: number
    target_count: number
    generation_run_id?: string | null
    generation_status?: 'queued' | 'running' | 'completed' | 'failed' | null
    retry_after_seconds?: number | null
  }
  questions: Array<ExerciseItem & {
    question_type: 'choice_context' | 'fill_blank' | 'dialogue_complete' | 'error_fix' | 'multiple_choice'
    stem: string
    options: string[]
    metadata?: ExerciseItem['metadata'] & {
      interaction?: {
        type?: string
        input_mode?: 'choice' | 'text'
        allow_retry?: boolean
        hint_levels?: number
      }
      scenario?: {
        name?: string
        setting?: string
        zh?: string
      }
      cognitive_level?: string
      estimated_seconds?: number
      rubric?: Record<string, unknown>
    }
  }>
}

export interface ExerciseAnswerResult {
  question_id: string
  correct: boolean
  score: number
  passed: boolean
  answer: string
  explanation: string
  feedback: string
  hint?: string | null
  can_retry: boolean
  error_type?: string | null
  next_review_signal: string
  rubric: Record<string, unknown>
}

export interface UnitVocabularySummary {
  unit_id: string
  total: number
  enrolled: number
  new: number
  learning: number
  mastered: number
  due: number
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
  recent_events?: Array<{
    id: string
    event_type: string
    skill: string
    source_type: string
    source_id?: string | null
    confidence: number
    occurred_at: string
    summary: string
  }>
  active_weaknesses?: string[]
}

export interface MemoryCardItem {
  id: string
  type: string
  title: string
  content: string
  skill: string
  confidence: number
  status?: string | null
  evidence: string[]
  impact: string
  updated_at?: string | null
  editable: boolean
}

export interface MemoryCenter {
  learner: Learner
  cards: MemoryCardItem[]
  recommendation_reason: string
  metrics: Record<string, number>
  settings: {
    emotion_rhythm_enabled: boolean
    inferred_preferences_enabled: boolean
    low_confidence_memory_enabled: boolean
  }
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
  profile?: {
    ability_scores: Array<{
      label: string
      value: number
      evidence_count: number
    }>
    mastery_buckets: Array<{
      label: string
      value: number
    }>
    trend: Array<{
      date: string
      accuracy: number
      due_reviews: number
    }>
  }
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
