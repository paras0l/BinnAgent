import { useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Dice5,
  Flame,
  Headphones,
  Mic2,
  Search,
  Sparkles,
  Volume2,
  Waves,
  X,
  Zap,
} from 'lucide-react'
import type { Learner, LearningProgressItem } from '@/types'

type PhonemeCategory = 'monophthong' | 'diphthong' | 'consonant'
type CategoryFilter = 'all' | PhonemeCategory

interface PronunciationPageProps {
  learner: Learner
}

interface PracticeExample {
  word: string
  phonetic: string
  highlight: string
  meaning: string
}

interface PhonemeCard {
  id: string
  category: PhonemeCategory
  symbol: string
  word: string
  wordPhonetic: string
  visual: string
  meaning: string
  phonemeParts: string[]
  wordParts: string[]
  highlightIndex: number
  tips: string
  commonMistake: string
  practiceExamples: PracticeExample[]
}

interface ProgressState {
  opened: string[]
  completed: string[]
  recent: string[]
}

type HighlightTarget = { kind: 'main' } | { kind: 'practice'; word: string } | null

const STORAGE_VERSION = 'v1'

const CATEGORY_META: Record<PhonemeCategory, { label: string; shortLabel: string; tone: string }> = {
  monophthong: {
    label: '单元音',
    shortLabel: '元音',
    tone: 'border-accent/40 bg-accent/10 text-foreground',
  },
  diphthong: {
    label: '双元音',
    shortLabel: '滑音',
    tone: 'border-warning/40 bg-warning/10 text-foreground',
  },
  consonant: {
    label: '辅音',
    shortLabel: '辅音',
    tone: 'border-primary/30 bg-primary/10 text-foreground',
  },
}

const RAW_PHONEMES: Array<
  Pick<PhonemeCard, 'category' | 'symbol' | 'word' | 'visual' | 'meaning'> & {
    focus?: string
    avoid?: string
  }
