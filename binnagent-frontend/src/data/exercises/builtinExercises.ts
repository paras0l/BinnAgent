import type { ExerciseItem, ExerciseTarget } from '@/types/exercises'

const presentForFutureTarget = {
  type: 'grammar_topic',
  id: 'present-for-future',
  label: '主将从现',
} satisfies ExerciseTarget

const becauseBecauseOfTarget = {
  type: 'grammar_topic',
  id: 'because-because-of',
  label: 'because 与 because of',
} satisfies ExerciseTarget

const whichThatTarget = {
  type: 'grammar_topic',
  id: 'which-that-relative',
  label: '定语从句中 which/that 的选择',
} satisfies ExerciseTarget

const significantTarget = {
  type: 'vocabulary_item',
  id: 'significant',
  label: 'significant',
} satisfies ExerciseTarget

const lookUpTarget = {
  type: 'vocabulary_item',
  id: 'look-up',
  label: 'look up',
} satisfies ExerciseTarget

export const CORE_VOCABULARY_EXERCISE_TARGET = {
  type: 'vocabulary',
  id: 'core-vocabulary',
  label: '核心词汇理解',
} satisfies ExerciseTarget

export const BUILTIN_EXERCISES: ExerciseItem[] = [
  {
    id: 'grammar-present-for-future-choice-1',
    target: presentForFutureTarget,
    skill: 'grammar',
    type: 'single_choice',
    prompt: 'If it ___ tomorrow, we will stay at home.',
    options: ['will rain', 'rains', 'rained', 'is raining'],
    correctAnswer: 'rains',
    explanation: '真实条件句里，主句用 will 表示将来，if 从句用一般现在时表示将来，所以选 rains。',
    difficulty: 'easy',
  },
  {
    id: 'grammar-because-because-of-fill-1',
    target: becauseBecauseOfTarget,
    skill: 'grammar',
    type: 'fill_blank',
    prompt: '补全句子：We stayed inside ___ the heavy rain.',
    correctAnswer: 'because of',
    acceptedAnswers: ['because of'],
    explanation: 'the heavy rain 是名词短语，前面要用介词短语 because of；because 后面接完整句子。',
    difficulty: 'easy',
  },
  {
    id: 'grammar-which-that-choice-1',
    target: whichThatTarget,
    skill: 'grammar',
    type: 'single_choice',
    prompt: 'This is the book ___ helped me understand relative clauses.',
    options: ['who', 'where', 'that', 'when'],
    correctAnswer: 'that',
    explanation: '先行词 the book 是物，且从句缺少主语；限制性定语从句里可用 that 或 which，这里选项中 that 最合适。',
    difficulty: 'medium',
  },
  {
    id: 'vocab-significant-choice-1',
    target: significantTarget,
    skill: 'vocabulary',
    type: 'single_choice',
    prompt: 'Which sentence uses significant correctly?',
    options: [
      'The result was significant because it changed our plan.',
      'She significant the door before leaving.',
      'They walked significant to school.',
      'This cup is very significant to drink.',
    ],
    correctAnswer: 'The result was significant because it changed our plan.',
    explanation: 'significant 是形容词，表示“重要的、显著的”。第一句用它修饰 result，并说明影响很大。',
    difficulty: 'easy',
  },
  {
    id: 'vocab-look-up-fill-1',
    target: lookUpTarget,
    skill: 'vocabulary',
    type: 'fill_blank',
    prompt: '补全句子：If you do not know the word, ___ it ___ in a dictionary.',
    correctAnswer: 'look; up',
    acceptedAnswers: ['look it up', 'look up'],
    explanation: 'look up 表示“查阅”。代词 it 作宾语时通常放在 look 和 up 中间：look it up。',
    difficulty: 'easy',
  },
  {
    id: 'vocab-core-choice-1',
    target: CORE_VOCABULARY_EXERCISE_TARGET,
    skill: 'vocabulary',
    type: 'single_choice',
    prompt: '遇到一个新词时，哪一种记录最能帮助后续复习？',
    options: [
      '只写中文意思',
      '记录核心义项、例句和容易混淆的用法',
      '只复制整段词典解释',
      '只标记为已掌握',
    ],
    correctAnswer: '记录核心义项、例句和容易混淆的用法',
    explanation: '词汇掌握需要语义、搭配和语境证据。只写中文意思很容易造成会认不会用。',
    difficulty: 'easy',
  },
]
