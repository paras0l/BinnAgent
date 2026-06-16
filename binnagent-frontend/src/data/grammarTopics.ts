export type GrammarCategory =
  | 'tense'
  | 'clause'
  | 'nonfinite'
  | 'subjunctive'
  | 'modal'
  | 'agreement'
  | 'article-preposition'
  | 'sentence-structure'
  | 'error-prone'

export interface GrammarTopic {
  id: string
  category: GrammarCategory
  title: string
  level: '基础' | '进阶' | '高频易错'
  tags: string[]
  shortDescription: string
}

export const GRAMMAR_CATEGORY_LABELS: Record<GrammarCategory, string> = {
  tense: '时态',
  clause: '从句',
  nonfinite: '非谓语',
  subjunctive: '虚拟语气',
  modal: '情态动词',
  agreement: '主谓一致',
  'article-preposition': '冠词/介词',
  'sentence-structure': '句子结构',
  'error-prone': '易错点',
}

export const GRAMMAR_TOPICS: GrammarTopic[] = [
  {
    id: 'present-for-future',
    category: 'tense',
    title: '主将从现',
    level: '高频易错',
    tags: ['时间状语从句', '条件状语从句', '一般现在时'],
    shortDescription: '主句表达将来，从句用一般现在时表示将来，常见于 if、when、as soon as 等引导的从句。',
  },
  {
    id: 'if-present-for-future',
    category: 'clause',
    title: 'if 条件状语从句中的主将从现',
    level: '基础',
    tags: ['if', '条件', 'will'],
    shortDescription: '只聚焦真实条件句里 if 从句不用 will 的规则，例如 If it rains tomorrow, I will stay home.',
  },
  {
    id: 'when-time-clause',
    category: 'clause',
    title: 'when 引导时间状语从句',
    level: '基础',
    tags: ['when', '时间状语', '时态'],
    shortDescription: '区分 when 从句表达“当……时”的时间关系，以及将来语境下的时态选择。',
  },
  {
    id: 'since-time-clause',
    category: 'clause',
    title: 'since 引导时间状语从句',
    level: '进阶',
    tags: ['since', '现在完成时', '时间点'],
    shortDescription: '讲清 since 后接过去时间点或一般过去时从句，主句常用现在完成时。',
  },
  {
    id: 'which-that-relative',
    category: 'clause',
    title: '定语从句中 which/that 的选择',
    level: '高频易错',
    tags: ['定语从句', 'which', 'that'],
    shortDescription: '只比较限制性定语从句中 which 和 that 的常见选择，不展开整个定语从句体系。',
  },
  {
    id: 'because-because-of',
    category: 'error-prone',
    title: 'because 与 because of',
    level: '基础',
    tags: ['原因', '连词', '介词短语'],
    shortDescription: 'because 后接句子，because of 后接名词、代词或动名词短语。',
  },
  {
    id: 'too-to',
    category: 'sentence-structure',
    title: 'too...to...',
    level: '基础',
    tags: ['句型', '结果', '否定含义'],
    shortDescription: '讲清 too + adj./adv. + to do 表示“太……而不能……”，以及和 enough to 的差异。',
  },
  {
    id: 'used-to-do',
    category: 'tense',
    title: 'used to do',
    level: '基础',
    tags: ['过去习惯', 'used to', '一般过去'],
    shortDescription: '表达过去常常做但现在不一定如此，避免和 be used to doing 混淆。',
  },
  {
    id: 'be-used-to-doing',
    category: 'error-prone',
    title: 'be used to doing',
    level: '高频易错',
    tags: ['习惯于', '介词 to', '动名词'],
    shortDescription: 'be used to 中的 to 是介词，后面接名词或 doing，表示“习惯于”。',
  },
  {
    id: 'stop-to-do-doing',
    category: 'nonfinite',
    title: 'stop to do 与 stop doing',
    level: '高频易错',
    tags: ['非谓语', '动名词', '不定式'],
    shortDescription: 'stop to do 是停下来去做另一件事，stop doing 是停止正在做的事。',
  },
  {
    id: 'wish-subjunctive-present',
    category: 'subjunctive',
    title: 'I wish + 一般过去时',
    level: '进阶',
    tags: ['wish', '虚拟', '现在相反'],
    shortDescription: '用 I wish + 一般过去时表达与现在事实相反的愿望，例如 I wish I knew.',
  },
  {
    id: 'should-have-done',
    category: 'modal',
    title: 'should have done',
    level: '进阶',
    tags: ['情态动词', '过去', '后悔'],
    shortDescription: '表达过去本该做却没做，常用于反思和建议。',
  },
  {
    id: 'there-be-agreement',
    category: 'agreement',
    title: 'there be 句型的主谓一致',
    level: '基础',
    tags: ['there be', '就近原则', '主谓一致'],
    shortDescription: 'there be 的 be 动词通常和后面最近的名词保持一致。',
  },
  {
    id: 'a-an-the-first-mention',
    category: 'article-preposition',
    title: '第一次提到用 a/an，第二次用 the',
    level: '基础',
    tags: ['冠词', '特指', '泛指'],
    shortDescription: '用一个具体规则解释 a/an 和 the 的最基础切换场景。',
  },
  {
    id: 'in-on-at-time',
    category: 'article-preposition',
    title: 'in/on/at 表示时间',
    level: '高频易错',
    tags: ['介词', '时间', '搭配'],
    shortDescription: '只讲时间搭配：at 具体时刻，on 具体日期/星期，in 月份/年份/较长时间。',
  },
]
