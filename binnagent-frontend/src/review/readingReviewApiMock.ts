import { countEnglishWords, splitReadingSentences, type ReadingMaterialHistoryItem } from '@/data/readingWorkshop'
import { READING_REVIEW_LEARNER, READING_REVIEW_MATERIAL } from './readingReviewFixtures'

const jsonHeaders = { 'Content-Type': 'application/json; charset=utf-8' }
const originalFetch = window.fetch.bind(window)
let materialSequence = 1
let attemptSequence = 1
let materials: ReadingMaterialHistoryItem[] = [READING_REVIEW_MATERIAL]

export function installReadingReviewApiMock() {
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof Request ? input : null
    const url = new URL(request?.url ?? String(input), window.location.origin)
    if (!url.pathname.startsWith('/api/')) return originalFetch(input, init)

    const method = (init?.method ?? request?.method ?? 'GET').toUpperCase()
    const body = await readJsonBody(request, init)
    const learnerRoot = `/api/learners/${READING_REVIEW_LEARNER.id}`

    if (url.pathname === `${learnerRoot}/reading-workshop/materials` && method === 'GET') {
      return json(materials)
    }

    if (url.pathname === `${learnerRoot}/reading-workshop/materials` && method === 'POST') {
      const saved = createMaterial(body)
      materials = [saved, ...materials.filter((item) => item.id !== saved.id)].slice(0, 20)
      return json(saved, 201)
    }

    if (url.pathname === `${learnerRoot}/reading-workshop/generated-materials` && method === 'POST') {
      const generated = createGeneratedMaterial(body)
      materials = [generated, ...materials].slice(0, 20)
      return json({ material: generated, generation_context: generated.generation_context }, 201)
    }

    if (
      url.pathname.startsWith(`${learnerRoot}/reading-workshop/materials/`)
      && url.pathname.endsWith('/complete')
      && method === 'POST'
    ) {
      const materialId = decodeURIComponent(url.pathname.split('/').at(-2) ?? READING_REVIEW_MATERIAL.id)
      return json({
        material_id: materialId,
        attempt_id: `review-attempt-${attemptSequence++}`,
        reading_value: 18,
        message: '团队验收示例中的阅读证据已记录。',
      })
    }

    if (url.pathname === '/api/reading-workshop/title-suggestion' && method === 'POST') {
      const text = stringValue(body.text)
      const sentences = splitReadingSentences(text)
      return json({
        is_complete: text.trim().length >= 40,
        suggested_title: text.trim().length >= 40 ? 'A Closer Look at the Passage' : null,
        reason: text.trim().length >= 40 ? '内容已形成完整主题。' : '还需要更多正文。',
        word_count: countEnglishWords(text),
        sentence_count: sentences.length,
      })
    }

    if (url.pathname === '/api/chat/send' && method === 'POST') {
      const question = stringValue(body.message)
      return json({
        reply: `可以先回到原文找证据：这段材料用 “However” 引出维护城市树木的限制。你的问题是“${question.slice(0, 80)}”，建议先判断它在问主旨、逻辑关系，还是句子主干。`,
        thread_id: 'review-reading-coach-thread',
      })
    }

    if (url.pathname === `${learnerRoot}/reading-workshop/selection-translation` && method === 'POST') {
      const selection = stringValue(body.selection)
      return json({
        translation: reviewTranslation(selection),
        context_note: '这是验收环境中的上下文释义，可继续验证选词、取消与重选行为。',
        source: 'model',
        build_version: 'sites-review-v1',
      })
    }

    if (url.pathname.endsWith('/exercise-attempts/summary') && method === 'GET') {
      return json({
        total: 0,
        correct: 0,
        incorrect: 0,
        accuracy: 0,
        last_attempt_at: null,
        last_result: null,
        needs_review: false,
        learning_status: 'not_started',
      })
    }

    if (url.pathname.endsWith('/exercise-attempts') && method === 'POST') return json(body, 201)
    if (url.pathname.endsWith('/exercise-attempts') && method === 'GET') return json([])
    if (url.pathname.endsWith('/exercises') && method === 'GET') return json([])

    return json({ detail: '该接口不在本次精读与泛读团队验收范围内。' }, 404)
  }
}

async function readJsonBody(request: Request | null, init?: RequestInit): Promise<Record<string, unknown>> {
  try {
    const raw = typeof init?.body === 'string'
      ? init.body
      : request
        ? await request.clone().text()
        : ''
    return raw ? JSON.parse(raw) as Record<string, unknown> : {}
  } catch {
    return {}
  }
}

function createMaterial(body: Record<string, unknown>): ReadingMaterialHistoryItem {
  const text = stringValue(body.text)
  const title = stringValue(body.title) || null
  const existing = materials.find((item) => item.text === text && item.title === title)
  const now = new Date().toISOString()
  return {
    id: existing?.id ?? `review-material-${materialSequence++}`,
    learner_id: READING_REVIEW_LEARNER.id,
    curriculum_node_id: null,
    title,
    text,
    level: body.level === 'junior' || body.level === 'cet4' || body.level === 'cet6' ? body.level : 'general',
    goal: body.goal === 'intensive' || body.goal === 'extensive' ? body.goal : 'mixed',
    material_type: body.material_type === 'dialogue' ? 'dialogue' : 'passage',
    word_count: countEnglishWords(text),
    sentence_count: splitReadingSentences(text).length,
    source: 'team_review_fixture',
    generation_context: null,
    created_at: existing?.created_at ?? now,
    updated_at: now,
  }
}

function createGeneratedMaterial(body: Record<string, unknown>): ReadingMaterialHistoryItem {
  const topic = stringValue(body.topic) || 'everyday discovery'
  const now = new Date().toISOString()
  const text = `A small community project can change how people understand ${topic}. Volunteers first observe a local problem, and then they collect simple evidence before choosing an action. Although early results may be limited, the group keeps a clear record so that later decisions are easier to explain. This habit turns a general interest into a practical learning process.`
  return {
    id: `review-generated-${materialSequence++}`,
    learner_id: READING_REVIEW_LEARNER.id,
    curriculum_node_id: null,
    title: `A Practical View of ${titleCase(topic)}`,
    text,
    level: 'general',
    goal: 'mixed',
    material_type: 'passage',
    word_count: countEnglishWords(text),
    sentence_count: splitReadingSentences(text).length,
    source: 'unit_llm_generation',
    generation_context: {
      source_title: 'BinnAgent 个性化阅读验收',
      unit_title: topic,
      grammar_focus: ['让步状语从句', '连接词与句间逻辑'],
      vocabulary_used: ['observe', 'evidence', 'practical'],
      level_rationale: '按团队验收学习者的 B1 水平生成。',
      confidence: 1,
    },
    created_at: now,
    updated_at: now,
  }
}

function reviewTranslation(selection: string) {
  const normalized = selection.toLowerCase()
  if (normalized.includes('urban forest')) return '城市森林；城市中由树木与相关生态空间构成的系统。'
  if (normalized.includes('overflow')) return '溢出；这里指暴雨时排水系统超出承载能力。'
  if (normalized.includes('shade')) return '阴凉、遮荫；这里指树冠为街道降低日晒。'
  return `“${selection}”在本句中的含义需要结合前后逻辑理解。`
}

function stringValue(value: unknown) {
  return typeof value === 'string' ? value.trim() : ''
}

function titleCase(value: string) {
  return value.replace(/\b[a-z]/g, (letter) => letter.toUpperCase())
}

function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status, headers: jsonHeaders })
}