> = [
  { category: 'monophthong', symbol: '/iː/', word: 'see', visual: '👀', meaning: '看见', focus: '嘴角向两边拉，声音拉长，像微笑着说“衣”。', avoid: '不要读得太短，否则容易变成 /ɪ/。' },
  { category: 'monophthong', symbol: '/ɪ/', word: 'big', visual: '🐘', meaning: '大的', focus: '舌位比 /iː/ 放松，声音短促，嘴角不要用力拉开。', avoid: '不要拖成长音，也不要读成中文“衣”。' },
  { category: 'monophthong', symbol: '/e/', word: 'bed', visual: '🛏️', meaning: '床', focus: '嘴巴自然打开，舌前部抬起，声音短而清楚。', avoid: '不要滑成 /eɪ/，bed 不是 bayd。' },
  { category: 'monophthong', symbol: '/æ/', word: 'cat', visual: '🐱', meaning: '猫', focus: '嘴巴横向打开更大，舌尖靠近下齿，发出明亮的短音。', avoid: '不要读成 /e/，cat 和 ket 要能分开。' },
  { category: 'monophthong', symbol: '/ɑː/', word: 'car', visual: '🚗', meaning: '汽车', focus: '口腔打开，舌头放低靠后，声音稳定拉长。', avoid: '不要加中文“儿”尾音。' },
  { category: 'monophthong', symbol: '/ɒ/', word: 'hot', visual: '🔥', meaning: '热的', focus: '嘴唇略圆，舌位低后，声音短促有重量。', avoid: '不要读成长音 /ɔː/。' },
  { category: 'monophthong', symbol: '/ɔː/', word: 'door', visual: '🚪', meaning: '门', focus: '嘴唇圆起，声音拉长，保持稳定不要滑动。', avoid: '不要读得太短，door 的核心是长圆唇音。' },
  { category: 'monophthong', symbol: '/ʊ/', word: 'book', visual: '📖', meaning: '书', focus: '嘴唇轻轻圆起，舌后部抬起，短而放松。', avoid: '不要拉成长音 /uː/，book 不是 boook。' },
  { category: 'monophthong', symbol: '/uː/', word: 'moon', visual: '🌙', meaning: '月亮', focus: '嘴唇圆而向前，舌后部抬起，声音拉长。', avoid: '不要读得松散或太短。' },
  { category: 'monophthong', symbol: '/ʌ/', word: 'cup', visual: '☕', meaning: '杯子', focus: '嘴巴自然半开，舌中部放低，短促有弹性。', avoid: '不要读成 /ɑː/ 或中文“啊”。' },
  { category: 'monophthong', symbol: '/ɜː/', word: 'bird', visual: '🐦', meaning: '鸟', focus: '舌头居中略卷，声音拉长，英式里不要明显卷舌。', avoid: '不要读成 /ə/，bird 的元音更长更饱满。' },
  { category: 'monophthong', symbol: '/ə/', word: 'sofa', visual: '🛋️', meaning: '沙发', focus: '最放松的中央元音，轻轻带过，常出现在非重读音节。', avoid: '不要用力读重，它通常很弱。' },
  { category: 'diphthong', symbol: '/eɪ/', word: 'day', visual: '☀️', meaning: '日子', focus: '从 /e/ 平滑滑向 /ɪ/，前半段更清楚。', avoid: '不要读成单一的“诶”。' },
  { category: 'diphthong', symbol: '/aɪ/', word: 'my', visual: '👤', meaning: '我的', focus: '从张开的 /a/ 滑向 /ɪ/，像一个完整的弧线。', avoid: '不要只发中文“爱”的平音。' },
  { category: 'diphthong', symbol: '/ɔɪ/', word: 'boy', visual: '👦', meaning: '男孩', focus: '先圆唇发 /ɔ/，再滑向 /ɪ/，嘴型会变窄。', avoid: '不要把两段拆得太生硬。' },
  { category: 'diphthong', symbol: '/aʊ/', word: 'now', visual: '⏰', meaning: '现在', focus: '从开口 /a/ 滑向圆唇 /ʊ/，收尾要自然。', avoid: '不要读成单音“闹”。' },
  { category: 'diphthong', symbol: '/əʊ/', word: 'go', visual: '🚶', meaning: '去', focus: '从放松的 /ə/ 滑向 /ʊ/，英式收尾更圆。', avoid: '不要把开头读得过重。' },
  { category: 'diphthong', symbol: '/ɪə/', word: 'ear', visual: '👂', meaning: '耳朵', focus: '从短 /ɪ/ 滑到 /ə/，收尾放松。', avoid: '不要加很重的中文“儿”。' },
  { category: 'diphthong', symbol: '/eə/', word: 'air', visual: '🌬️', meaning: '空气', focus: '从 /e/ 滑向 /ə/，嘴巴逐渐放松。', avoid: '不要读成 /eɪ/。' },
  { category: 'diphthong', symbol: '/ʊə/', word: 'pure', visual: '💧', meaning: '纯净的', focus: '从 /ʊ/ 滑向 /ə/，先圆唇再放松。', avoid: '不要把后半段吞掉。' },
  { category: 'consonant', symbol: '/p/', word: 'pen', visual: '🖊️', meaning: '笔', focus: '双唇闭合后突然放气，清辅音声带不震动。', avoid: '不要在词尾额外加“呃”。' },
  { category: 'consonant', symbol: '/b/', word: 'bag', visual: '🎒', meaning: '包', focus: '双唇闭合后放开，声带震动，声音更厚。', avoid: '不要读成清辅音 /p/。' },
  { category: 'consonant', symbol: '/t/', word: 'top', visual: '🔝', meaning: '顶部', focus: '舌尖抵住齿龈后释放，清辅音短促。', avoid: '不要在词尾加中文元音。' },
  { category: 'consonant', symbol: '/d/', word: 'dog', visual: '🐕', meaning: '狗', focus: '舌尖抵住齿龈后释放，声带震动。', avoid: '不要读成 /t/。' },
  { category: 'consonant', symbol: '/k/', word: 'key', visual: '🔑', meaning: '钥匙', focus: '舌后部抵住软腭后放开，气流干净。', avoid: '不要加“可”的尾音。' },
  { category: 'consonant', symbol: '/g/', word: 'get', visual: '✋', meaning: '得到', focus: '舌后部抵住软腭后释放，声带震动。', avoid: '不要读成 /k/。' },
  { category: 'consonant', symbol: '/f/', word: 'fish', visual: '🐟', meaning: '鱼', focus: '上齿轻触下唇，让气流摩擦出来。', avoid: '不要双唇闭合读成 /p/。' },
  { category: 'consonant', symbol: '/v/', word: 'van', visual: '🚐', meaning: '货车', focus: '上齿轻触下唇，同时声带震动。', avoid: '不要读成 /w/ 或 /f/。' },
  { category: 'consonant', symbol: '/θ/', word: 'think', visual: '💭', meaning: '想', focus: '舌尖轻放上下齿之间，送气摩擦。', avoid: '不要读成 /s/。' },
  { category: 'consonant', symbol: '/ð/', word: 'this', visual: '👉', meaning: '这个', focus: '舌尖轻放齿间，声带震动。', avoid: '不要读成 /z/ 或 /d/。' },
  { category: 'consonant', symbol: '/s/', word: 'sun', visual: '☀️', meaning: '太阳', focus: '舌尖靠近齿龈，气流从窄缝摩擦，声带不震动。', avoid: '不要读成卷舌音。' },
  { category: 'consonant', symbol: '/z/', word: 'zoo', visual: '🦁', meaning: '动物园', focus: '保持 /s/ 的口型，加上声带震动。', avoid: '不要读成 /s/。' },
  { category: 'consonant', symbol: '/ʃ/', word: 'ship', visual: '🚢', meaning: '船', focus: '嘴唇略圆，舌面抬起，气流摩擦更柔。', avoid: '不要读成 /s/，ship 和 sip 要分开。' },
  { category: 'consonant', symbol: '/ʒ/', word: 'vision', visual: '👁️', meaning: '视觉', focus: '像 /ʃ/ 的浊音版本，声带震动。', avoid: '不要读得像中文“日”太重。' },
  { category: 'consonant', symbol: '/h/', word: 'hat', visual: '🎩', meaning: '帽子', focus: '喉部轻送气，后面元音决定口型。', avoid: '不要用力摩擦喉咙。' },
  { category: 'consonant', symbol: '/tʃ/', word: 'chip', visual: '🍟', meaning: '薯条/芯片', focus: '先堵住再摩擦释放，像 /t/ + /ʃ/ 连成一个音。', avoid: '不要拆成两个很远的音。' },
  { category: 'consonant', symbol: '/dʒ/', word: 'jet', visual: '✈️', meaning: '喷气机', focus: '先堵住再摩擦释放，并保持声带震动。', avoid: '不要读成 /tʃ/。' },
  { category: 'consonant', symbol: '/m/', word: 'man', visual: '👨', meaning: '男人', focus: '双唇闭合，气流从鼻腔出来，声带震动。', avoid: '不要张嘴太早。' },
  { category: 'consonant', symbol: '/n/', word: 'net', visual: '🥅', meaning: '网', focus: '舌尖抵住齿龈，气流从鼻腔出来。', avoid: '不要读成 /l/。' },
  { category: 'consonant', symbol: '/ŋ/', word: 'sing', visual: '🎤', meaning: '唱', focus: '舌后部抵住软腭，气流从鼻腔出来。', avoid: 'sing 词尾不要再加 /g/。' },
  { category: 'consonant', symbol: '/l/', word: 'leg', visual: '🦵', meaning: '腿', focus: '舌尖抵住上齿龈，气流从舌侧通过。', avoid: '不要读成 /n/ 或中文“了”。' },
  { category: 'consonant', symbol: '/r/', word: 'red', visual: '🔴', meaning: '红色', focus: '舌尖向后卷但不碰上腭，嘴唇略向前。', avoid: '不要读成中文拼音 r。' },
  { category: 'consonant', symbol: '/j/', word: 'yes', visual: '✅', meaning: '是', focus: '舌前部抬高，快速滑入后面的元音。', avoid: '不要读成 /dʒ/。' },
  { category: 'consonant', symbol: '/w/', word: 'wet', visual: '💧', meaning: '湿的', focus: '嘴唇圆起向前，再快速打开进入元音。', avoid: '不要读成 /v/。' },
  { category: 'consonant', symbol: '/ts/', word: 'cats', visual: '🐱🐱', meaning: '猫们', focus: '先 /t/ 后 /s/ 紧密释放，常出现在复数词尾。', avoid: '不要在后面加“呃”。' },
  { category: 'consonant', symbol: '/dz/', word: 'beds', visual: '🛏️🛏️', meaning: '床们', focus: '先 /d/ 后 /z/ 紧密释放，声带保持震动。', avoid: '不要读成 /ts/。' },
  { category: 'consonant', symbol: '/tr/', word: 'tree', visual: '🌳', meaning: '树', focus: '舌尖先做 /t/，马上卷向 /r/，形成紧凑组合。', avoid: '不要拆成 tu-ree。' },
  { category: 'consonant', symbol: '/dr/', word: 'dream', visual: '🌠', meaning: '梦', focus: '舌尖先做 /d/，马上卷向 /r/，声带震动。', avoid: '不要拆成 du-ream。' },
]

const PHONETIC_DETAILS: Record<
  string,
  Pick<PhonemeCard, 'wordPhonetic' | 'wordParts' | 'highlightIndex'>
