const STORAGE_KEY = 'binnGrammarPendingPrompt'
const FILLED_ATTR = 'data-binn-grammar-filled'
const RETURN_BUTTON_ID = 'binn-grammar-return-button'

window.addEventListener('message', (event) => {
  if (event.source !== window) return
  const data = event.data
  if (!data || data.type !== 'BINN_GRAMMAR_PROMPT_READY') return

  chrome.runtime.sendMessage(
    {
      type: 'BINN_GRAMMAR_PROMPT_READY',
      prompt: data.prompt,
      topicTitle: data.topicTitle,
      sourceUrl: data.sourceUrl,
      targetUrl: data.targetUrl,
    },
    () => {
      window.postMessage({ type: 'BINN_GRAMMAR_EXTENSION_ACK' }, window.location.origin)
    }
  )
})

chrome.runtime.onMessage.addListener((message) => {
  if (!message || message.type !== 'BINN_GRAMMAR_HTML_RETURNED') return
  window.postMessage(
    {
      type: 'BINN_GRAMMAR_HTML_RETURNED',
      html: message.html,
    },
    window.location.origin
  )
})

chrome.storage.local.get(STORAGE_KEY, (items) => {
  const pending = items[STORAGE_KEY]
  if (!pending || !pending.prompt || !isCurrentTarget(pending.targetUrl)) return
  installReturnButton()
  tryFillPrompt(pending.prompt)
})

function isCurrentTarget(targetUrl) {
  if (!targetUrl) return false
  try {
    const target = new URL(targetUrl)
    return window.location.hostname === target.hostname || window.location.hostname.endsWith(`.${target.hostname}`)
  } catch {
    return false
  }
}

function tryFillPrompt(prompt) {
  let attempts = 0
  const timer = window.setInterval(() => {
    attempts += 1
    const input = findInput()
    if (input && fillInput(input, prompt)) {
      window.clearInterval(timer)
      input.setAttribute(FILLED_ATTR, 'true')
    }
    if (attempts >= 30) window.clearInterval(timer)
  }, 500)
}

function findInput() {
  const selectors = [
    'textarea:not([readonly]):not([disabled])',
    '[contenteditable="true"]',
    '[role="textbox"]',
    'div[contenteditable="true"]',
  ]
  const candidates = selectors.flatMap((selector) => Array.from(document.querySelectorAll(selector)))
  return candidates
    .filter((element) => !element.getAttribute(FILLED_ATTR))
    .filter(isVisible)
    .sort((a, b) => scoreInput(b) - scoreInput(a))[0]
}

function isVisible(element) {
  const rect = element.getBoundingClientRect()
  const style = window.getComputedStyle(element)
  return rect.width > 120 && rect.height > 24 && style.visibility !== 'hidden' && style.display !== 'none'
}

function scoreInput(element) {
  const rect = element.getBoundingClientRect()
  const lower = `${element.getAttribute('placeholder') || ''} ${element.getAttribute('aria-label') || ''}`.toLowerCase()
  let score = rect.width + rect.height
  if (lower.includes('message') || lower.includes('send') || lower.includes('输入') || lower.includes('问')) score += 500
  if (rect.bottom > window.innerHeight * 0.55) score += 300
  return score
}

function fillInput(element, prompt) {
  element.focus()
  if (element instanceof HTMLTextAreaElement || element instanceof HTMLInputElement) {
    const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value')?.set
    setter?.call(element, prompt)
    element.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: prompt }))
    element.dispatchEvent(new Event('change', { bubbles: true }))
    return element.value === prompt
  }

  if (element.isContentEditable || element.getAttribute('role') === 'textbox') {
    element.textContent = prompt
    element.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: prompt }))
    element.dispatchEvent(new Event('change', { bubbles: true }))
    return true
  }

  return false
}

