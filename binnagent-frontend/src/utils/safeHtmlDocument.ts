const MAX_EMBEDDED_CSS_LENGTH = 24_000

const UNSAFE_CSS_PATTERN = /(?:@import\b|@font-face\b|@namespace\b|@document\b|url\s*\(|image-set\s*\(|expression\s*\(|javascript\s*:|vbscript\s*:|behavior\s*:|-moz-binding\b)/i

const REMOVED_ELEMENTS = [
  'script',
  'iframe',
  'object',
  'embed',
  'form',
  'link',
  'meta',
  'base',
].join(', ')

export const DETAIL_DOCUMENT_CSP = [
  "default-src 'none'",
  "style-src 'unsafe-inline'",
  'img-src data:',
  "font-src 'none'",
  "connect-src 'none'",
  "media-src 'none'",
  "object-src 'none'",
  "frame-src 'none'",
  "form-action 'none'",
  "base-uri 'none'",
].join('; ')

export const DEFAULT_READER_CSS = `
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body {
    width: min(100%, 880px);
    margin: 0 auto;
    padding: 32px 28px 48px;
    font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    color: #0f172a;
    background: #ffffff;
    line-height: 1.75;
  }
  h1 { margin: 0 0 18px; font-size: 30px; line-height: 1.2; }
  h2 { margin: 28px 0 10px; font-size: 21px; line-height: 1.35; color: #3730a3; }
  h3 { margin: 22px 0 8px; font-size: 17px; line-height: 1.4; }
  p { margin: 9px 0; }
  ul, ol { padding-left: 24px; }
  li + li { margin-top: 6px; }
  blockquote, .example {
    margin: 14px 0;
    padding: 10px 14px;
    border-left: 4px solid #6366f1;
    background: #f8fafc;
  }
  code { padding: 2px 5px; border-radius: 5px; background: #eef2ff; color: #3730a3; }
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 8px; border: 1px solid #e2e8f0; }
  @media (max-width: 640px) {
    body { padding: 24px 18px 40px; }
    h1 { font-size: 26px; }
  }
`

const REDUCED_MOTION_CSS = `
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      scroll-behavior: auto !important;
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
    }
  }
`

export type SafeHtmlStyleMode = 'embedded' | 'fallback' | 'rejected'

export interface SafeHtmlDocument {
  bodyHtml: string
  srcDoc: string
  styleMode: SafeHtmlStyleMode
}

export function sanitizeEmbeddedCss(value: string) {
  const normalized = value.replace(/\/\*[\s\S]*?\*\//g, '').trim()
  if (!normalized || normalized.length > MAX_EMBEDDED_CSS_LENGTH || UNSAFE_CSS_PATTERN.test(normalized)) {
    return ''
  }
  return normalized
}

export function sanitizeInlineStyle(value: string) {
  const normalized = value.trim()
  if (!normalized || normalized.length > 2_000 || UNSAFE_CSS_PATTERN.test(normalized)) return ''
  return normalized
}

export function createSafeHtmlDocument(value: string): SafeHtmlDocument {
  if (!value.trim()) return { bodyHtml: '', srcDoc: '', styleMode: 'fallback' }

  const document = new DOMParser().parseFromString(value, 'text/html')
  const sourceStyleNodes = Array.from(document.querySelectorAll('style'))
  const sourceStyles = sourceStyleNodes.map((node) => node.textContent ?? '').join('\n')
  const embeddedCss = sanitizeEmbeddedCss(sourceStyles)
  const styleMode: SafeHtmlStyleMode = embeddedCss
    ? 'embedded'
    : sourceStyles.trim()
      ? 'rejected'
      : 'fallback'

  sourceStyleNodes.forEach((node) => node.remove())
  document.querySelectorAll(REMOVED_ELEMENTS).forEach((node) => node.remove())
  sanitizeElementAttributes(document)

  const bodyHtml = document.body.innerHTML
  if (!bodyHtml.trim()) return { bodyHtml: '', srcDoc: '', styleMode }

  const htmlClass = safeClassName(document.documentElement.getAttribute('class'))
  const bodyClass = safeClassName(document.body.getAttribute('class'))
  const bodyStyle = sanitizeInlineStyle(document.body.getAttribute('style') ?? '')
  const selectedCss = embeddedCss || DEFAULT_READER_CSS
  const htmlClassAttribute = htmlClass ? ` class="${escapeAttribute(htmlClass)}"` : ''
  const bodyClassAttribute = bodyClass ? ` class="${escapeAttribute(bodyClass)}"` : ''
  const bodyStyleAttribute = bodyStyle ? ` style="${escapeAttribute(bodyStyle)}"` : ''

  const srcDoc = `<!doctype html>
<html lang="zh-CN"${htmlClassAttribute}>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="Content-Security-Policy" content="${escapeAttribute(DETAIL_DOCUMENT_CSP)}">
    <style>${selectedCss}\n${REDUCED_MOTION_CSS}</style>
  </head>
  <body${bodyClassAttribute}${bodyStyleAttribute}>${bodyHtml}</body>
</html>`

  return { bodyHtml, srcDoc, styleMode }
}

function sanitizeElementAttributes(document: Document) {
  document.querySelectorAll('*').forEach((element) => {
    for (const attribute of Array.from(element.attributes)) {
      const name = attribute.name.toLowerCase()
      if (
        name.startsWith('on')
        || ['src', 'srcset', 'href', 'xlink:href', 'action', 'formaction', 'srcdoc'].includes(name)
      ) {
        element.removeAttribute(attribute.name)
        continue
      }
      if (name === 'style') {
        const safeStyle = sanitizeInlineStyle(attribute.value)
        if (safeStyle) element.setAttribute('style', safeStyle)
        else element.removeAttribute('style')
      }
    }
  })
}

function safeClassName(value: string | null) {
  if (!value) return ''
  return value.replace(/[^a-zA-Z0-9_\-\s:]/g, '').trim().slice(0, 500)
}

function escapeAttribute(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('"', '&quot;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
}
