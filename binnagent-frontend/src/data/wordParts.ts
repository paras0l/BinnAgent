import type {
  MorphologyPartKind,
  WordPart,
  WordPartAnalysis,
  WordPartAnalysisPart,
  WordPartKind,
  WordPartLevel,
} from '@/types'

export type WordPartFilterKind = WordPartKind | 'all'
export type WordPartFilterLevel = WordPartLevel | 'all'

export interface WordPartExercise {
  id: string
  word: string
  targetMeaning: string
  breakdown: string
  hints: string[]
  explanation: string
  example: string
  relatedWordPartIds: string[]
}

export const WORD_PARTS: WordPart[] = [
  {
    id: 'prefix-un',
    kind: 'prefix',
    form: 'un-',
    meaning: 'not / 不',
    simpleExplanation: '表示否定，常把形容词或动词变成相反意思。',
    examples: [
      { word: 'unhappy', breakdown: 'un- + happy', meaning: '不开心的' },
      { word: 'unhelpful', breakdown: 'un- + help + -ful', meaning: '没有帮助的' },
    ],
    tags: ['否定', '高频'],
    level: 'common',
  },
  {
    id: 'prefix-re',
    kind: 'prefix',
    form: 're-',
    meaning: 'again / back / 再、回',
    simpleExplanation: '表示重复、返回或重新做某事。',
    examples: [
      { word: 'review', breakdown: 're- + view', meaning: '再看一遍，复习，评论' },
      { word: 'rewrite', breakdown: 're- + write', meaning: '重写' },
    ],
    tags: ['重复', '方向'],
    level: 'common',
  },
  {
    id: 'prefix-pre',
    kind: 'prefix',
    form: 'pre-',
    meaning: 'before / 预先',
    simpleExplanation: '表示在某事之前或提前发生。',
    examples: [
      { word: 'preview', breakdown: 'pre- + view', meaning: '预览' },
      { word: 'prediction', breakdown: 'pre- + dict + -ion', meaning: '预测' },
    ],
    tags: ['时间', 'CET'],
    level: 'cet4',
  },
  {
    id: 'prefix-dis',
    kind: 'prefix',
    form: 'dis-',
    meaning: 'not / apart / 不、分开',
    simpleExplanation: '常表示否定、相反或分离。',
    examples: [
      { word: 'disagree', breakdown: 'dis- + agree', meaning: '不同意' },
      { word: 'disconnect', breakdown: 'dis- + connect', meaning: '断开连接' },
    ],
    tags: ['否定', '分离'],
    level: 'common',
  },
  {
    id: 'prefix-mis',
    kind: 'prefix',
    form: 'mis-',
    meaning: 'wrongly / 错误地',
    simpleExplanation: '表示错误、误解或做得不对。',
    examples: [
      { word: 'misread', breakdown: 'mis- + read', meaning: '读错，误解' },
      { word: 'misuse', breakdown: 'mis- + use', meaning: '误用' },
    ],
    tags: ['错误', '易混'],
    level: 'common',
  },
  {
    id: 'prefix-over',
    kind: 'prefix',
    form: 'over-',
    meaning: 'too much / above / 过度、在上方',
    simpleExplanation: '表示过量、超过或在上方。',
    examples: [
      { word: 'overwork', breakdown: 'over- + work', meaning: '过度工作' },
      { word: 'overweight', breakdown: 'over- + weight', meaning: '超重的' },
    ],
    tags: ['程度', '位置'],
    level: 'common',
  },
  {
    id: 'prefix-under',
    kind: 'prefix',
    form: 'under-',
    meaning: 'below / not enough / 在下、较少',
    simpleExplanation: '表示在下面、不足或低于某标准。',
    examples: [
      { word: 'underground', breakdown: 'under- + ground', meaning: '地下的' },
      { word: 'underestimate', breakdown: 'under- + estimate', meaning: '低估' },
    ],
    tags: ['程度', '位置'],
    level: 'common',
  },
  {
    id: 'prefix-inter',
    kind: 'prefix',
    form: 'inter-',
    meaning: 'between / among / 在……之间',
    simpleExplanation: '表示两者或多者之间的关系。',
    examples: [
      { word: 'international', breakdown: 'inter- + nation + -al', meaning: '国际的' },
      { word: 'interact', breakdown: 'inter- + act', meaning: '互动' },
    ],
    tags: ['关系', 'CET'],
    level: 'cet4',
  },
  {
    id: 'prefix-trans',
    kind: 'prefix',
    form: 'trans-',
    meaning: 'across / change / 穿过、转变',
    simpleExplanation: '表示跨越、转移或改变状态。',
    examples: [
      { word: 'transport', breakdown: 'trans- + port', meaning: '运输' },
      { word: 'translate', breakdown: 'trans- + late', meaning: '翻译，转换语言' },
    ],
    tags: ['方向', '变化'],
    level: 'cet4',
  },
  {
    id: 'prefix-sub',
    kind: 'prefix',
    form: 'sub-',
    meaning: 'under / below / 在下',
    simpleExplanation: '表示下方、次级或从属。',
    examples: [
      { word: 'subway', breakdown: 'sub- + way', meaning: '地铁，地下通道' },
      { word: 'submarine', breakdown: 'sub- + marine', meaning: '潜水艇' },
    ],
    tags: ['位置', '层级'],
    level: 'common',
  },
  {
    id: 'suffix-ful',
    kind: 'suffix',
    form: '-ful',
    meaning: 'full of / 充满……的',
    simpleExplanation: '常把名词或动词变成形容词，表示具有某性质。',
    examples: [
      { word: 'helpful', breakdown: 'help + -ful', meaning: '有帮助的' },
      { word: 'careful', breakdown: 'care + -ful', meaning: '小心的' },
    ],
    tags: ['形容词', '高频'],
    level: 'common',
  },
  {
    id: 'suffix-less',
    kind: 'suffix',
    form: '-less',
    meaning: 'without / 没有……的',
    simpleExplanation: '常构成形容词，表示缺少某物或某性质。',
    examples: [
      { word: 'careless', breakdown: 'care + -less', meaning: '粗心的' },
      { word: 'homeless', breakdown: 'home + -less', meaning: '无家可归的' },
    ],
    tags: ['形容词', '否定'],
    level: 'common',
  },
  {
    id: 'suffix-ness',
    kind: 'suffix',
    form: '-ness',
    meaning: 'state / quality / 状态、性质',
    simpleExplanation: '常把形容词变成抽象名词。',
    examples: [
      { word: 'happiness', breakdown: 'happy + -ness', meaning: '幸福，快乐' },
      { word: 'darkness', breakdown: 'dark + -ness', meaning: '黑暗' },
    ],
    tags: ['名词', '抽象'],
    level: 'common',
  },
  {
    id: 'suffix-tion',
    kind: 'suffix',
    form: '-tion',
    meaning: 'action / result / 名词后缀',
    simpleExplanation: '常把动词相关形式变成表示行为或结果的名词。',
    examples: [
      { word: 'prediction', breakdown: 'pre- + dict + -ion', meaning: '预测' },
      { word: 'information', breakdown: 'inform + -ation', meaning: '信息' },
    ],
    tags: ['名词', 'CET'],
    level: 'cet4',
    aliases: ['ion', 'ation'],
  },
  {
    id: 'suffix-ment',
    kind: 'suffix',
    form: '-ment',
    meaning: 'result / state / 结果、状态',
    simpleExplanation: '常把动词变成名词，表示行为结果或状态。',
    examples: [
      { word: 'movement', breakdown: 'move + -ment', meaning: '运动，动作' },
      { word: 'agreement', breakdown: 'agree + -ment', meaning: '协议，同意' },
    ],
    tags: ['名词'],
    level: 'common',
  },
  {
    id: 'suffix-able',
    kind: 'suffix',
    form: '-able',
    meaning: 'can be / 能够……的',
    simpleExplanation: '常构成形容词，表示可以被做或具有某能力。',
    examples: [
      { word: 'readable', breakdown: 'read + -able', meaning: '易读的' },
      { word: 'visible', breakdown: 'vis + -ible', meaning: '可见的' },
    ],
    tags: ['形容词', '能力'],
    level: 'cet4',
    aliases: ['ible'],
  },
  {
    id: 'suffix-ive',
    kind: 'suffix',
    form: '-ive',
    meaning: 'having the nature of / 有……性质的',
    simpleExplanation: '常构成形容词，表示倾向、性质或功能。',
    examples: [
      { word: 'active', breakdown: 'act + -ive', meaning: '积极的，活跃的' },
      { word: 'creative', breakdown: 'create + -ive', meaning: '有创造力的' },
    ],
    tags: ['形容词', 'CET'],
    level: 'cet4',
  },
  {
    id: 'suffix-er',
    kind: 'suffix',
    form: '-er',
    meaning: 'person or thing / 人或物',
    simpleExplanation: '常表示做某事的人或工具，也可表示比较级。',
    examples: [
      { word: 'teacher', breakdown: 'teach + -er', meaning: '老师' },
      { word: 'reader', breakdown: 'read + -er', meaning: '读者' },
    ],
    tags: ['名词', '比较级'],
    level: 'junior',
  },
  {
    id: 'suffix-or',
    kind: 'suffix',
    form: '-or',
    meaning: 'person or thing / 人或物',
    simpleExplanation: '常表示执行动作的人、物或角色。',
    examples: [
      { word: 'actor', breakdown: 'act + -or', meaning: '演员' },
      { word: 'visitor', breakdown: 'visit + -or', meaning: '访客' },
    ],
    tags: ['名词'],
    level: 'common',
  },
  {
    id: 'suffix-ly',
    kind: 'suffix',
    form: '-ly',
    meaning: 'in a way / ……地',
    simpleExplanation: '常把形容词变成副词，表示方式。',
    examples: [
      { word: 'quickly', breakdown: 'quick + -ly', meaning: '快速地' },
      { word: 'carefully', breakdown: 'careful + -ly', meaning: '小心地' },
    ],
    tags: ['副词'],
    level: 'junior',
  },
  {
    id: 'root-spect',
    kind: 'root',
    form: 'spect',
    meaning: 'look / 看',
    simpleExplanation: '表示看、观察或检查。',
    examples: [
      { word: 'inspect', breakdown: 'in- + spect', meaning: '检查' },
      { word: 'respect', breakdown: 're- + spect', meaning: '尊重，重视' },
    ],
    tags: ['感知', 'CET'],
    level: 'cet4',
  },
  {
    id: 'root-port',
    kind: 'root',
    form: 'port',
    meaning: 'carry / 搬运',
    simpleExplanation: '表示携带、搬运或运输。',
    examples: [
      { word: 'transport', breakdown: 'trans- + port', meaning: '运输' },
      { word: 'import', breakdown: 'im- + port', meaning: '进口，输入' },
    ],
    tags: ['移动', 'CET'],
    level: 'cet4',
  },
  {
    id: 'root-dict',
    kind: 'root',
    form: 'dict',
    meaning: 'say / 说',
    simpleExplanation: '表示说、宣布或表达。',
    examples: [
      { word: 'predict', breakdown: 'pre- + dict', meaning: '预测' },
      { word: 'prediction', breakdown: 'pre- + dict + -ion', meaning: '预测' },
    ],
    tags: ['语言', 'CET'],
    level: 'cet4',
  },
  {
    id: 'root-scrib-script',
    kind: 'root',
    form: 'scrib/script',
    meaning: 'write / 写',
    simpleExplanation: '表示书写、记录或文本。',
    examples: [
      { word: 'describe', breakdown: 'de- + scrib(e)', meaning: '描述' },
      { word: 'script', breakdown: 'script', meaning: '脚本，手稿' },
    ],
    tags: ['书写', 'CET'],
    level: 'cet4',
    aliases: ['scrib', 'script'],
  },
  {
    id: 'root-form',
    kind: 'root',
    form: 'form',
    meaning: 'shape / 形状',
    simpleExplanation: '表示形状、形式或形成。',
    examples: [
      { word: 'format', breakdown: 'form + -at', meaning: '格式' },
      { word: 'transform', breakdown: 'trans- + form', meaning: '改变形态' },
    ],
    tags: ['结构', 'CET'],
    level: 'common',
  },
  {
    id: 'root-struct',
    kind: 'root',
    form: 'struct',
    meaning: 'build / 建造',
    simpleExplanation: '表示建造、组织或结构。',
    examples: [
      { word: 'construct', breakdown: 'con- + struct', meaning: '建造' },
      { word: 'structure', breakdown: 'struct + -ure', meaning: '结构' },
    ],
    tags: ['结构', 'CET'],
    level: 'cet4',
  },
  {
    id: 'root-vis-vid',
    kind: 'root',
    form: 'vis/vid',
    meaning: 'see / 看',
    simpleExplanation: '表示看、可见或影像。',
    examples: [
      { word: 'visible', breakdown: 'vis + -ible', meaning: '可见的' },
      { word: 'video', breakdown: 'vid + -eo', meaning: '视频' },
    ],
    tags: ['感知', 'CET'],
    level: 'cet4',
    aliases: ['vis', 'vid', 'view'],
  },
  {
    id: 'root-tele',
    kind: 'root',
    form: 'tele',
    meaning: 'far / 远',
    simpleExplanation: '表示远距离传递或远方。',
    examples: [
      { word: 'telephone', breakdown: 'tele + phon(e)', meaning: '电话' },
      { word: 'television', breakdown: 'tele + vis + -ion', meaning: '电视' },
    ],
    tags: ['距离', '科技'],
    level: 'common',
  },
  {
    id: 'root-phon',
    kind: 'root',
    form: 'phon',
    meaning: 'sound / 声音',
    simpleExplanation: '表示声音、发声或语音。',
    examples: [
      { word: 'telephone', breakdown: 'tele + phon(e)', meaning: '电话' },
      { word: 'phonetic', breakdown: 'phon + -etic', meaning: '语音的' },
    ],
    tags: ['声音', '发音'],
    level: 'common',
  },
  {
    id: 'root-bio',
    kind: 'root',
    form: 'bio',
    meaning: 'life / 生命',
    simpleExplanation: '表示生命、生物或生物学。',
    examples: [
      { word: 'biology', breakdown: 'bio + -logy', meaning: '生物学' },
      { word: 'biography', breakdown: 'bio + graph + -y', meaning: '传记' },
    ],
    tags: ['科学', 'CET'],
    level: 'cet4',
  },
]

