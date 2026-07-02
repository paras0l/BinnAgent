export const devConsoleRoutes = [
  { id: 'memory', label: 'Memory Debug', path: '/dev/memory' },
  { id: 'episode', label: 'Episode Debug', path: '/dev/episodes' },
  { id: 'tools', label: 'Tool Calls', path: '/dev/tools' },
  { id: 'evidence', label: 'Evidence Debug', path: '/dev/evidence' },
  { id: 'rag', label: 'RAG Debug', path: '/dev/rag' },
  { id: 'prompt', label: 'Prompt Debug', path: '/dev/prompts' },
  { id: 'verification', label: 'VerificationReport', path: '/dev/verification' },
  { id: 'simulation', label: 'Simulation Report', path: '/dev/simulation' },
] as const

export type DevConsoleRouteId = (typeof devConsoleRoutes)[number]['id']

export function findDevConsoleRoute(pathname: string) {
  if (pathname.startsWith('/runtime/episodes/')) {
    return devConsoleRoutes.find((route) => route.id === 'episode') ?? devConsoleRoutes[0]
  }
  return devConsoleRoutes.find((route) => pathname.startsWith(route.path)) ?? devConsoleRoutes[0]
}
