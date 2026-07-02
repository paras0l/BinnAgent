export const DEBUG_TOKEN_STORAGE_KEY = 'BINNAGENT_DEBUG_TOKEN'

export function readDebugToken() {
  const storedToken = readStoredDebugToken()
  if (storedToken) return storedToken
  const envToken = import.meta.env.VITE_DEBUG_CONSOLE_TOKEN
  return typeof envToken === 'string' && envToken.trim() ? envToken.trim() : null
}

export function saveDebugToken(token: string) {
  if (typeof localStorage === 'undefined') return
  const nextToken = token.trim()
  if (nextToken) localStorage.setItem(DEBUG_TOKEN_STORAGE_KEY, nextToken)
  else localStorage.removeItem(DEBUG_TOKEN_STORAGE_KEY)
}

export function clearDebugToken() {
  if (typeof localStorage === 'undefined') return
  localStorage.removeItem(DEBUG_TOKEN_STORAGE_KEY)
}

export function hasDebugToken() {
  return readDebugToken() !== null
}

export function debugFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const token = readDebugToken()
  const headers = new Headers(init.headers)
  if (token) headers.set('X-Debug-Token', token)
  return fetch(input, { ...init, headers })
}

function readStoredDebugToken() {
  if (typeof localStorage === 'undefined') return null
  const value = localStorage.getItem(DEBUG_TOKEN_STORAGE_KEY)
  return value?.trim() || null
}