export const WORD_PART_EXERCISES: WordPartExercise[] = [
  {
    id: 'exercise-unhelpful',
    word: 'unhelpful',
    targetMeaning: '没有帮助的',
    breakdown: 'un- + help + -ful',
    hints: ['先找否定前缀。', '核心词是 help。', '-ful 常把词变成“有……性质的”形容词。'],
    explanation: 'un- 表示 not，help 是帮助，-ful 表示具有某性质。合起来就是“不具有帮助性质的”。',
    example: 'A long but vague answer can be unhelpful.',
    relatedWordPartIds: ['prefix-un', 'suffix-ful'],
  },
  {
    id: 'exercise-review',
    word: 'review',
    targetMeaning: '复习，评论',
    breakdown: 're- + view',
    hints: ['这个词开头有 re-。', 'view 和“看”有关。', '先按“再看一遍”猜大意。'],
    explanation: 're- 表示 again/back，view 表示看。review 可理解为“再看一遍”，所以有复习、回顾和评论的意思。',
    example: 'Please review the notes before the quiz.',
    relatedWordPartIds: ['prefix-re', 'root-vis-vid'],
  },
  {
    id: 'exercise-transport',
    word: 'transport',
    targetMeaning: '运输',
    breakdown: 'trans- + port',
    hints: ['trans- 常表示 across。', 'port 表示 carry。', '把东西从一处带到另一处。'],
    explanation: 'trans- 表示跨越，port 表示搬运。transport 就是“跨地方搬运”，即运输。',
    example: 'The company transports food to nearby cities.',
    relatedWordPartIds: ['prefix-trans', 'root-port'],
  },
  {
    id: 'exercise-prediction',
    word: 'prediction',
    targetMeaning: '预测',
    breakdown: 'pre- + dict + -ion',
    hints: ['pre- 表示 before。', 'dict 表示 say。', '-ion 常提示这是名词。'],
    explanation: 'pre- 是提前，dict 是说，-ion 是名词后缀。prediction 可理解为“提前说出的话”，也就是预测。',
    example: 'The weather prediction was correct.',
    relatedWordPartIds: ['prefix-pre', 'root-dict', 'suffix-tion'],
  },
  {
    id: 'exercise-visible',
    word: 'visible',
    targetMeaning: '可见的',
    breakdown: 'vis + -ible',
    hints: ['vis 和 see/look 有关。', '-ible 与 -able 类似，表示 can be。', '先猜“能够被看见的”。'],
    explanation: 'vis 表示看，-ible 表示能够被……的。visible 就是“能够被看见的”。',
    example: 'The moon is clearly visible tonight.',
    relatedWordPartIds: ['root-vis-vid', 'suffix-able'],
  },
  {
    id: 'exercise-disconnect',
    word: 'disconnect',
    targetMeaning: '断开连接',
    breakdown: 'dis- + connect',
    hints: ['dis- 可表示 apart。', 'connect 是连接。', '把连接分开就是断开。'],
    explanation: 'dis- 表示分开或相反，connect 是连接。disconnect 表示断开连接。',
    example: 'Please disconnect the charger after use.',
    relatedWordPartIds: ['prefix-dis'],
  },
  {
    id: 'exercise-movement',
    word: 'movement',
    targetMeaning: '运动，动作',
    breakdown: 'move + -ment',
    hints: ['先识别基础词 move。', '-ment 常把动词变成名词。', '表示动作、过程或结果。'],
    explanation: 'move 是移动，-ment 常构成名词。movement 表示移动的动作、运动或活动。',
    example: 'Regular movement helps you stay healthy.',
    relatedWordPartIds: ['suffix-ment'],
  },
  {
    id: 'exercise-telephone',
    word: 'telephone',
    targetMeaning: '电话',
    breakdown: 'tele + phon(e)',
    hints: ['tele 表示 far。', 'phon 表示 sound。', '远距离传递声音。'],
    explanation: 'tele 表示远，phon 表示声音。telephone 原本可以理解为“远距离的声音”。',
    example: 'The telephone changed long-distance communication.',
    relatedWordPartIds: ['root-tele', 'root-phon'],
  },
]