function installReturnButton() {
  if (document.getElementById(RETURN_BUTTON_ID)) return
  const button = document.createElement('button')
  button.id = RETURN_BUTTON_ID
  button.type = 'button'
  button.textContent = '发送回 BinnAgent'
  Object.assign(button.style, {
    position: 'fixed',
    right: '18px',
    bottom: '18px',
    zIndex: '2147483647',
    border: '0',
    borderRadius: '10px',
    background: '#6366f1',
    color: '#fff',
    boxShadow: '0 10px 25px rgba(15, 23, 42, 0.22)',
    cursor: 'pointer',
    font: '600 14px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    padding: '11px 14px',
  })
  button.addEventListener('click', async () => {
    const html = await extractHtmlForReturn()
    if (!html) {
      button.textContent = '未找到 HTML'
      window.setTimeout(() => {
        button.textContent = '发送回 BinnAgent'
      }, 1800)
      return
    }
    chrome.runtime.sendMessage({ type: 'BINN_GRAMMAR_RETURN_HTML', html }, (response) => {
      button.textContent = response?.ok ? '已发送' : '发送失败'
      window.setTimeout(() => {
        button.textContent = '发送回 BinnAgent'
      }, 1800)
    })
  })
  document.documentElement.appendChild(button)
}

async function extractHtmlForReturn() {
  const clipboardHtml = await readClipboardHtml()
  if (clipboardHtml) return clipboardHtml

  const selected = window.getSelection()?.toString().trim()
  const selectedHtml = selected ? extractHtmlOnly(selected) : ''
  if (selectedHtml) return selectedHtml

  const codeCandidates = Array.from(document.querySelectorAll('pre, code'))
    .map((element) => element.textContent?.trim() || '')
    .filter(Boolean)
  for (const candidate of codeCandidates) {
    const html = extractHtmlOnly(candidate)
    if (html) return html
  }

  const responseCandidates = Array.from(
    document.querySelectorAll('[class*="markdown"], [class*="message"], [class*="answer"], article')
  )
    .map((element) => element.textContent?.trim() || '')
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)

  for (const candidate of responseCandidates) {
    const html = extractHtmlOnly(candidate)
    if (html) return html
  }

  return ''
}

async function readClipboardHtml() {
  try {
    const text = await navigator.clipboard?.readText()
    return text ? extractHtmlOnly(text) : ''
  } catch {
    return ''
  }
}

function extractHtmlOnly(text) {
  const match = text.match(/```(?:html)?\s*([\s\S]*?)```/i)
  const raw = (match?.[1] || text).trim()
  const withoutLanguageLabel = raw.replace(/^html\s*(?=<)/i, '').trim()
  const fullDocument = extractFullHtmlDocument(withoutLanguageLabel)
  if (fullDocument) return fullDocument

  const start = withoutLanguageLabel.search(/<(main|article|section|div|h1|h2|p|ul|ol|table)\b/i)
  if (start < 0) return ''

  const sliced = withoutLanguageLabel.slice(start)
  const end = findHtmlEnd(sliced)
  const html = (end > 0 ? sliced.slice(0, end) : sliced).trim()
  if (!looksLikeHtmlFragment(html)) return ''
  return html
}

function extractFullHtmlDocument(text) {
  const htmlStart = text.search(/<!doctype html\b|<html[\s>]/i)
  if (htmlStart < 0) {
    if (/<head[\s>]/i.test(text) && /<body[\s>]/i.test(text)) {
      return `<!doctype html><html lang="zh-CN">${text.trim()}</html>`
    }
    return ''
  }

  const sliced = text.slice(htmlStart).trim()
  const htmlClose = sliced.search(/<\/html>/i)
  if (htmlClose >= 0) return sliced.slice(0, htmlClose + '</html>'.length).trim()
  return sliced
}

function findHtmlEnd(text) {
  const closingTags = ['main', 'article', 'section', 'div', 'ul', 'ol', 'table']
  let lastEnd = -1
  for (const tag of closingTags) {
    const pattern = new RegExp(`</${tag}>`, 'gi')
    for (let match = pattern.exec(text); match; match = pattern.exec(text)) {
      lastEnd = Math.max(lastEnd, match.index + match[0].length)
    }
  }
  if (lastEnd > 0) return lastEnd

  const simpleBlock = text.match(/^[\s\S]*?<\/(p|h1|h2|h3|li)>/i)
  return simpleBlock ? simpleBlock[0].length : -1
}

function looksLikeHtmlFragment(text) {
  if (!/<[a-z][\s\S]*>/i.test(text)) return false
  if (/^(以下|下面|当然|好的|这里是|这是|复制|注意)[:：\s]/i.test(text)) return false
  return /<\/?(main|article|section|div|h1|h2|h3|p|ul|ol|li|table|blockquote|strong|em|code)\b/i.test(text)
}
