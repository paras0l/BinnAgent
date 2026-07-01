export type ExerciseTargetType =
  | 'curriculum_node'
  | 'grammar_topic'
  | 'vocabulary_item'
  | 'vocabulary'
  | 'word_part'
  | 'reading_passage'
  | 'writing_phrase'
  | 'pronunciation_item'

export interface ExerciseTarget {
  type: ExerciseTargetType
  id: string
  label: string
}

export type ExerciseSourceType =
  | 'builtin'
  | 'curriculum'
  | 'generated'
  | 'imported'
  | 'manual'

export interface ExerciseSource {
  type: ExerciseSourceType
  name?: string
  refId?: string
  path?: string
}

export type ExerciseSkill = 'grammar' | 'vocabulary' | 'reading'

export type ExerciseType = 'single_choice' | 'fill_blank'

export interface ExerciseItem {
  id: string
  target: ExerciseTarget
  skill: ExerciseSkill
  type: ExerciseType
  prompt: string
  options?: string[]
  correctAnswer: string
  acceptedAnswers?: string[]
  explanation: string
  difficulty?: 'easy' | 'medium' | 'hard'
  source: ExerciseSource
  metadata?: Record<string, unknown>
}

export type ExerciseAttemptResult = 'correct' | 'incorrect'

export interface ExerciseAttempt {
  id: string
  exerciseId: string
  target: ExerciseTarget
  answer: string
  result: ExerciseAttemptResult
  createdAt: string
  should_update_mastery: boolean
  should_create_error_pattern: boolean
  should_create_memory_evidence: boolean
  metadata?: Record<string, unknown>
  sourceContext?: Record<string, unknown>
}