export const WORD_PART_LEVEL_LABELS: Record<WordPartFilterLevel, string> = {
  all: '全部级别',
  common: '高频通用',
  junior: '初中常见',
  cet4: 'CET-4',
  cet6: 'CET-6',
}

export const WORD_PART_KIND_LABELS: Record<WordPartFilterKind, string> = {
  all: '全部',
  prefix: '前缀',
  root: '词根',
  suffix: '后缀',
}

export const MORPHOLOGY_KIND_LABELS: Record<MorphologyPartKind, string> = {
  prefix: '前缀',
  root: '词根',
  suffix: '后缀',
  base: '基础词',
  connector: '连接',
}

const EXACT_ANALYSES: Record<string, WordPartAnalysis> = {
  unhelpful: analysisFromParts(
    [
      part('un-', 'prefix', 'not / 不', '把 helpful 变成相反意思。', 0.95),
      part('help', 'base', '帮助', '核心基础词。', 0.9),
      part('-ful', 'suffix', 'full of / 具有……性质的', '提示形容词性质。', 0.95),
    ],
    'unhelpful 可以理解为“不具有帮助性质的”，也就是没有帮助的。',
    ['prefix-un', 'suffix-ful'],
  ),
  review: analysisFromParts(
    [
      part('re-', 'prefix', 'again / back / 再、回', '表示重新或再次。', 0.95),
      part('view', 'root', 'see / 看', '承载“看”的核心含义。', 0.86),
    ],
    'review 可先理解为“再看一遍”，再根据语境判断是复习、回顾还是评论。',
    ['prefix-re', 'root-vis-vid'],
  ),
  preview: analysisFromParts(
    [
      part('pre-', 'prefix', 'before / 预先', '表示提前。', 0.95),
      part('view', 'root', 'see / 看', '承载“看”的含义。', 0.86),
    ],
    'preview 可以理解为“预先看”，也就是预览。',
    ['prefix-pre', 'root-vis-vid'],
  ),
  transport: analysisFromParts(
    [
      part('trans-', 'prefix', 'across / 跨越', '表示从一处到另一处。', 0.92),
      part('port', 'root', 'carry / 搬运', '承载搬运的核心含义。', 0.93),
    ],
    'transport 可以理解为“跨地方搬运”，所以表示运输。',
    ['prefix-trans', 'root-port'],
  ),
  prediction: analysisFromParts(
    [
      part('pre-', 'prefix', 'before / 预先', '表示提前。', 0.95),
      part('dict', 'root', 'say / 说', '承载“说出”的核心含义。', 0.88),
      part('-ion', 'suffix', '名词后缀', '提示这是名词。', 0.93),
    ],
    'prediction 原意接近“提前说出”，所以表示预测。',
    ['prefix-pre', 'root-dict', 'suffix-tion'],
  ),
  visible: analysisFromParts(
    [
      part('vis', 'root', 'see / 看', '承载“看见”的核心含义。', 0.9),
      part('-ible', 'suffix', 'can be / 能够……的', '与 -able 类似，表示可被做。', 0.88),
    ],
    'visible 可以理解为“能够被看见的”，也就是可见的。',
    ['root-vis-vid', 'suffix-able'],
  ),
  disconnect: analysisFromParts(
    [
      part('dis-', 'prefix', 'apart / 分开', '表示分离或相反。', 0.86),
      part('connect', 'base', '连接', '核心基础词。', 0.92),
    ],
    'disconnect 可以理解为“把连接分开”，也就是断开连接。',
    ['prefix-dis'],
  ),
  misread: analysisFromParts(
    [
      part('mis-', 'prefix', 'wrongly / 错误地', '表示误做某事。', 0.92),
      part('read', 'base', '阅读', '核心基础词。', 0.9),
    ],
    'misread 是“错误地阅读或理解”，所以表示读错、误解。',
    ['prefix-mis'],
  ),
  movement: analysisFromParts(
    [
      part('move', 'base', '移动', '核心基础词。', 0.9),
      part('-ment', 'suffix', '结果或状态', '常把动词变成名词。', 0.9),
    ],
    'movement 表示移动这一动作、过程或活动。',
    ['suffix-ment'],
  ),
  telephone: analysisFromParts(
    [
      part('tele', 'root', 'far / 远', '表示远距离。', 0.9),
      part('phon', 'root', 'sound / 声音', '表示声音或语音。', 0.9),
    ],
    'telephone 可以理解为“远距离的声音”，也就是电话。',
    ['root-tele', 'root-phon'],
  ),
}

