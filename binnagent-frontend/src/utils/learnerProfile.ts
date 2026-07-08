import type { LearnerProfile } from '@/types'

export const LEARNING_GOAL_OPTIONS = [
  { value: 'zhongkao', label: '通过中考' },
  { value: 'gaokao', label: '通过高考' },
  { value: 'cet4', label: '通过大学英语四级' },
  { value: 'cet6', label: '通过大学英语六级' },
  { value: 'ielts', label: '冲刺 IELTS 雅思' },
  { value: 'toefl', label: '冲刺 TOEFL 托福' },
  { value: 'postgraduate', label: '考研英语' },
  { value: 'daily_communication', label: '日常交流能力提升' },
] as const

export const CURRENT_LEVEL_OPTIONS = [
  { value: 'a1', label: 'A1 入门', description: '能理解少量高频词和简单句。' },
  { value: 'a2', label: 'A2 初级', description: '能完成简单日常表达和基础阅读。' },
  { value: 'b1', label: 'B1 中级', description: '能理解常见话题，能写较简单段落。' },
  { value: 'b2', label: 'B2 中高级', description: '能处理较复杂文本，能表达观点。' },
  { value: 'c1', label: 'C1 高级', description: '能理解复杂材料，表达较自然准确。' },
  { value: 'c2', label: 'C2 熟练', description: '接近熟练使用，关注精确度和风格。' },
] as const

export const LEVEL_STANDARD_NOTES = [
  {
    title: 'CEFR 是当前水平',
    detail: '系统保存 A1-C2，用它控制讲解深度、例句复杂度和练习难度。',
  },
  {
    title: '考试是学习目标',
    detail: '中考、高考、四六级、雅思和托福表示冲刺方向，不等同于当前水平。',
  },
  {
    title: '先粗选再修正',
    detail: '不确定时选接近的一档，后续可以根据练习表现和老师建议再调整。',
  },
] as const

export function learningGoalLabel(value?: string | null) {
  return LEARNING_GOAL_OPTIONS.find((item) => item.value === value)?.label ?? value ?? '未设置'
}

export function currentLevelLabel(value?: string | null) {
  return CURRENT_LEVEL_OPTIONS.find((item) => item.value === value)?.label ?? value ?? '未设置'
}

export function learnerBackground(profile?: LearnerProfile | null) {
  const target = learningGoalLabel(profile?.target_exam)
  const level = currentLevelLabel(profile?.current_level)
  return `学习目标：${target}；当前水平：${level}；母语为中文，喜欢中英结合、结构清楚、例句实用。请根据当前水平控制难度，并让例句、题型和反馈服务学习目标。`
}

export function promptWithLearnerProfile(prompt: string, profile?: LearnerProfile | null) {
  return `${prompt.trim()}\n\n学习者画像：${learnerBackground(profile)}`
}
