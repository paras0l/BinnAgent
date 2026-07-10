import { describe, expect, it } from 'vitest'
import {
  DEFAULT_READER_CSS,
  DETAIL_DOCUMENT_CSP,
  sanitizeEmbeddedCss,
  sanitizeInlineStyle,
} from './safeHtmlDocument'

describe('safe HTML document styling policy', () => {
  it('preserves self-contained responsive styles', () => {
    const css = `
      .card { max-width: 820px; border-radius: 28px; box-shadow: 0 12px 40px #0001; }
      @media (max-width: 640px) { .card { padding: 24px 18px; } }
    `

    expect(sanitizeEmbeddedCss(css)).toContain('.card')
    expect(sanitizeEmbeddedCss(css)).toContain('@media')
  })

  it.each([
    '@import "https://example.com/theme.css";',
    '.card { background-image: url(https://example.com/track.png); }',
    '@font-face { font-family: remote; src: url(https://example.com/font.woff2); }',
    '.card { width: expression(alert(1)); }',
  ])('rejects styles that can load or execute external content', (css) => {
    expect(sanitizeEmbeddedCss(css)).toBe('')
  })

  it('keeps safe inline presentation and drops URL-backed inline styles', () => {
    expect(sanitizeInlineStyle('margin-top: 1rem; color: #475569')).toBe('margin-top: 1rem; color: #475569')
    expect(sanitizeInlineStyle('background: url(https://example.com/a.png)')).toBe('')
  })

  it('uses a network-denying CSP while allowing sanitized inline CSS', () => {
    expect(DETAIL_DOCUMENT_CSP).toContain("default-src 'none'")
    expect(DETAIL_DOCUMENT_CSP).toContain("style-src 'unsafe-inline'")
    expect(DETAIL_DOCUMENT_CSP).toContain("connect-src 'none'")
    expect(DETAIL_DOCUMENT_CSP).toContain("form-action 'none'")
  })

  it('keeps the fallback theme scoped to the reader body instead of every nested section', () => {
    expect(DEFAULT_READER_CSS).not.toContain('main, article, section')
    expect(DEFAULT_READER_CSS).toContain('width: min(100%, 880px)')
  })
})
