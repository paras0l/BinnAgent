export type ShadowingSelfRating = 'smooth' | 'okay' | 'needs-practice'

export interface ShadowingItem {
  id: string
  sentence: string
  meaning: string
  chunks: string[]
  stressWords: string[]
  intonation: string
  practiceTip: string
}

export const SHADOWING_ITEMS: ShadowingItem[] = [
  {
    id: 'shadowing-001',
    sentence: 'Could you give me a minute to think about it?',
    meaning: '你能给我一分钟想一想吗？',
    chunks: ['Could you give me', 'a minute', 'to think about it?'],
    stressWords: ['give', 'minute', 'think'],
    intonation: '礼貌请求，前半句自然上扬，结尾轻轻下降。',
    practiceTip: '把 Could you 连成 /kudʒu/，不要逐词停顿；minute 后短暂停一下。',
  },
  {
    id: 'shadowing-002',
    sentence: 'I used to be nervous, but now I feel more confident.',
    meaning: '我以前会紧张，但现在更自信了。',
    chunks: ['I used to be nervous,', 'but now', 'I feel more confident.'],
    stressWords: ['used', 'nervous', 'now', 'confident'],
    intonation: 'but 前略降，now 后把语气重新抬起来，结尾下降。',
    practiceTip: 'used to 读成 /juːstə/，把 but now 作为转折重心读清楚。',
  },
  {
    id: 'shadowing-003',
    sentence: 'The best way to improve is to practice a little every day.',
    meaning: '最好的提升方法是每天练一点。',
    chunks: ['The best way to improve', 'is to practice', 'a little every day.'],
    stressWords: ['best', 'improve', 'practice', 'every'],
    intonation: '说明观点时语气稳定，improve 后略停，结尾坚定下降。',
    practiceTip: 'best way 的 /t/ 可轻读，practice a 连在一起，保持节奏均匀。',
  },
  {
    id: 'shadowing-004',
    sentence: 'I am not sure if I agree with that point.',
    meaning: '我不确定自己是否同意那个观点。',
    chunks: ['I am not sure', 'if I agree', 'with that point.'],
    stressWords: ['not', 'sure', 'agree', 'point'],
    intonation: '表达保留意见，not sure 放慢一点，结尾自然下降。',
    practiceTip: 'sure 后稍停，agree 前不要抢拍；with that point 读成一个短语。',
  },
  {
    id: 'shadowing-005',
    sentence: 'This topic is important because it affects our daily life.',
    meaning: '这个话题很重要，因为它影响我们的日常生活。',
    chunks: ['This topic is important', 'because it affects', 'our daily life.'],
    stressWords: ['topic', 'important', 'affects', 'daily life'],
    intonation: '原因解释，important 后停顿，because 后保持向前推进。',
    practiceTip: 'because it 可连读，affects 的重音在第二音节；daily life 两词都要清楚。',
  },
  {
    id: 'shadowing-006',
    sentence: 'What I mean is that we need a clearer plan.',
    meaning: '我的意思是，我们需要一个更清晰的计划。',
    chunks: ['What I mean is', 'that we need', 'a clearer plan.'],
    stressWords: ['mean', 'need', 'clearer', 'plan'],
    intonation: '澄清想法，What I mean is 轻读，核心落在 clearer plan。',
    practiceTip: 'mean is 可顺滑连读；clearer plan 前稍微放慢，像在强调结论。',
  },
  {
    id: 'shadowing-007',
    sentence: 'It sounds simple, but it is actually quite challenging.',
    meaning: '这听起来简单，但实际上很有挑战。',
    chunks: ['It sounds simple,', 'but it is actually', 'quite challenging.'],
    stressWords: ['sounds', 'simple', 'actually', 'challenging'],
    intonation: 'simple 后下降，but 后重新抬起，challenging 结尾下降。',
    practiceTip: 'actually 可弱化成 /ˈæktʃuəli/；quite challenging 作为重音组读饱满。',
  },
  {
    id: 'shadowing-008',
    sentence: 'I would rather focus on quality than speed.',
    meaning: '我宁愿关注质量，而不是速度。',
    chunks: ['I would rather focus', 'on quality', 'than speed.'],
    stressWords: ['rather', 'focus', 'quality', 'speed'],
    intonation: '比较取舍，quality 稍高，speed 收低形成对比。',
    practiceTip: 'would rather 可弱读；quality 和 speed 都要重，但 speed 更短促。',
  },
  {
    id: 'shadowing-009',
    sentence: 'Can you explain it in a simpler way?',
    meaning: '你能用更简单的方式解释一下吗？',
    chunks: ['Can you explain it', 'in a simpler way?'],
    stressWords: ['explain', 'simpler', 'way'],
    intonation: '一般疑问句，句尾自然上扬，语气保持礼貌。',
    practiceTip: 'Can you 可连成 /kənju/；simpler way 连读时不要吞掉 /r/ 的过渡。',
  },
  {
    id: 'shadowing-010',
    sentence: 'At first, I thought it was impossible.',
    meaning: '一开始，我以为这不可能。',
    chunks: ['At first,', 'I thought', 'it was impossible.'],
    stressWords: ['first', 'thought', 'impossible'],
    intonation: '叙述过去判断，At first 后停顿，impossible 逐步下降。',
    practiceTip: 'thought it 中 /t/ 轻触即可；impossible 重音在第二音节。',
  },
  {
    id: 'shadowing-011',
    sentence: 'The more I listen, the easier it becomes.',
    meaning: '我听得越多，它就变得越容易。',
    chunks: ['The more I listen,', 'the easier', 'it becomes.'],
    stressWords: ['more', 'listen', 'easier', 'becomes'],
    intonation: 'the more... the easier... 是平行结构，两半节奏要对应。',
    practiceTip: '两段都用三拍读法：more-I-listen，easier-it-becomes。',
  },
  {
    id: 'shadowing-012',
    sentence: 'Let me try again, but this time a bit slower.',
    meaning: '让我再试一次，但这次稍微慢一点。',
    chunks: ['Let me try again,', 'but this time', 'a bit slower.'],
    stressWords: ['try', 'again', 'this time', 'slower'],
    intonation: '自我修正，again 后下降，this time 重新强调，slower 放慢。',
    practiceTip: 'Let me 弱读成 /lemi/；a bit slower 的 bit 不要读得太重。',
  },
]

export const SHADOWING_RATING_LABELS: Record<ShadowingSelfRating, string> = {
  smooth: '顺畅',
  okay: '一般',
  'needs-practice': '需要再练',
}