export function searchWordParts(
  query: string,
  kind: WordPartFilterKind = 'all',
  level: WordPartFilterLevel = 'all',
): WordPart[] {
  const normalizedQuery = normalizeSearch(query)
  return WORD_PARTS.filter((item) => kind === 'all' || item.kind === kind)
    .filter((item) => level === 'all' || item.level === level)
    .filter((item) => {
      if (!normalizedQuery) return true
      const haystack = [
        item.form,
        item.meaning,
        item.simpleExplanation,
        item.tags.join(' '),
        item.examples.map((example) => `${example.word} ${example.breakdown} ${example.meaning}`).join(' '),
      ].join(' ').toLowerCase()
      return haystack.includes(normalizedQuery)
    })
}

export function inferWordPartAnalysis(term: string | null | undefined): WordPartAnalysis | null {
  const normalized = normalizeLookupWord(term)
  if (!normalized) return null
  if (EXACT_ANALYSES[normalized]) return EXACT_ANALYSES[normalized]

  const prefixMatch = findAffixMatch(normalized, 'prefix')
  const suffixMatch = findAffixMatch(normalized, 'suffix')
  const middle = normalized
    .slice(prefixMatch?.lookup.length ?? 0)
    .slice(0, suffixMatch ? -suffixMatch.lookup.length : undefined)
  const rootMatch = findRootMatch(middle || normalized)

  if (!prefixMatch && !suffixMatch && !rootMatch) return null
  if (!rootMatch && (!prefixMatch || !suffixMatch)) return null

  const parts: WordPartAnalysisPart[] = []
  const related = new Set<string>()
  if (prefixMatch) {
    parts.push(part(prefixMatch.part.form, 'prefix', prefixMatch.part.meaning, prefixMatch.part.simpleExplanation, 0.68))
    related.add(prefixMatch.part.id)
  }
  if (rootMatch) {
    parts.push(part(rootMatch.displayForm, 'root', rootMatch.part.meaning, rootMatch.part.simpleExplanation, 0.64))
    related.add(rootMatch.part.id)
  } else if (middle.length >= 3) {
    parts.push(part(middle, 'base', '基础词或词干', '可先把它当作核心部分，再查词典验证。', 0.45))
  }
  if (suffixMatch) {
    parts.push(part(suffixMatch.part.form, 'suffix', suffixMatch.part.meaning, suffixMatch.part.simpleExplanation, 0.68))
    related.add(suffixMatch.part.id)
  }

  if (parts.length < 2) return null
  return {
    parts,
    summary: `${normalized} 可能包含 ${parts.map((item) => item.form).join(' + ')}，可以先用构词线索猜大意，再回到例句里确认。`,
    caution: '这是基于常见词根词缀的辅助分析，具体含义和用法仍要结合词典与例句。',
    related_word_part_ids: Array.from(related),
  }
}

