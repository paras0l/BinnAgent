export type ReadingWorkspace = 'input' | 'extensive' | 'intensive' | 'review'

export type ReadingLevel = 'junior' | 'cet4' | 'cet6' | 'general'

export type ReadingTrainingGoal = 'intensive' | 'extensive' | 'mixed'

export interface ReadingMaterial {
  title: string
  text: string
  level: ReadingLevel
  goal: ReadingTrainingGoal
}

export interface ReadingSentence {
  id: string
  order: number
  text: string
}

export interface ReadingKeywordCandidate {
  word: string
  count: number
}

export interface ReadingGrammarOption {
  id: string
  label: string
  grammarTopicTitle: string
  description: string
  signalWords: string[]
}

export interface ReadingSentenceHint {
  id: string
  label: string
  text: string
}

export const READING_LEVEL_LABELS: Record<ReadingLevel, string> = {
  junior: '初中',
  cet4: 'CET-4',
  cet6: 'CET-6',
  general: '通用',
}

export const READING_GOAL_LABELS: Record<ReadingTrainingGoal, string> = {
  intensive: '精读',
  extensive: '泛读',
  mixed: '先泛读后精读',
}

export const READING_GRAMMAR_OPTIONS: ReadingGrammarOption[] = [
  {
    id: 'relative-clause',
    label: '定语从句',
    grammarTopicTitle: '定语从句中 which/that 的选择',
    description: '看 which、that、who 等关系词如何修饰前面的名词。',
    signalWords: ['which', 'that', 'who', 'whose', 'where'],
  },
  {
    id: 'nonfinite-modifier',
    label: '非谓语作后置定语',
    grammarTopicTitle: '非谓语作后置定语',
    description: '看 doing、done、to do 放在名词后面时如何压缩从句。',
    signalWords: ['to ', 'ing', 'ed'],
  },
  {
    id: 'because',
    label: 'because / because of',
    grammarTopicTitle: 'because 与 because of',
    description: '区分后面接完整句子，还是接名词、代词或动名词短语。',
    signalWords: ['because', 'because of'],
  },
  {
    id: 'present-for-future',
    label: '主将从现',
    grammarTopicTitle: '主将从现',
    description: '遇到 if、when、as soon as 等从句时，检查将来语境里的时态。',
    signalWords: ['if', 'when', 'as soon as', 'unless'],
  },
  {
    id: 'concession-clause',
    label: '让步状语从句',
    grammarTopicTitle: '让步状语从句',
    description: '看 although、though、even though 引导的让步关系如何改变语气。',
    signalWords: ['although', 'though', 'even though'],
  },
  {
    id: 'prepositional-phrase',
    label: '介词短语',
    grammarTopicTitle: '介词短语',
    description: '把 in、on、at、with、by、for 等介词短语和句子主干分开看。',
    signalWords: [' in ', ' on ', ' at ', ' with ', ' by ', ' for ', ' of '],
  },
  {
    id: 'connectors',
    label: '连接词与句间逻辑',
    grammarTopicTitle: '连接词与句间逻辑',
    description: '用 however、therefore、but、so 等词判断转折、因果或递进。',
    signalWords: ['however', 'therefore', 'moreover', 'but', 'so', 'yet'],
  },
]

const COMMON_READING_WORDS = new Set([
  'the',
  'and',
  'that',
  'this',
  'with',
  'from',
  'have',
  'has',
  'had',
  'for',
  'are',
  'was',
  'were',
  'not',
  'but',
  'they',
  'their',
  'there',
  'when',
  'which',
  'who',
  'will',
  'would',
  'could',
  'should',
  'into',
  'about',
  'because',
  'than',
  'then',
  'also',
  'more',
  'most',
  'can',
  'may',
  'one',
  'you',
  'your',
  'our',
  'its',
  'his',
  'her',
  'she',
  'him',
])