> = {
  see: { wordPhonetic: '/siː/', wordParts: ['s', 'ee'], highlightIndex: 1 },
  big: { wordPhonetic: '/bɪɡ/', wordParts: ['b', 'i', 'g'], highlightIndex: 1 },
  bed: { wordPhonetic: '/bed/', wordParts: ['b', 'e', 'd'], highlightIndex: 1 },
  cat: { wordPhonetic: '/kæt/', wordParts: ['c', 'a', 't'], highlightIndex: 1 },
  car: { wordPhonetic: '/kɑː/', wordParts: ['c', 'ar'], highlightIndex: 1 },
  hot: { wordPhonetic: '/hɒt/', wordParts: ['h', 'o', 't'], highlightIndex: 1 },
  door: { wordPhonetic: '/dɔː/', wordParts: ['d', 'oor'], highlightIndex: 1 },
  book: { wordPhonetic: '/bʊk/', wordParts: ['b', 'oo', 'k'], highlightIndex: 1 },
  moon: { wordPhonetic: '/muːn/', wordParts: ['m', 'oo', 'n'], highlightIndex: 1 },
  cup: { wordPhonetic: '/kʌp/', wordParts: ['c', 'u', 'p'], highlightIndex: 1 },
  bird: { wordPhonetic: '/bɜːd/', wordParts: ['b', 'ir', 'd'], highlightIndex: 1 },
  sofa: { wordPhonetic: '/ˈsəʊfə/', wordParts: ['sof', 'a'], highlightIndex: 1 },
  day: { wordPhonetic: '/deɪ/', wordParts: ['d', 'ay'], highlightIndex: 1 },
  my: { wordPhonetic: '/maɪ/', wordParts: ['m', 'y'], highlightIndex: 1 },
  boy: { wordPhonetic: '/bɔɪ/', wordParts: ['b', 'oy'], highlightIndex: 1 },
  now: { wordPhonetic: '/naʊ/', wordParts: ['n', 'ow'], highlightIndex: 1 },
  go: { wordPhonetic: '/ɡəʊ/', wordParts: ['g', 'o'], highlightIndex: 1 },
  ear: { wordPhonetic: '/ɪə/', wordParts: ['ear'], highlightIndex: 0 },
  air: { wordPhonetic: '/eə/', wordParts: ['air'], highlightIndex: 0 },
  pure: { wordPhonetic: '/pjʊə/', wordParts: ['p', 'ure'], highlightIndex: 1 },
  pen: { wordPhonetic: '/pen/', wordParts: ['p', 'en'], highlightIndex: 0 },
  bag: { wordPhonetic: '/bæɡ/', wordParts: ['b', 'ag'], highlightIndex: 0 },
  top: { wordPhonetic: '/tɒp/', wordParts: ['t', 'op'], highlightIndex: 0 },
  dog: { wordPhonetic: '/dɒɡ/', wordParts: ['d', 'og'], highlightIndex: 0 },
  key: { wordPhonetic: '/kiː/', wordParts: ['k', 'ey'], highlightIndex: 0 },
  get: { wordPhonetic: '/ɡet/', wordParts: ['g', 'et'], highlightIndex: 0 },
  fish: { wordPhonetic: '/fɪʃ/', wordParts: ['f', 'ish'], highlightIndex: 0 },
  van: { wordPhonetic: '/væn/', wordParts: ['v', 'an'], highlightIndex: 0 },
  think: { wordPhonetic: '/θɪŋk/', wordParts: ['th', 'ink'], highlightIndex: 0 },
  this: { wordPhonetic: '/ðɪs/', wordParts: ['th', 'is'], highlightIndex: 0 },
  sun: { wordPhonetic: '/sʌn/', wordParts: ['s', 'un'], highlightIndex: 0 },
  zoo: { wordPhonetic: '/zuː/', wordParts: ['z', 'oo'], highlightIndex: 0 },
  ship: { wordPhonetic: '/ʃɪp/', wordParts: ['sh', 'ip'], highlightIndex: 0 },
  vision: { wordPhonetic: '/ˈvɪʒən/', wordParts: ['vi', 'si', 'on'], highlightIndex: 1 },
  hat: { wordPhonetic: '/hæt/', wordParts: ['h', 'at'], highlightIndex: 0 },
  chip: { wordPhonetic: '/tʃɪp/', wordParts: ['ch', 'ip'], highlightIndex: 0 },
  jet: { wordPhonetic: '/dʒet/', wordParts: ['j', 'et'], highlightIndex: 0 },
  man: { wordPhonetic: '/mæn/', wordParts: ['m', 'an'], highlightIndex: 0 },
  net: { wordPhonetic: '/net/', wordParts: ['n', 'et'], highlightIndex: 0 },
  sing: { wordPhonetic: '/sɪŋ/', wordParts: ['si', 'ng'], highlightIndex: 1 },
  leg: { wordPhonetic: '/leɡ/', wordParts: ['l', 'eg'], highlightIndex: 0 },
  red: { wordPhonetic: '/red/', wordParts: ['r', 'ed'], highlightIndex: 0 },
  yes: { wordPhonetic: '/jes/', wordParts: ['y', 'es'], highlightIndex: 0 },
  wet: { wordPhonetic: '/wet/', wordParts: ['w', 'et'], highlightIndex: 0 },
  cats: { wordPhonetic: '/kæts/', wordParts: ['ca', 'ts'], highlightIndex: 1 },
  beds: { wordPhonetic: '/bedz/', wordParts: ['be', 'ds'], highlightIndex: 1 },
  tree: { wordPhonetic: '/triː/', wordParts: ['tr', 'ee'], highlightIndex: 0 },
  dream: { wordPhonetic: '/driːm/', wordParts: ['dr', 'eam'], highlightIndex: 0 },
}

