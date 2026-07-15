export type ReadingWorkspace = 'input' | 'extensive' | 'intensive' | 'review'

export type ReadingLevel = 'junior' | 'cet4' | 'cet6' | 'general'

export type ReadingTrainingGoal = 'intensive' | 'extensive' | 'mixed'

export type ReadingMaterialType = 'dialogue' | 'passage'

export type ReadingMaterialLength = 'short' | 'long'

export interface ReadingMaterial {
  title: string
  text: string
  level: ReadingLevel
  goal: ReadingTrainingGoal
  material_type?: ReadingMaterialType
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

export interface ReadingTitleSuggestionResponse {
  is_complete: boolean
  suggested_title?: string | null
  reason: string
  word_count: number
  sentence_count: number
}

export interface ReadingMaterialHistoryItem {
  id: string
  learner_id: string
  curriculum_node_id?: string | null
  title?: string | null
  text: string
  level: ReadingLevel
  goal: ReadingTrainingGoal
  material_type: ReadingMaterialType
  word_count: number
  sentence_count: number
  source: string
  generation_context?: ReadingGenerationContext | null
  created_at: string
  updated_at: string
}

export interface ReadingGenerationContext {
  prompt_id?: string | null
  prompt_version?: string | null
  prompt_execution_record_id?: string | null
  schema_validation_status?: string | null
  repair_used?: boolean
  source_id?: string
  source_title?: string
  unit_title?: string
  unit_subtitle?: string | null
  length?: ReadingMaterialLength
  theme?: string | null
  grammar_focus?: string[]
  vocabulary_used?: string[]
  level_rationale?: string | null
  comprehension_checks?: Array<{ question: string; answer: string }>
  confidence?: number | null
}

export interface ReadingMaterialGenerationResponse {
  material: ReadingMaterialHistoryItem
  generation_context: ReadingGenerationContext
}

export interface ReadingMaterialCompleteResponse {
  material_id: string
  attempt_id: string
  reading_value: number
  message: string
}

export interface ReadingCompletionStateInput {
  hasMaterial: boolean
  hasExtensiveEvidence: boolean
  analyzedSentenceCount: number
  goal: ReadingTrainingGoal
  isRecorded: boolean
}

export interface ReadingCompletionState {
  completion: Record<ReadingWorkspace, boolean>
  canComplete: boolean
  missingLabels: string[]
}

export interface ReadingCompletionPayloadInput {
  clientAttemptId: string
  analyzedSentenceIds: string[]
  goal: ReadingTrainingGoal
  extensiveEvidence: {
    gist: string
    centralSentence: string
  }
  grammarTopicCount: number
  grammarBlindSpots: string[]
  notes: string | null
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

export const READING_MATERIAL_TYPE_LABELS: Record<ReadingMaterialType, string> = {
  passage: '短文',
  dialogue: '对话',
}

export const READING_MATERIAL_LENGTH_LABELS: Record<ReadingMaterialLength, string> = {
  short: '短材料',
  long: '长材料',
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
const NONFINITE_PARTICIPLE_PATTERN = /\b(?:am|is|are|was|were|be|been|being|have|has|had|keep|keeps|kept|start|starts|started|begin|begins|began|continue|continues|continued)\s+[a-z]{3,}(?:ing|ed)\b|\b[a-z]{3,}(?:ing|ed)\s+(?:by|in|on|at|with|without|for|from)\b/i
const PREPOSITIONAL_PHRASE_PATTERN = /\b(in|on|at|for|with|without|by|from|of|about|after|before|during|through)\s+[a-z]/i

// A conservative verb lexicon avoids treating every "to + word" prepositional
// phrase (for example, "to school" or "to London") as an infinitive.
const COMMON_INFINITIVE_VERBS = new Set([
  'add',
  'answer',
  'ask',
  'be',
  'become',
  'begin',
  'build',
  'change',
  'check',
  'choose',
  'compare',
  'complete',
  'continue',
  'create',
  'decide',
  'describe',
  'develop',
  'discover',
  'do',
  'explain',
  'find',
  'finish',
  'focus',
  'follow',
  'get',
  'give',
  'help',
  'identify',
  'improve',
  'include',
  'keep',
  'know',
  'learn',
  'make',
  'notice',
  'practice',
  'prepare',
  'read',
  'remember',
  'review',
  'see',
  'show',
  'start',
  'study',
  'take',
  'think',
  'try',
  'understand',
  'use',
  'work',
  'write',
])

function hasNonfiniteForm(sentence: string): boolean {
  if (NONFINITE_PARTICIPLE_PATTERN.test(sentence)) return true

  return Array.from(sentence.matchAll(/\bto\s+([A-Za-z]+)\b/g)).some((match) => {
    const candidate = match[1].toLowerCase()
    return (
      COMMON_INFINITIVE_VERBS.has(candidate)
      || /(?:ate|en|ify|ise|ize)$/.test(candidate)
    )
  })
}

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
  if (wordCount === 0) return 0
  return Math.max(1, Math.ceil(wordCount / wordsPerMinute[level]))
}

export function buildReadingCompletionState({
  hasMaterial,
  hasExtensiveEvidence,
  analyzedSentenceCount,
  goal,
  isRecorded,
}: ReadingCompletionStateInput): ReadingCompletionState {
  const completion: Record<ReadingWorkspace, boolean> = {
    input: hasMaterial,
    extensive: hasMaterial && hasExtensiveEvidence,
    intensive: hasMaterial && analyzedSentenceCount > 0,
    review: hasMaterial && isRecorded,
  }
  const missingLabels: string[] = []

  if (!completion.input) missingLabels.push('添加阅读材料')
  if (goal !== 'intensive' && !completion.extensive) missingLabels.push('完成泛读记录')
  if (goal !== 'extensive' && !completion.intensive) missingLabels.push('完成至少 1 个精读句')

  return {
    completion,
    canComplete: missingLabels.length === 0,
    missingLabels,
  }
}

export function buildReadingCompletionPayload({
  clientAttemptId,
  analyzedSentenceIds,
  goal,
  extensiveEvidence,
  grammarTopicCount,
  grammarBlindSpots,
  notes,
}: ReadingCompletionPayloadInput) {
  return {
    client_attempt_id: clientAttemptId,
    selected_sentence_count: analyzedSentenceIds.length,
    analyzed_sentence_ids: analyzedSentenceIds,
    ...(goal !== 'intensive' ? {
      extensive_evidence: {
        gist: extensiveEvidence.gist.trim(),
        central_sentence: extensiveEvidence.centralSentence.trim(),
      },
    } : {}),
    grammar_topic_count: grammarTopicCount,
    grammar_blind_spots: grammarBlindSpots,
    correction_notes: [] as string[],
    notes,
  }
}

export function fingerprintReadingCompletionPayload(
  payload: ReturnType<typeof buildReadingCompletionPayload>
): string {
  const evidence = { ...payload, client_attempt_id: '' }
  const serialized = JSON.stringify(evidence)
  let hash = 2166136261
  for (let index = 0; index < serialized.length; index += 1) {
    hash ^= serialized.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return `reading-evidence-${(hash >>> 0).toString(16).padStart(8, '0')}`
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
  return READING_GRAMMAR_OPTIONS.filter((option) => {
    if (option.id === 'nonfinite-modifier') return hasNonfiniteForm(sentence)
    return option.signalWords.some((signal) => normalized.includes(signal.toLowerCase()))
  }).map((option) => option.id)
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

  if (hasNonfiniteForm(sentence)) {
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