export function spellingSafeMorphologyParts(analysis: WordPartAnalysis | null | undefined): WordPartAnalysisPart[] {
  if (!analysis) return []
  return analysis.parts.filter((item) => item.kind === 'prefix' || item.kind === 'suffix')
}

export function formatMorphologyForNote(analysis: WordPartAnalysis | null | undefined): string {
  if (!analysis) return ''
  const lines = [
    '构词分析',
    ...analysis.parts.map((item) => `${item.form} (${MORPHOLOGY_KIND_LABELS[item.kind]}) = ${item.meaning}`),
    analysis.summary,
  ]
  if (analysis.caution) lines.push(`注意：${analysis.caution}`)
  return lines.join('\n')
}

function part(
  form: string,
  kind: MorphologyPartKind,
  meaning: string,
  explanation?: string,
  confidence?: number,
): WordPartAnalysisPart {
  return { form, kind, meaning, explanation, confidence }
}

function analysisFromParts(
  parts: WordPartAnalysisPart[],
  summary: string,
  relatedWordPartIds: string[],
): WordPartAnalysis {
  return {
    parts,
    summary,
    caution: '构词法适合帮助记忆和猜大意，最终仍要结合例句验证。',
    related_word_part_ids: relatedWordPartIds,
  }
}

function normalizeSearch(value: string) {
  return value.trim().toLowerCase()
}