const SENTENCE_PATTERN = /[^.!?]+(?:[.!?]+["')\]]*)?|[^.!?]+$/g
const ENGLISH_WORD_PATTERN = /[A-Za-z]+(?:[-'][A-Za-z]+)?/g
const NONFINITE_PATTERN = /\b(to\s+[a-z]+|[a-z]+ing|[a-z]+ed)\b/i
const PREPOSITIONAL_PHRASE_PATTERN = /\b(in|on|at|for|with|without|by|from|of|about|after|before|during|through)\s+[a-z]/i

export function splitReadingSentences(text: string): ReadingSentence[] {
  const normalized = text.replace(/\s+/g, ' ').trim()
  if (!normalized) return []

  return (normalized.match(SENTENCE_PATTERN) ?? [])
    .map((sentence) => sentence.trim())
    .filter(Boolean)
    .map((sentence, index) => ({
      id: `reading-sentence-${index + 1}`,
      order: index + 1,
      text: sentence,
    }))
}

export function countEnglishWords(text: string): number {
  return text.match(ENGLISH_WORD_PATTERN)?.length ?? 0
}

export function estimateReadingMinutes(text: string, level: ReadingLevel): number {
  const wordsPerMinute: Record<ReadingLevel, number> = {
    junior: 100,
    cet4: 130,
    cet6: 145,
    general: 125,
  }
  const wordCount = countEnglishWords(text)
  return Math.max(1, Math.ceil(wordCount / wordsPerMinute[level]))
}

export function buildKeywordCandidates(text: string, limit = 8): ReadingKeywordCandidate[] {
  const matches = text.match(ENGLISH_WORD_PATTERN) ?? []
  const counts = new Map<string, { count: number; firstIndex: number }>()

  matches.forEach((rawWord, index) => {
    const word = rawWord.toLowerCase()
    if (word.length < 4 || COMMON_READING_WORDS.has(word)) return
    const current = counts.get(word)
    counts.set(word, {
      count: (current?.count ?? 0) + 1,
      firstIndex: current?.firstIndex ?? index,
    })
  })

  return Array.from(counts.entries())
    .sort(([, a], [, b]) => b.count - a.count || a.firstIndex - b.firstIndex)
    .slice(0, limit)
    .map(([word, meta]) => ({ word, count: meta.count }))
}

export function suggestGrammarOptionIds(sentence: string): string[] {
  const normalized = ` ${sentence.toLowerCase()} `
  return READING_GRAMMAR_OPTIONS.filter((option) =>
    option.signalWords.some((signal) => normalized.includes(signal.toLowerCase()))
  ).map((option) => option.id)
}

export function buildSentenceFocusHints(sentence: string): ReadingSentenceHint[] {
  const normalized = sentence.toLowerCase()
  const hints: ReadingSentenceHint[] = []

  if (/\b(which|that|who|whose|where)\b/.test(normalized)) {
    hints.push({
      id: 'relative',
      label: '从句线索',
      text: '先确认关系词修饰的先行词，再判断从句是否补充说明这个名词。',
    })
  }

  if (/\b(because|although|though|if|when|while|unless|since|as soon as)\b/.test(normalized)) {
    hints.push({
      id: 'adverbial',
      label: '状语线索',
      text: '把原因、时间、条件或让步部分圈出来，再回到主句判断核心意思。',
    })
  }

  if (NONFINITE_PATTERN.test(sentence)) {
    hints.push({
      id: 'nonfinite',
      label: '非谓语线索',
      text: '检查 to do、doing、done 是否在补充名词、目的、结果或伴随动作。',
    })
  }

  if (PREPOSITIONAL_PHRASE_PATTERN.test(sentence)) {
    hints.push({
      id: 'preposition',
      label: '修饰语线索',
      text: '先临时拿掉介词短语，读出主干，再把地点、方式、对象等信息补回去。',
    })
  }

  if (/\b(however|therefore|moreover|instead|but|yet|so)\b/.test(normalized)) {
    hints.push({
      id: 'logic',
      label: '逻辑线索',
      text: '连接词通常提示转折、因果或递进，先判断句间关系再理解细节。',
    })
  }

  if (hints.length > 0) return hints

  return [
    {
      id: 'baseline',
      label: '主干线索',
      text: '先找谓语动词，再定位主语和宾语/表语；修饰语放到第二遍处理。',
    },
  ]
}

export function uniqueList<T>(items: T[]): T[] {
  return Array.from(new Set(items))
}
