const worker = {
  async fetch(request, env) {
    const response = await env.ASSETS.fetch(request)
    if (response.status !== 404) return withSecurityHeaders(response)

    const acceptsHtml = request.headers.get('accept')?.includes('text/html')
    if (!acceptsHtml || request.method !== 'GET') return response

    const indexRequest = new Request(new URL('/index.html', request.url), request)
    return withSecurityHeaders(await env.ASSETS.fetch(indexRequest))
  },
}

function withSecurityHeaders(response) {
  const headers = new Headers(response.headers)
  headers.set('X-Content-Type-Options', 'nosniff')
  headers.set('Referrer-Policy', 'strict-origin-when-cross-origin')
  headers.set('Permissions-Policy', 'camera=(), geolocation=(), microphone=()')
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  })
}

export default worker
