export const learnerRoutes = [
  { id: 'chat', label: 'AI对话', path: '/' },
  { id: 'explore', label: '探索', path: '/explore' },
  { id: 'dashboard', label: '学习中心', path: '/dashboard' },
] as const

export type LearnerRouteId = (typeof learnerRoutes)[number]['id']
