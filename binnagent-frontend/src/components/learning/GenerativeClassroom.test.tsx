import { renderToString } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { GenerativeClassroom, type ClassroomPlan } from './GenerativeClassroom'

const PLAN: ClassroomPlan = {
  schema_version: '1.0',
  classroom_id: 'starter-1:v1',
  generation_mode: 'llm_generated',
  source: { id: 'source-1', title: '人教版七年级上册', edition: '2024' },
  unit: { id: 'unit-1', title: 'Starter Unit 1', subtitle: 'Hello!', ordinal: 1 },
  hero: {
    eyebrow: 'PEP 2024 · AI ORGANIZED CLASS',
    title: 'Starter Unit 1 · Hello!',
    mission: '完成问候与自我介绍。',
    coach_message: '先理解，再开口。',
  },
  phases: [
    { id: 'launch', kind: 'briefing', title: '入场 · 明确任务', minutes: 2, icon: 'sparkles' },
    { id: 'notice', kind: 'cards', title: '发现 · 激活语言', minutes: 5, icon: 'scan' },
    { id: 'grammar', kind: 'grammar', title: '语法 · 看懂并会用', minutes: 6, icon: 'braces' },
    { id: 'listen', kind: 'audio', title: '听辨 · 教材原声', minutes: 6, icon: 'headphones' },
    { id: 'textbook', kind: 'textbook', title: '教材 · 完成原题', minutes: 8, icon: 'book-open' },
    { id: 'practice', kind: 'challenge', title: '诊断 · AI 挑战', minutes: 5, icon: 'target' },
    { id: 'reflect', kind: 'reflection', title: '收束 · 学习复盘', minutes: 2, icon: 'flag' },
  ],
  language_cards: [
    { id: 'hello', front: 'hello', back: '你好；向同学问好', accent: 'violet' },
    { id: 'name', front: 'name', back: '名字；介绍自己', accent: 'cyan' },
    { id: 'class', front: 'class', back: '班级；说出班级', accent: 'amber' },
  ],
  focus: { grammar: 'be 动词', question: 'How do you greet a classmate?' },
  grammar_lab: {
    title: '用合适的问候开启并结束对话',
    can_do: '我能根据时间和交际阶段选择问候语。',
    rule: '时间、初次见面和结束对话分别有常用表达。',
    forms: ['Good morning.', 'Nice to meet you.', 'Goodbye.'],
    examples: [{ en: "Good morning. I'm Emma.", zh: '早上好。我是埃玛。' }],
    common_error: '所有场景都只说 Hello。',
    checks: [
      { id: 'g1', prompt: '早晨问候？', options: ['Good morning.', 'Goodbye.', 'Good night.'], answer: 'Good morning.', explanation: '上午问候用 Good morning。' },
      { id: 'g2', prompt: '初次见面？', options: ['Nice to meet you.', 'See you.', 'Good night.'], answer: 'Nice to meet you.', explanation: '初次见面用 Nice to meet you。' },
      { id: 'g3', prompt: '结束对话？', options: ['Goodbye.', 'Good morning.', 'How are you?'], answer: 'Goodbye.', explanation: '结束时使用 Goodbye。' },
    ],
    transfer_prompt: '写一个三句迷你对话。',
  },
  audio: { track: '01-Starter-Unit-1-Hello.mp3', timeline_available: true },
  vocabulary: { core_count: 24, primary_review_count: 48, core: [], primary_review: [] },
  textbook_tasks: [{ id: 'task-a', title: 'Section A 教材任务', instruction: '完成原题。', asset: 'task.webp', printed_page: 1, pdf_page: 10, response_type: 'text' }],
  completion: { xp: 60, memory_message: '同步到掌握度、学习记忆与复习计划。' },
  resume: null,
}

describe('GenerativeClassroom', () => {
  it('renders the focused lesson route, mission, and completion standard', () => {
    const html = renderToString(
      <GenerativeClassroom
        learnerId="learner-1"
        plan={PLAN}
        lesson={null}
        prompt=""
        options={[]}
        answer=""
        isSubmitting={false}
        feedback={null}
        boosterCount={0}
        onAnswerChange={vi.fn()}
        onSubmit={vi.fn()}
        onOpenBoosters={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(html).toContain('今日教材课')
    expect(html).toContain('入场 · 明确任务')
    expect(html).toContain('听辨 · 教材原声')
    expect(html).toContain('语法 · 看懂并会用')
    expect(html).toContain('教材 · 完成原题')
    expect(html).toContain('诊断 · AI 挑战')
    expect(html).toContain('完成问候与自我介绍。')
    expect(html).toContain('完成标准')
    expect(html).toContain('收起课堂路径')
  })

  it('offers a recovery action when the scored challenge is unavailable', () => {
    const html = renderToString(
      <GenerativeClassroom
        learnerId="learner-1"
        plan={{ ...PLAN, resume: { current_phase_id: 'practice', completed_phase_ids: ['launch', 'notice', 'grammar', 'listen', 'textbook'], flipped_card_ids: [], listened_cue_ids: [], status: 'in_progress', updated_at: null } }}
        lesson={null}
        prompt=""
        options={[]}
        answer=""
        isSubmitting={false}
        feedback={null}
        boosterCount={0}
        onAnswerChange={vi.fn()}
        onSubmit={vi.fn()}
        onPrepareChallenge={vi.fn()}
        onOpenBoosters={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(html).toContain('评分挑战还没准备好')
    expect(html).toContain('重新准备挑战')
    expect(html).toContain('不需要重做前面的步骤')
  })

  it('renders an explicit grammar rule, checks, and transfer task', () => {
    const html = renderToString(
      <GenerativeClassroom
        learnerId="learner-1"
        plan={{ ...PLAN, resume: { current_phase_id: 'grammar', completed_phase_ids: ['launch', 'notice'], flipped_card_ids: [], listened_cue_ids: [], status: 'in_progress', updated_at: null } }}
        lesson={null}
        prompt=""
        options={[]}
        answer=""
        isSubmitting={false}
        feedback={null}
        boosterCount={0}
        onAnswerChange={vi.fn()}
        onSubmit={vi.fn()}
        onOpenBoosters={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(html).toContain('当前句型')
    expect(html).toContain('先抓住规则')
    expect(html).toContain('立即辨析')
    expect(html).toContain('自己用出来')
    expect(html).toContain('用合适的问候开启并结束对话')
  })

  it('renders the original textbook task and AI coaching workspace', () => {
    const html = renderToString(
      <GenerativeClassroom
        learnerId="learner-1"
        plan={{ ...PLAN, resume: { current_phase_id: 'textbook', completed_phase_ids: ['launch', 'notice', 'listen'], flipped_card_ids: [], listened_cue_ids: [], status: 'in_progress', updated_at: null } }}
        lesson={null}
        prompt=""
        options={[]}
        answer=""
        isSubmitting={false}
        feedback={null}
        boosterCount={0}
        onAnswerChange={vi.fn()}
        onSubmit={vi.fn()}
        onOpenBoosters={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(html).toContain('Section A 教材任务')
    expect(html).toContain('教材第 1 页原题')
    expect(html).toContain('做题提示')
    expect(html).toContain('按题号记录答案')
    expect(html).toContain('/classroom/textbook-task/task.webp')
  })
})