const PRACTICE_EXAMPLES: Record<string, PracticeExample[]> = {
  see: [
    { word: 'tree', phonetic: '/triː/', highlight: 'ee', meaning: '树' },
    { word: 'green', phonetic: '/ɡriːn/', highlight: 'ee', meaning: '绿色的' },
    { word: 'meet', phonetic: '/miːt/', highlight: 'ee', meaning: '见面' },
  ],
  big: [
    { word: 'sit', phonetic: '/sɪt/', highlight: 'i', meaning: '坐' },
    { word: 'fish', phonetic: '/fɪʃ/', highlight: 'i', meaning: '鱼' },
    { word: 'milk', phonetic: '/mɪlk/', highlight: 'i', meaning: '牛奶' },
  ],
  bed: [
    { word: 'red', phonetic: '/red/', highlight: 'e', meaning: '红色的' },
    { word: 'pen', phonetic: '/pen/', highlight: 'e', meaning: '笔' },
    { word: 'desk', phonetic: '/desk/', highlight: 'e', meaning: '书桌' },
  ],
  cat: [
    { word: 'hat', phonetic: '/hæt/', highlight: 'a', meaning: '帽子' },
    { word: 'map', phonetic: '/mæp/', highlight: 'a', meaning: '地图' },
    { word: 'apple', phonetic: '/ˈæpəl/', highlight: 'a', meaning: '苹果' },
  ],
  car: [
    { word: 'park', phonetic: '/pɑːk/', highlight: 'ar', meaning: '公园' },
    { word: 'star', phonetic: '/stɑː/', highlight: 'ar', meaning: '星星' },
    { word: 'father', phonetic: '/ˈfɑːðə/', highlight: 'a', meaning: '父亲' },
  ],
  hot: [
    { word: 'box', phonetic: '/bɒks/', highlight: 'o', meaning: '盒子' },
    { word: 'shop', phonetic: '/ʃɒp/', highlight: 'o', meaning: '商店' },
    { word: 'clock', phonetic: '/klɒk/', highlight: 'o', meaning: '钟' },
  ],
  door: [
    { word: 'four', phonetic: '/fɔː/', highlight: 'our', meaning: '四' },
    { word: 'more', phonetic: '/mɔː/', highlight: 'or', meaning: '更多' },
    { word: 'saw', phonetic: '/sɔː/', highlight: 'aw', meaning: '看见了' },
  ],
  book: [
    { word: 'good', phonetic: '/ɡʊd/', highlight: 'oo', meaning: '好的' },
    { word: 'foot', phonetic: '/fʊt/', highlight: 'oo', meaning: '脚' },
    { word: 'cook', phonetic: '/kʊk/', highlight: 'oo', meaning: '烹饪' },
  ],
  moon: [
    { word: 'food', phonetic: '/fuːd/', highlight: 'oo', meaning: '食物' },
    { word: 'blue', phonetic: '/bluː/', highlight: 'ue', meaning: '蓝色' },
    { word: 'school', phonetic: '/skuːl/', highlight: 'oo', meaning: '学校' },
  ],
  cup: [
    { word: 'sun', phonetic: '/sʌn/', highlight: 'u', meaning: '太阳' },
    { word: 'bus', phonetic: '/bʌs/', highlight: 'u', meaning: '公交车' },
    { word: 'love', phonetic: '/lʌv/', highlight: 'o', meaning: '爱' },
  ],
  bird: [
    { word: 'nurse', phonetic: '/nɜːs/', highlight: 'ur', meaning: '护士' },
    { word: 'word', phonetic: '/wɜːd/', highlight: 'or', meaning: '单词' },
    { word: 'learn', phonetic: '/lɜːn/', highlight: 'ear', meaning: '学习' },
  ],
  sofa: [
    { word: 'about', phonetic: '/əˈbaʊt/', highlight: 'a', meaning: '关于' },
    { word: 'banana', phonetic: '/bəˈnɑːnə/', highlight: 'a', meaning: '香蕉' },
    { word: 'teacher', phonetic: '/ˈtiːtʃə/', highlight: 'er', meaning: '老师' },
  ],
  day: [
    { word: 'make', phonetic: '/meɪk/', highlight: 'a', meaning: '制作' },
    { word: 'rain', phonetic: '/reɪn/', highlight: 'ai', meaning: '雨' },
    { word: 'play', phonetic: '/pleɪ/', highlight: 'ay', meaning: '玩' },
  ],
  my: [
    { word: 'time', phonetic: '/taɪm/', highlight: 'i', meaning: '时间' },
    { word: 'light', phonetic: '/laɪt/', highlight: 'igh', meaning: '光' },
    { word: 'bike', phonetic: '/baɪk/', highlight: 'i', meaning: '自行车' },
  ],
  boy: [
    { word: 'toy', phonetic: '/tɔɪ/', highlight: 'oy', meaning: '玩具' },
    { word: 'coin', phonetic: '/kɔɪn/', highlight: 'oi', meaning: '硬币' },
    { word: 'voice', phonetic: '/vɔɪs/', highlight: 'oi', meaning: '声音' },
  ],
  now: [
    { word: 'house', phonetic: '/haʊs/', highlight: 'ou', meaning: '房子' },
    { word: 'brown', phonetic: '/braʊn/', highlight: 'ow', meaning: '棕色' },
    { word: 'mouth', phonetic: '/maʊθ/', highlight: 'ou', meaning: '嘴' },
  ],
  go: [
    { word: 'home', phonetic: '/həʊm/', highlight: 'o', meaning: '家' },
    { word: 'boat', phonetic: '/bəʊt/', highlight: 'oa', meaning: '船' },
    { word: 'show', phonetic: '/ʃəʊ/', highlight: 'ow', meaning: '展示' },
  ],
  ear: [
    { word: 'near', phonetic: '/nɪə/', highlight: 'ear', meaning: '近的' },
    { word: 'here', phonetic: '/hɪə/', highlight: 'ere', meaning: '这里' },
    { word: 'beer', phonetic: '/bɪə/', highlight: 'eer', meaning: '啤酒' },
  ],
  air: [
    { word: 'chair', phonetic: '/tʃeə/', highlight: 'air', meaning: '椅子' },
    { word: 'care', phonetic: '/keə/', highlight: 'are', meaning: '关心' },
    { word: 'there', phonetic: '/ðeə/', highlight: 'ere', meaning: '那里' },
  ],
  pure: [
    { word: 'cure', phonetic: '/kjʊə/', highlight: 'ure', meaning: '治愈' },
    { word: 'tour', phonetic: '/tʊə/', highlight: 'our', meaning: '旅行' },
    { word: 'secure', phonetic: '/sɪˈkjʊə/', highlight: 'ure', meaning: '安全的' },
  ],
  pen: [
    { word: 'park', phonetic: '/pɑːk/', highlight: 'p', meaning: '公园' },
    { word: 'paper', phonetic: '/ˈpeɪpə/', highlight: 'p', meaning: '纸' },
    { word: 'happy', phonetic: '/ˈhæpi/', highlight: 'pp', meaning: '开心的' },
  ],
  bag: [
    { word: 'book', phonetic: '/bʊk/', highlight: 'b', meaning: '书' },
    { word: 'baby', phonetic: '/ˈbeɪbi/', highlight: 'b', meaning: '婴儿' },
    { word: 'table', phonetic: '/ˈteɪbəl/', highlight: 'b', meaning: '桌子' },
  ],
  top: [
    { word: 'tea', phonetic: '/tiː/', highlight: 't', meaning: '茶' },
    { word: 'time', phonetic: '/taɪm/', highlight: 't', meaning: '时间' },
    { word: 'water', phonetic: '/ˈwɔːtə/', highlight: 't', meaning: '水' },
  ],
  dog: [
    { word: 'day', phonetic: '/deɪ/', highlight: 'd', meaning: '日子' },
    { word: 'desk', phonetic: '/desk/', highlight: 'd', meaning: '书桌' },
    { word: 'ready', phonetic: '/ˈredi/', highlight: 'd', meaning: '准备好的' },
  ],
  key: [
    { word: 'cat', phonetic: '/kæt/', highlight: 'c', meaning: '猫' },
    { word: 'cake', phonetic: '/keɪk/', highlight: 'c', meaning: '蛋糕' },
    { word: 'school', phonetic: '/skuːl/', highlight: 'ch', meaning: '学校' },
  ],
  get: [
    { word: 'go', phonetic: '/ɡəʊ/', highlight: 'g', meaning: '去' },
    { word: 'green', phonetic: '/ɡriːn/', highlight: 'g', meaning: '绿色的' },
    { word: 'again', phonetic: '/əˈɡen/', highlight: 'g', meaning: '再次' },
  ],
  fish: [
    { word: 'food', phonetic: '/fuːd/', highlight: 'f', meaning: '食物' },
    { word: 'leaf', phonetic: '/liːf/', highlight: 'f', meaning: '叶子' },
    { word: 'photo', phonetic: '/ˈfəʊtəʊ/', highlight: 'ph', meaning: '照片' },
  ],
  van: [
    { word: 'voice', phonetic: '/vɔɪs/', highlight: 'v', meaning: '声音' },
    { word: 'very', phonetic: '/ˈveri/', highlight: 'v', meaning: '非常' },
    { word: 'seven', phonetic: '/ˈsevən/', highlight: 'v', meaning: '七' },
  ],
  think: [
    { word: 'three', phonetic: '/θriː/', highlight: 'th', meaning: '三' },
    { word: 'thank', phonetic: '/θæŋk/', highlight: 'th', meaning: '感谢' },
    { word: 'mouth', phonetic: '/maʊθ/', highlight: 'th', meaning: '嘴' },
  ],
  this: [
    { word: 'that', phonetic: '/ðæt/', highlight: 'th', meaning: '那个' },
    { word: 'mother', phonetic: '/ˈmʌðə/', highlight: 'th', meaning: '母亲' },
    { word: 'weather', phonetic: '/ˈweðə/', highlight: 'th', meaning: '天气' },
  ],
  sun: [
    { word: 'sit', phonetic: '/sɪt/', highlight: 's', meaning: '坐' },
    { word: 'bus', phonetic: '/bʌs/', highlight: 's', meaning: '公交车' },
    { word: 'city', phonetic: '/ˈsɪti/', highlight: 'c', meaning: '城市' },
  ],
  zoo: [
    { word: 'zero', phonetic: '/ˈzɪərəʊ/', highlight: 'z', meaning: '零' },
    { word: 'busy', phonetic: '/ˈbɪzi/', highlight: 's', meaning: '忙的' },
    { word: 'music', phonetic: '/ˈmjuːzɪk/', highlight: 's', meaning: '音乐' },
  ],
  ship: [
    { word: 'she', phonetic: '/ʃiː/', highlight: 'sh', meaning: '她' },
    { word: 'shop', phonetic: '/ʃɒp/', highlight: 'sh', meaning: '商店' },
    { word: 'station', phonetic: '/ˈsteɪʃən/', highlight: 'ti', meaning: '车站' },
  ],
  vision: [
    { word: 'usually', phonetic: '/ˈjuːʒuəli/', highlight: 'su', meaning: '通常' },
    { word: 'measure', phonetic: '/ˈmeʒə/', highlight: 'su', meaning: '测量' },
    { word: 'pleasure', phonetic: '/ˈpleʒə/', highlight: 'su', meaning: '愉快' },
  ],
  hat: [
    { word: 'home', phonetic: '/həʊm/', highlight: 'h', meaning: '家' },
    { word: 'happy', phonetic: '/ˈhæpi/', highlight: 'h', meaning: '开心的' },
    { word: 'behind', phonetic: '/bɪˈhaɪnd/', highlight: 'h', meaning: '在后面' },
  ],
  chip: [
    { word: 'chair', phonetic: '/tʃeə/', highlight: 'ch', meaning: '椅子' },
    { word: 'watch', phonetic: '/wɒtʃ/', highlight: 'tch', meaning: '手表' },
    { word: 'teacher', phonetic: '/ˈtiːtʃə/', highlight: 'ch', meaning: '老师' },
  ],
  jet: [
    { word: 'jump', phonetic: '/dʒʌmp/', highlight: 'j', meaning: '跳' },
    { word: 'orange', phonetic: '/ˈɒrɪndʒ/', highlight: 'ge', meaning: '橙子' },
    { word: 'bridge', phonetic: '/brɪdʒ/', highlight: 'dge', meaning: '桥' },
  ],
  man: [
    { word: 'moon', phonetic: '/muːn/', highlight: 'm', meaning: '月亮' },
    { word: 'summer', phonetic: '/ˈsʌmə/', highlight: 'mm', meaning: '夏天' },
    { word: 'team', phonetic: '/tiːm/', highlight: 'm', meaning: '团队' },
  ],
  net: [
    { word: 'name', phonetic: '/neɪm/', highlight: 'n', meaning: '名字' },
    { word: 'sunny', phonetic: '/ˈsʌni/', highlight: 'nn', meaning: '晴朗的' },
    { word: 'green', phonetic: '/ɡriːn/', highlight: 'n', meaning: '绿色的' },
  ],
  sing: [
    { word: 'song', phonetic: '/sɒŋ/', highlight: 'ng', meaning: '歌曲' },
    { word: 'long', phonetic: '/lɒŋ/', highlight: 'ng', meaning: '长的' },
    { word: 'bank', phonetic: '/bæŋk/', highlight: 'n', meaning: '银行' },
  ],
  leg: [
    { word: 'light', phonetic: '/laɪt/', highlight: 'l', meaning: '光' },
    { word: 'blue', phonetic: '/bluː/', highlight: 'l', meaning: '蓝色' },
    { word: 'hello', phonetic: '/həˈləʊ/', highlight: 'll', meaning: '你好' },
  ],
  red: [
    { word: 'rain', phonetic: '/reɪn/', highlight: 'r', meaning: '雨' },
    { word: 'green', phonetic: '/ɡriːn/', highlight: 'r', meaning: '绿色的' },
    { word: 'sorry', phonetic: '/ˈsɒri/', highlight: 'rr', meaning: '抱歉' },
  ],
  yes: [
    { word: 'you', phonetic: '/juː/', highlight: 'y', meaning: '你' },
    { word: 'yellow', phonetic: '/ˈjeləʊ/', highlight: 'y', meaning: '黄色' },
    { word: 'cute', phonetic: '/kjuːt/', highlight: 'u', meaning: '可爱的' },
  ],
  wet: [
    { word: 'we', phonetic: '/wiː/', highlight: 'w', meaning: '我们' },
    { word: 'water', phonetic: '/ˈwɔːtə/', highlight: 'w', meaning: '水' },
    { word: 'quick', phonetic: '/kwɪk/', highlight: 'u', meaning: '快的' },
  ],
  cats: [
    { word: 'hats', phonetic: '/hæts/', highlight: 'ts', meaning: '帽子们' },
    { word: 'boats', phonetic: '/bəʊts/', highlight: 'ts', meaning: '船们' },
    { word: 'lights', phonetic: '/laɪts/', highlight: 'ts', meaning: '灯们' },
  ],
  beds: [
    { word: 'cards', phonetic: '/kɑːdz/', highlight: 'ds', meaning: '卡片们' },
    { word: 'words', phonetic: '/wɜːdz/', highlight: 'ds', meaning: '单词们' },
    { word: 'friends', phonetic: '/frendz/', highlight: 'ds', meaning: '朋友们' },
  ],
  tree: [
    { word: 'train', phonetic: '/treɪn/', highlight: 'tr', meaning: '火车' },
    { word: 'try', phonetic: '/traɪ/', highlight: 'tr', meaning: '尝试' },
    { word: 'street', phonetic: '/striːt/', highlight: 'tr', meaning: '街道' },
  ],
  dream: [
    { word: 'drink', phonetic: '/drɪŋk/', highlight: 'dr', meaning: '喝' },
    { word: 'drive', phonetic: '/draɪv/', highlight: 'dr', meaning: '驾驶' },
    { word: 'children', phonetic: '/ˈtʃɪldrən/', highlight: 'dr', meaning: '孩子们' },
  ],
}

