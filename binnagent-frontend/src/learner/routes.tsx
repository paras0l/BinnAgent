export const learnerRoutes = [
  { id: 'chat', label: 'AI对话', path: '/' },
  { id: 'daily', label: '今日学习', path: '/daily' },
  { id: 'knowledge', label: '教材', path: '/knowledge' },
  { id: 'practice', label: '练习', path: '/practice' },
  { id: 'review', label: '复习', path: '/review' },
  { id: 'explore', label: '探索', path: '/explore' },
  { id: 'progress', label: '学习进度', path: '/progress' },
  { id: 'profile', label: '个人设置', path: '/profile' },
] as const

export type LearnerRouteId = (typeof learnerRoutes)[number]['id']
