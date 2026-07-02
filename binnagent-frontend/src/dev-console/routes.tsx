export const devConsoleRoutes = [
  { id: 'learners', label: 'Learners', path: '/dev/learners' },
  { id: 'episodes', label: 'Recent Episodes', path: '/dev/episodes' },
  { id: 'memory', label: 'Memory Debug', path: '/dev/memory' },
  { id: 'tools', label: 'Tool Registry', path: '/dev/tools' },
  { id: 'tool-call-records', label: 'Tool Call Records', path: '/dev/tool-calls' },
  { id: 'evidence', label: 'Evidence Debug', path: '/dev/evidence' },
  { id: 'rag', label: 'RAG Debug', path: '/dev/rag' },
  { id: 'prompt', label: 'Prompt Debug', path: '/dev/prompts' },
  { id: 'verification', label: 'VerificationReport', path: '/dev/verification' },
  { id: 'simulation', label: 'Simulation Report', path: '/dev/simulation' },
] as const

export type DevConsoleRouteId = (typeof devConsoleRoutes)[number]['id']

export function findDevConsoleRoute(pathname: string) {
  if (pathname.startsWith('/runtime/episodes/')) {
    return devConsoleRoutes.find((route) => route.id === 'episodes') ?? devConsoleRoutes[0]
  }
  return devConsoleRoutes.find((route) => pathname.startsWith(route.path)) ?? devConsoleRoutes[0]
}