const PHONEMES: PhonemeCard[] = RAW_PHONEMES.map((item) => {
  const plainSymbol = item.symbol.replaceAll('/', '')
  const details = PHONETIC_DETAILS[item.word] ?? {
    wordPhonetic: item.symbol,
    wordParts: [item.word],
    highlightIndex: 0,
  }
  return {
    ...item,
    ...details,
    id: `${item.category}-${plainSymbol}`,
    phonemeParts: [item.symbol],
    tips: item.focus ?? '观察口型，先慢速发准目标音，再把它放回例词里。',
    commonMistake: item.avoid ?? '初学时容易用中文近似音替代，练习时要听清长度、口型和声带震动。',
    practiceExamples: PRACTICE_EXAMPLES[item.word] ?? [],
  }
})

const FILTERS: Array<{ id: CategoryFilter; label: string }> = [
  { id: 'all', label: '全部' },
  { id: 'monophthong', label: '单元音' },
  { id: 'diphthong', label: '双元音' },
  { id: 'consonant', label: '辅音' },
]

const SKILL_SECTIONS = [
  {
    id: 'connected-speech',
    icon: Waves,
    title: '连读弱读',
    description: '把单词连成自然语流，重点听 function words 的变轻。',
    examples: [
      { label: '辅音 + 元音连读', phrase: 'pick it up', note: '像 pick-it-up，词尾辅音会带到下一个元音前。' },
      { label: 'to 弱读', phrase: 'want to go', note: '自然语速里 to 常弱成 /tə/，不要每个词都重读。' },
      { label: 'of / and 弱读', phrase: 'a cup of tea and milk', note: 'of 和 and 通常轻读，内容词 tea、milk 更突出。' },
    ],
  },
  {
    id: 'stress',
    icon: Zap,
    title: '重音对比',
    description: '重音决定听感层级，也会改变词性或句子重点。',
    examples: [
      { label: '词重音', phrase: 'REcord / reCORD', note: '名词 record 常前重，动词 record 常后重。' },
      { label: '句重音', phrase: "I didn't say he stole it.", note: '重读不同词，暗示的纠正对象也不同。' },
      { label: '信息焦点', phrase: 'She bought a NEW phone.', note: '重读 new，强调不是旧手机或普通手机。' },
    ],
  },
  {
    id: 'intonation',
    icon: Sparkles,
    title: '语调',
    description: '语调像句子的表情，帮助表达确定、疑问、选择和情绪。',
    examples: [
      { label: '陈述下降', phrase: 'I finished the book.', note: '结尾下降，表达完整确定。' },
      { label: '一般疑问上升', phrase: 'Are you ready?', note: '结尾上扬，表示等待回答。' },
      { label: '选择疑问', phrase: 'Tea or coffee?', note: '前项上扬，最后一项下降。' },
    ],
  },
]