function normalizeLookupWord(value: string | null | undefined) {
  const normalized = value?.trim().toLowerCase().replace(/^[^a-z]+|[^a-z]+$/g, '') ?? ''
  if (!/^[a-z]+$/.test(normalized)) return ''
  return normalized
}

function findAffixMatch(word: string, kind: 'prefix' | 'suffix') {
  const candidates = WORD_PARTS.filter((item) => item.kind === kind)
    .flatMap((item) => wordPartLookups(item).map((lookup) => ({ part: item, lookup })))
    .sort((a, b) => b.lookup.length - a.lookup.length)
  return candidates.find((candidate) => (
    kind === 'prefix'
      ? word.startsWith(candidate.lookup) && word.length > candidate.lookup.length + 2
      : word.endsWith(candidate.lookup) && word.length > candidate.lookup.length + 2
  ))
}

function findRootMatch(value: string) {
  const candidates = WORD_PARTS.filter((item) => item.kind === 'root')
    .flatMap((item) => wordPartLookups(item).map((lookup) => ({ part: item, lookup })))
    .filter((candidate) => candidate.lookup.length >= 3)
    .sort((a, b) => b.lookup.length - a.lookup.length)
  const match = candidates.find((candidate) => value.includes(candidate.lookup))
  if (!match) return null
  return {
    part: match.part,
    displayForm: match.lookup,
  }
}

function wordPartLookups(item: WordPart) {
  const forms = item.aliases?.length ? item.aliases : item.form.split('/')
  return forms
    .map((form) => form.replace(/^-+|-+$/g, '').toLowerCase())
    .filter(Boolean)
}
