import type { DashboardSummary, LearnerProfile } from '@/types'

export function buildTodaySteps(summary: DashboardSummary, learningTrack: LearnerProfile['learning_track'] = 'reading') {
  const isReadingTrack = learningTrack === 'reading'
  return [
    {
      title: summary.stats.today_reviews > 0 ? `复习 ${summary.stats.today_reviews} 个到期词汇` : '快速热身',
      description: summary.stats.today_reviews > 0 ? '先遮住答案主动回忆，再根据熟练度评分。' : '用一两个已学词汇进入状态。',
      action: 'review',
      badge: summary.stats.today_reviews > 0 ? '建议优先' : '完成',
      state: summary.stats.today_reviews === 0 ? 'done' : 'next',
    },
    {
      title: isReadingTrack ? '阅读今天的个性化短文' : '开始今天的教材课',
      description: isReadingTrack
        ? '先完整读一遍抓主旨和作者态度，不被生词打断。'
        : '完成一组新词判断、一个句型、一段教材原声和一页原题，系统会保存每一步证据。',
      action: isReadingTrack ? 'reading' : 'lesson',
      badge: summary.today_goal.completed >= summary.today_goal.total ? '已完成' : '主线',
      state: summary.today_goal.completed >= summary.today_goal.total ? 'done' : 'next',
    },
    {
      title: isReadingTrack ? '精读排盲并完成理解检查' : '完成一道检查题',
      description: isReadingTrack
        ? '回看重点句，确认生词、语法结构和理解偏差，再记录纠错依据。'
        : '用教材语境确认今天学到的内容能不能用出来。',
      action: isReadingTrack ? 'reading' : 'lesson',
      badge: isReadingTrack ? '排盲' : '收口',
      state: 'next',
    },
    {
      title: '与 AI 完成一次对话',
      description: '围绕今天学到的内容说一说、问一问，把知识用进真实表达。',
      action: 'chat',
      badge: summary.stats.today_ai_conversations > 0 ? '已完成' : '对话',
      state: summary.stats.today_ai_conversations > 0 ? 'done' : 'next',
    },
  ] as const
}