function loadProgress(storageKey: string): ProgressState {
  try {
    const raw = localStorage.getItem(storageKey)
    if (!raw) return { opened: [], completed: [], recent: [] }
    const parsed = JSON.parse(raw) as Partial<ProgressState>
    return {
      opened: Array.isArray(parsed.opened) ? parsed.opened : [],
      completed: Array.isArray(parsed.completed) ? parsed.completed : [],
      recent: Array.isArray(parsed.recent) ? parsed.recent : [],
    }
  } catch {
    return { opened: [], completed: [], recent: [] }
  }
}

function uniqueList(items: string[]) {
  return Array.from(new Set(items))
}

function progressFromBackend(items: LearningProgressItem[]): ProgressState {
  const opened = items
    .filter((item) => item.opened_count > 0)
    .map((item) => item.item_id)
  const completed = items
    .filter((item) => item.status === 'learned')
    .map((item) => item.item_id)
  const recent = [...items]
    .filter((item) => item.last_opened_at)
    .sort((a, b) => Date.parse(b.last_opened_at ?? '') - Date.parse(a.last_opened_at ?? ''))
    .map((item) => item.item_id)
    .slice(0, 8)

  return {
    opened: uniqueList(opened),
    completed: uniqueList(completed),
    recent: uniqueList(recent),
  }
}

