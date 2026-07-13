export interface ImageBoardItem {
  id: string
  title: string
  imageUrl: string
}

export interface ImageBoardArtifact {
  id: string
  type: 'image_board'
  title: string
  items: ImageBoardItem[]
}

export interface InteractiveHtmlArtifact {
  id: string
  type: 'interactive_html'
  title: string
  html: string
  css: string
  javascript: string
  height: number
  allowedEvents: string[]
}

export type ChatArtifact = ImageBoardArtifact | InteractiveHtmlArtifact

export interface ChatArtifactAction {
  message: string
  context: {
    artifactId: string
    artifactType: ChatArtifact['type']
    artifactTitle: string
    eventType: string
    payload: Record<string, unknown>
  }
}

export interface ParsedChatArtifacts {
  content: string
  artifacts: ChatArtifact[]
}

const MARKDOWN_IMAGE_PATTERN = /!\[([^\]]*)\]\(([^\s)]+)(?:\s+["'][^"']*["'])?\)/gu
const INTERACTIVE_WIDGET_PATTERN = /```binnagent-widget\s*\n([\s\S]*?)```/giu
const STYLE_PATTERN = /<style(?:\s[^>]*)?>([\s\S]*?)<\/style>/giu
const SCRIPT_PATTERN = /<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/giu
const TITLE_PATTERN = /<!--\s*title\s*:\s*([^\n]*?)\s*-->/iu
const HEIGHT_PATTERN = /<!--\s*height\s*:\s*(\d+)\s*-->/iu

export function parseChatArtifacts(messageId: string, content: string): ParsedChatArtifacts {
  const artifacts: ChatArtifact[] = []
  let widgetIndex = 0
  const contentWithoutWidgets = content.replace(INTERACTIVE_WIDGET_PATTERN, (_match, source: string) => {
    widgetIndex += 1
    const title = source.match(TITLE_PATTERN)?.[1]?.trim() || `互动组件 ${widgetIndex}`
    const requestedHeight = Number(source.match(HEIGHT_PATTERN)?.[1] || 360)
    const css = collectMatches(source, STYLE_PATTERN)
    const javascript = collectMatches(source, SCRIPT_PATTERN)
    const html = source
      .replace(STYLE_PATTERN, '')
      .replace(SCRIPT_PATTERN, '')
      .replace(TITLE_PATTERN, '')
      .replace(HEIGHT_PATTERN, '')
      .trim()
    artifacts.push({
      id: `${messageId}-interactive-${widgetIndex}`,
      type: 'interactive_html',
      title,
      html,
      css,
      javascript,
      height: Math.min(Math.max(requestedHeight, 220), 720),
      allowedEvents: ['interaction', 'answer', 'change', 'selection_changed', 'answer_submitted'],
    })
    return ''
  })

  const items: ImageBoardItem[] = []
  const contentWithoutImages = contentWithoutWidgets.replace(
    MARKDOWN_IMAGE_PATTERN,
    (_match, rawTitle: string, rawUrl: string) => {
      const imageUrl = safeImageUrl(rawUrl)
      if (!imageUrl) return _match
      const index = items.length + 1
      items.push({
        id: `${messageId}-image-${index}`,
        title: rawTitle.trim() || `图片 ${index}`,
        imageUrl,
      })
      return ''
    },
  )

  if (items.length > 0) {
    artifacts.push({
      id: `${messageId}-image-board`,
      type: 'image_board',
      title: items.length === 1 ? items[0].title : '对话图片板',
      items,
    })
  }

  if (artifacts.length === 0) return { content, artifacts: [] }

  return {
    content: contentWithoutImages.replace(/\n{3,}/gu, '\n\n').trim(),
    artifacts,
  }
}

export function streamingArtifactPreview(content: string): string {
  const fenceIndex = content.search(/```binnagent-widget\b/iu)
  if (fenceIndex < 0) return sanitizeVisibleAssistantContent(content)
  const visible = content.slice(0, fenceIndex).trimEnd()
  return sanitizeVisibleAssistantContent(`${visible}${visible ? '\n\n' : ''}_正在准备互动练习…_`)
}

export function sanitizeVisibleAssistantContent(content: string): string {
  return content
    .replace(/以下是一个严格只包含一个\s*`?binnagent-widget`?\s*代码块的回答[：:]?/giu, '请完成下面的互动练习：')
    .replace(/`?binnagent-widget`?/giu, '互动组件')
}

function collectMatches(source: string, pattern: RegExp): string {
  pattern.lastIndex = 0
  return Array.from(source.matchAll(pattern), (match) => match[1] || '').join('\n')
}

function safeImageUrl(rawUrl: string): string | null {
  const url = rawUrl.trim()
  if (/^(https?:|data:image\/|blob:)/iu.test(url)) return url
  if (url.startsWith('/')) return url
  return null
}
