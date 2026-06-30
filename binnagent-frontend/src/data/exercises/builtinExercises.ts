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

const prefixReTarget = {
  type: 'word_part',
  id: 'prefix-re',
  label: 're-',
} satisfies ExerciseTarget

const prefixUnTarget = {
  type: 'word_part',
  id: 'prefix-un',
  label: 'un-',
} satisfies ExerciseTarget

const prefixPreTarget = {
  type: 'word_part',
  id: 'prefix-pre',
  label: 'pre-',
} satisfies ExerciseTarget

const suffixTionTarget = {
  type: 'word_part',
  id: 'suffix-tion',
  label: '-tion',
} satisfies ExerciseTarget

const suffixFulTarget = {
  type: 'word_part',
  id: 'suffix-ful',
  label: '-ful',
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
  {
    id: 'word-part-prefix-re-choice-1',
    target: prefixReTarget,
    skill: 'vocabulary',
    type: 'single_choice',
    prompt: '在 review 这个词里，re- 最接近哪一层意思？',
    options: ['again / back', 'not', 'before', 'full of'],
    correctAnswer: 'again / back',
    explanation: 're- 常表示 again 或 back。review 可以理解为“再看一遍”，所以有“复习、回顾、评论”的意思。',
    difficulty: 'easy',
  },
  {
    id: 'word-part-prefix-un-choice-1',
    target: prefixUnTarget,
    skill: 'vocabulary',
    type: 'single_choice',
    prompt: 'unhelpful 中的 un- 表示什么？',
    options: ['not', 'again', 'before', 'a person who does something'],
    correctAnswer: 'not',
    explanation: 'un- 常表示 not / opposite of。unhelpful 就是“没有帮助的、不 helpful 的”。',
    difficulty: 'easy',
  },
  {
    id: 'word-part-prefix-pre-fill-1',
    target: prefixPreTarget,
    skill: 'vocabulary',
    type: 'fill_blank',
    prompt: '补全含义：pre- 通常表示 ___。',
    correctAnswer: 'before',
    acceptedAnswers: ['before', '预先', '在前', '之前'],
    explanation: 'pre- 常提示 before / 预先，例如 preview 是“预先看”，predict 是“预先说出/预测”。',
    difficulty: 'easy',
  },
  {
    id: 'word-part-suffix-tion-choice-1',
    target: suffixTionTarget,
    skill: 'vocabulary',
    type: 'single_choice',
    prompt: '看到单词以 -tion 结尾时，最常见的词性提示是什么？',
    options: ['名词', '动词', '副词', '介词'],
    correctAnswer: '名词',
    explanation: '-tion 常提示抽象名词或动作结果，例如 action、prediction、information。',
    difficulty: 'easy',
  },
  {
    id: 'word-part-suffix-ful-fill-1',
    target: suffixFulTarget,
    skill: 'vocabulary',
    type: 'fill_blank',
    prompt: '补全含义：-ful 常表示 full of / 具有……性质的，例如 careful 表示“___”。',
    correctAnswer: '小心的',
    acceptedAnswers: ['小心的', '仔细的', '充满小心的', 'careful'],
    explanation: '-ful 常把名词或动词线索变成形容词，表示“充满……的、具有……性质的”。careful 就是“小心的、仔细的”。',
    difficulty: 'easy',
  },
]