export function PronunciationPage({ learner }: PronunciationPageProps) {
  const storageKey = `binnPronunciation:${STORAGE_VERSION}:${learner.id}`
  const [filter, setFilter] = useState<CategoryFilter>('all')
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [progress, setProgress] = useState<ProgressState>(() => loadProgress(storageKey))
  const [activeHighlight, setActiveHighlight] = useState<HighlightTarget>(null)
  const [speechMessage, setSpeechMessage] = useState('')
  const [progressMessage, setProgressMessage] = useState('')

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(progress))
  }, [progress, storageKey])

  useEffect(() => {
    let isMounted = true
    fetch(`/api/learners/${learner.id}/learning-progress?skill=pronunciation`)
      .then((response) => {
        if (!response.ok) throw new Error('Failed to load pronunciation progress')
        return response.json() as Promise<LearningProgressItem[]>
      })
      .then((items) => {
        if (!isMounted || items.length === 0) return
        setProgress(progressFromBackend(items))
        setProgressMessage('')
      })
      .catch((err) => {
        console.error('Pronunciation progress load error:', err)
        if (isMounted) setProgressMessage('发音进度暂时无法同步，已使用本地进度。')
      })
    return () => {
      isMounted = false
    }
  }, [learner.id])

  const selected = PHONEMES.find((item) => item.id === selectedId) ?? null

  const visiblePhonemes = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return PHONEMES.filter((item) => filter === 'all' || item.category === filter).filter((item) => {
      if (!normalizedQuery) return true
      return [item.symbol, item.word, item.wordPhonetic, item.meaning, item.visual, CATEGORY_META[item.category].label]
        .join(' ')
        .toLowerCase()
        .includes(normalizedQuery)
    })
  }, [filter, query])

  const completedCount = progress.completed.length
  const openedCount = progress.opened.length
  const todayPlan = PHONEMES.filter((item) => !progress.completed.includes(item.id)).slice(0, 5)
  const selectedIndex = selected ? PHONEMES.findIndex((item) => item.id === selected.id) : -1

  const rememberOpened = (phoneme: PhonemeCard) => {
    setSelectedId(phoneme.id)
    setProgress((current) => ({
      opened: uniqueList([phoneme.id, ...current.opened]),
      completed: current.completed,
      recent: uniqueList([phoneme.id, ...current.recent]).slice(0, 8),
    }))
    void persistPronunciationProgress(phoneme, { mark_opened: true })
  }

  const handleSpeak = (text: string, target: HighlightTarget = null) => {
    if (!('speechSynthesis' in window)) {
      setSpeechMessage('当前浏览器不支持语音播放，可以先按提示自己跟读。')
      return
    }

    window.speechSynthesis.cancel()
    setSpeechMessage('')
    setActiveHighlight(target)

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'en-US'
    utterance.rate = 0.78
    utterance.onend = () => window.setTimeout(() => setActiveHighlight(null), 260)
    utterance.onerror = () => {
      setActiveHighlight(null)
      setSpeechMessage('语音播放暂时不可用，可以继续使用文字提示练习。')
    }
    window.speechSynthesis.speak(utterance)
  }

  const completeSelected = () => {
    if (!selected) return
    setProgress((current) => ({
      opened: uniqueList([selected.id, ...current.opened]),
      completed: uniqueList([selected.id, ...current.completed]),
      recent: uniqueList([selected.id, ...current.recent]).slice(0, 8),
    }))
    void persistPronunciationProgress(selected, { mark_learned: true })
  }

  async function persistPronunciationProgress(
    phoneme: PhonemeCard,
    payload: { mark_opened?: boolean; mark_learned?: boolean }
  ) {
    try {
      const response = await fetch(
        `/api/learners/${learner.id}/learning-progress/pronunciation/${encodeURIComponent(phoneme.id)}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: `${phoneme.symbol} ${phoneme.word}`,
            metadata: {
              category: phoneme.category,
              symbol: phoneme.symbol,
              word: phoneme.word,
              wordPhonetic: phoneme.wordPhonetic,
              meaning: phoneme.meaning,
            },
            ...payload,
          }),
        }
      )
      if (!response.ok) throw new Error('Failed to persist pronunciation progress')
      setProgressMessage('')
    } catch (err) {
      console.error('Pronunciation progress save error:', err)
      setProgressMessage('发音进度暂时无法同步，已保存在本地。')
    }
  }

  const goToOffset = (offset: number) => {
    if (!selected) return
    const nextIndex = (selectedIndex + offset + PHONEMES.length) % PHONEMES.length
    rememberOpened(PHONEMES[nextIndex])
  }

  const practiceToday = () => {
    const next = todayPlan[0] ?? PHONEMES[0]
    setFilter('all')
    setQuery('')
    rememberOpened(next)
  }

  const randomPractice = () => {
    const next = PHONEMES[Math.floor(Math.random() * PHONEMES.length)]
    rememberOpened(next)
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 p-4 sm:p-6">
      <section className="overflow-hidden rounded-xl border bg-card">
        <div className="grid gap-5 p-5 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <div className="flex items-center gap-2 text-primary">
              <Mic2 className="h-5 w-5" />
              <span className="text-sm font-semibold">音标训练</span>
            </div>
            <h1 className="mt-2 text-2xl font-bold text-foreground">用图像联想记住 48 个常见音标</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              先用卡片建立声音和画面的连接，再进入详情跟读目标音素。每天完成 5 个，口语底盘会一点点稳起来。
            </p>
            {progressMessage && <p className="mt-2 text-xs text-warning">{progressMessage}</p>}
          </div>
          <div className="grid grid-cols-3 gap-2 text-center sm:min-w-96">
            <StatTile label="音标总数" value={PHONEMES.length} />
            <StatTile label="已练习" value={completedCount} />
            <StatTile label="已打开" value={openedCount} />
          </div>
        </div>

        <div className="grid gap-3 border-t bg-muted/30 p-4 md:grid-cols-[1fr_auto_auto] md:items-center">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="w-full rounded-lg border bg-background py-2 pl-9 pr-3 text-sm outline-none transition-colors focus:border-primary"
              placeholder="搜索 /iː/、cat、猫..."
            />
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1 md:pb-0">
            {FILTERS.map((item) => (
              <button
                key={item.id}
                onClick={() => setFilter(item.id)}
                className={`shrink-0 rounded-lg border px-3 py-2 text-sm transition-colors ${
                  filter === item.id
                    ? 'border-primary bg-primary/10 font-medium text-primary'
                    : 'text-muted-foreground hover:bg-background hover:text-foreground'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <button
              onClick={practiceToday}
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 md:flex-none"
            >
              <Flame className="h-4 w-4" />
              今日 5 个
            </button>
            <button
              onClick={randomPractice}
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-background md:flex-none"
            >
              <Dice5 className="h-4 w-4" />
              随机练
            </button>
          </div>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6">
            {visiblePhonemes.map((item) => (
              <button
                key={item.id}
                onClick={() => rememberOpened(item)}
                className={`group flex min-h-40 flex-col rounded-xl border bg-card p-4 text-left transition-all hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-sm ${
                  selected?.id === item.id ? 'border-primary ring-2 ring-primary/15' : ''
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-4xl leading-none" aria-hidden="true">
                    {item.visual}
                  </span>
                  {progress.completed.includes(item.id) ? (
                    <CheckCircle2 className="h-5 w-5 shrink-0 text-success" />
                  ) : (
                    <span className={`rounded-md border px-2 py-1 text-xs ${CATEGORY_META[item.category].tone}`}>
                      {CATEGORY_META[item.category].shortLabel}
                    </span>
                  )}
                </div>
                <div className="mt-auto">
                  <p className="text-2xl font-bold text-foreground">{item.symbol}</p>
                  <p className="mt-1 text-sm font-semibold text-foreground">{item.word}</p>
                  <p className="mt-1 text-xs font-medium text-primary">{item.wordPhonetic}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{item.meaning}</p>
                </div>
              </button>
            ))}
          </div>

          {visiblePhonemes.length === 0 && (
            <div className="rounded-xl border bg-card p-8 text-center text-sm text-muted-foreground">
              没有找到匹配的音标，换个关键词试试。
            </div>
          )}

          <PronunciationSkillSections onSpeak={handleSpeak} />
        </section>

        {selected ? (
          <PhonemeDetailPanel
            activeHighlight={activeHighlight}
            isCompleted={progress.completed.includes(selected.id)}
            phoneme={selected}
            speechMessage={speechMessage}
            onClose={() => setSelectedId(null)}
            onComplete={completeSelected}
            onNext={() => goToOffset(1)}
            onPrevious={() => goToOffset(-1)}
            onSpeak={() => handleSpeak(selected.word, { kind: 'main' })}
            onSpeakPractice={(example) => handleSpeak(example.word, { kind: 'practice', word: example.word })}
          />
        ) : (
          <aside className="hidden self-start rounded-xl border bg-card p-5 shadow-sm xl:block">
            <div className="flex size-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Mic2 className="h-6 w-6" />
            </div>
            <h2 className="mt-4 text-lg font-bold text-foreground">点击一张音标卡片开始</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              详情里会显示例词、画面联想、播放按钮、音素高亮、发音要点和跟读练习。
            </p>
          </aside>
        )}
      </div>
    </div>
  )
}

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border bg-background p-3">
      <p className="text-2xl font-bold text-foreground">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{label}</p>
    </div>
  )
}

function PhonemeDetailPanel({
  activeHighlight,
  isCompleted,
  phoneme,
  speechMessage,
  onClose,
  onComplete,
  onNext,
  onPrevious,
  onSpeak,
  onSpeakPractice,
}: {
  activeHighlight: HighlightTarget
  isCompleted: boolean
  phoneme: PhonemeCard
  speechMessage: string
  onClose: () => void
  onComplete: () => void
  onNext: () => void
  onPrevious: () => void
  onSpeak: () => void
  onSpeakPractice: (example: PracticeExample) => void
}) {
  return (
    <aside className="sticky top-20 self-start rounded-xl border bg-card shadow-sm max-xl:fixed max-xl:inset-x-3 max-xl:bottom-3 max-xl:z-40 max-xl:max-h-[86vh] max-xl:overflow-y-auto">
      <div className="flex items-center justify-between border-b p-4">
        <div>
          <p className="text-xs text-muted-foreground">{CATEGORY_META[phoneme.category].label}</p>
          <h2 className="text-lg font-bold text-foreground">音标详情</h2>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground xl:hidden"
          title="关闭详情"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="space-y-4 p-4">
        <div className="rounded-xl border bg-muted/30 p-5 text-center">
          <div className="text-7xl leading-none" aria-hidden="true">
            {phoneme.visual}
          </div>
          <p className="mt-3 text-4xl font-bold text-foreground">{phoneme.symbol}</p>
          <p className="mt-2 text-base font-semibold text-foreground">{phoneme.word}</p>
          <p className="mt-1 text-sm font-medium text-primary">{phoneme.wordPhonetic}</p>
          <p className="text-sm text-muted-foreground">{phoneme.meaning}</p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={onSpeak}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <Volume2 className="h-4 w-4" />
            听一听
          </button>
          <button
            onClick={onComplete}
            className={`inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              isCompleted
                ? 'bg-success/10 text-success'
                : 'border text-foreground hover:bg-muted'
            }`}
          >
            <CheckCircle2 className="h-4 w-4" />
            {isCompleted ? '已完成' : '完成练习'}
          </button>
        </div>

        {speechMessage && (
          <div className="rounded-lg border border-warning/30 bg-warning/5 px-3 py-2 text-sm text-foreground">
            {speechMessage}
          </div>
        )}

        <div className="rounded-xl border p-4">
          <p className="text-sm font-semibold text-foreground">音素高亮</p>
          <InlineSegmentedWord
            className="mt-3 block text-4xl font-bold tracking-normal text-foreground"
            highlightIndex={phoneme.highlightIndex}
            isActive={activeHighlight?.kind === 'main'}
            parts={phoneme.wordParts}
          />
        </div>

        <InfoBlock title="发音要点" text={phoneme.tips} />
        <InfoBlock title="常见误区" text={phoneme.commonMistake} />
        <PracticeExamples
          activeHighlight={activeHighlight}
          examples={phoneme.practiceExamples}
          onSpeak={onSpeakPractice}
        />

        <div className="grid grid-cols-2 gap-3 pt-1">
          <button
            onClick={onPrevious}
            className="inline-flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
          >
            <ArrowLeft className="h-4 w-4" />
            上一个
          </button>
          <button
            onClick={onNext}
            className="inline-flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
          >
            下一个
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  )
}

function InfoBlock({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-xl border p-4">
      <p className="text-sm font-semibold text-foreground">{title}</p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{text}</p>
    </div>
  )
}

function InlineSegmentedWord({
  className = '',
  highlightIndex,
  isActive,
  parts,
}: {
  className?: string
  highlightIndex: number
  isActive: boolean
  parts: string[]
}) {
  return (
    <span className={className}>
      {parts.map((part, index) => (
        <span
          key={`${part}-${index}`}
          className={`rounded-sm transition-colors ${
            isActive && index === highlightIndex ? 'bg-accent px-0.5 text-foreground' : ''
          }`}
        >
          {part}
        </span>
      ))}
    </span>
  )
}

function HighlightedPracticeWord({
  example,
  isActive,
}: {
  example: PracticeExample
  isActive: boolean
}) {
  const lowerWord = example.word.toLowerCase()
  const lowerHighlight = example.highlight.toLowerCase()
  const start = lowerWord.indexOf(lowerHighlight)

  if (start < 0) {
    return <span>{example.word}</span>
  }

  const before = example.word.slice(0, start)
  const target = example.word.slice(start, start + example.highlight.length)
  const after = example.word.slice(start + example.highlight.length)

  return (
    <span>
      {before}
      <span className={`rounded-sm transition-colors ${isActive ? 'bg-accent px-0.5 text-foreground' : ''}`}>
        {target}
      </span>
      {after}
    </span>
  )
}

function PracticeExamples({
  activeHighlight,
  examples,
  onSpeak,
}: {
  activeHighlight: HighlightTarget
  examples: PracticeExample[]
  onSpeak: (example: PracticeExample) => void
}) {
  return (
    <div className="rounded-xl border p-4">
      <p className="text-sm font-semibold text-foreground">再练几个</p>
      <div className="mt-3 space-y-2">
        {examples.map((example) => {
          const isActive = activeHighlight?.kind === 'practice' && activeHighlight.word === example.word
          return (
            <div
              key={example.word}
              className="flex items-center justify-between gap-3 rounded-lg bg-muted/30 px-3 py-2"
            >
              <div className="min-w-0">
                <p className="text-base font-bold text-foreground">
                  <HighlightedPracticeWord example={example} isActive={isActive} />
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {example.phonetic} · {example.meaning}
                </p>
              </div>
              <button
                onClick={() => onSpeak(example)}
                className="shrink-0 rounded-lg p-2 text-muted-foreground transition-colors hover:bg-background hover:text-primary"
                title="播放例词"
              >
                <Volume2 className="h-4 w-4" />
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function PronunciationSkillSections({ onSpeak }: { onSpeak: (text: string) => void }) {
  return (
    <section className="grid gap-4 lg:grid-cols-3">
      {SKILL_SECTIONS.map((section) => {
        const Icon = section.icon
        return (
          <article key={section.id} className="rounded-xl border bg-card p-4">
            <div className="flex items-start gap-3">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Icon className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-foreground">{section.title}</h3>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">{section.description}</p>
              </div>
            </div>
            <div className="mt-4 space-y-3">
              {section.examples.map((example) => (
                <div key={`${section.id}-${example.phrase}`} className="rounded-lg border bg-muted/20 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-medium text-primary">{example.label}</p>
                      <p className="mt-1 text-sm font-bold text-foreground">{example.phrase}</p>
                    </div>
                    <button
                      onClick={() => onSpeak(example.phrase)}
                      className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-background hover:text-primary"
                      title="播放例句"
                    >
                      <Headphones className="h-4 w-4" />
                    </button>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">{example.note}</p>
                </div>
              ))}
            </div>
          </article>
        )
      })}
    </section>
  )
}
