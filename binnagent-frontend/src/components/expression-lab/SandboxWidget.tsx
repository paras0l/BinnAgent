/* eslint-disable react-refresh/only-export-components -- Sandbox protocol helpers are exported for security regression tests. */
import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type { ExpressionSystemAction, ExpressionUiBlock } from '@/services/expressionLabApi'
import { asStrings, firstText, numberValue, textValue } from './blockData'

const SANDBOX_CHANNEL = 'binnagent-expression-sandbox.v1'
const ALLOWED_EVENT_TYPES = new Set(['ready', 'resize', 'action', 'answer', 'change', 'selection_changed', 'answer_submitted', 'interaction'])
const MAX_SANDBOX_HEIGHT = 720
const MIN_SANDBOX_HEIGHT = 220

export interface AllowedSandboxMessage {
  channel: typeof SANDBOX_CHANNEL
  block_id: string
  nonce: string
  type: 'ready' | 'resize' | 'action' | 'answer' | 'change' | 'selection_changed' | 'answer_submitted' | 'interaction'
  payload: Record<string, unknown>
}

export type SandboxTelemetryEvent = AllowedSandboxMessage | {
  channel: typeof SANDBOX_CHANNEL
  block_id: string
  nonce: string
  type: 'timeout' | 'rebuild'
  payload: Record<string, unknown>
}

interface SandboxWidgetProps {
  block: ExpressionUiBlock
  actions: ExpressionSystemAction[]
  onAction: (action: ExpressionSystemAction) => void
  onEvent?: (message: SandboxTelemetryEvent) => void
}

export function SandboxWidget({ block, actions, onAction, onEvent }: SandboxWidgetProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null)
  const [instance, setInstance] = useState(0)
  const [height, setHeight] = useState(() => clampHeight(numberValue(block.data.height, 360)))
  const [timedOut, setTimedOut] = useState(false)
  const timeoutMs = clampTimeout(numberValue(block.data.timeout_ms, 8_000))
  const configuredEvents = useMemo(
    () => new Set(asStrings(block.data.allowed_events).filter((type) => ALLOWED_EVENT_TYPES.has(type))),
    [block.data.allowed_events],
  )
  const nonce = useMemo(() => `${block.id}:${instance}:${cryptoNonce()}`, [block.id, instance])
  const document = useMemo(() => buildSandboxDocument(block, nonce), [block, nonce])

  useEffect(() => {
    if (timedOut) return
    const timeout = window.setTimeout(() => {
      setTimedOut(true)
      onEvent?.({ channel: SANDBOX_CHANNEL, block_id: block.id, nonce, type: 'timeout', payload: { timeout_ms: timeoutMs } })
    }, timeoutMs)
    const handleMessage = (event: MessageEvent) => {
      if (event.source !== iframeRef.current?.contentWindow) return
      if (!isAllowedSandboxMessage(event.data, block.id, nonce, configuredEvents)) return
      const message = event.data
      if (message.type === 'ready') window.clearTimeout(timeout)
      if (message.type === 'resize') setHeight(clampHeight(numberValue(message.payload.height, MIN_SANDBOX_HEIGHT)))
      if (message.type === 'action') {
        const actionId = textValue(message.payload.action_id)
        const action = actions.find((item) => (
          item.spec_action_id === actionId || item.id === actionId
        ) && (!item.block_id || item.block_id === block.id))
        if (action) onAction(action)
      }
      if (message.type !== 'ready' && message.type !== 'resize') onEvent?.(message)
    }
    window.addEventListener('message', handleMessage)
    return () => {
      window.clearTimeout(timeout)
      window.removeEventListener('message', handleMessage)
    }
  }, [actions, block.id, configuredEvents, nonce, onAction, onEvent, timedOut, timeoutMs])

  if (timedOut) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-amber-900">
        <div className="flex items-center gap-2 font-black"><AlertTriangle className="size-5" />互动组件响应超时</div>
        <p className="mt-2 text-sm leading-6">组件已经销毁，不会继续运行。可以重建一次，或忽略这个实验模块继续学习。</p>
        <Button variant="secondary" className="mt-4" onClick={() => {
          onEvent?.({ channel: SANDBOX_CHANNEL, block_id: block.id, nonce, type: 'rebuild', payload: { timeout_ms: timeoutMs } })
          setTimedOut(false)
          setInstance((value) => value + 1)
        }}><RefreshCw className="size-4" />重建组件</Button>
      </div>
    )
  }

  return (
    <iframe
      key={instance}
      ref={iframeRef}
      title={block.title || '表达实验室互动组件'}
      sandbox="allow-scripts"
      referrerPolicy="no-referrer"
      srcDoc={document}
      className="w-full rounded-xl border border-slate-200 bg-white"
      style={{ height }}
    />
  )
}

export function sanitizeSandboxHtml(value: string) {
  if (!value.trim()) return '<main><p>互动内容暂时为空。</p></main>'
  if (typeof DOMParser === 'undefined') return escapeHtml(value)
  const document = new DOMParser().parseFromString(value, 'text/html')
  document.querySelectorAll('form').forEach((form) => form.replaceWith(...Array.from(form.childNodes)))
  document.querySelectorAll('script, iframe, frame, frameset, object, embed, link, meta, base, foreignObject').forEach((node) => node.remove())
  document.querySelectorAll('*').forEach((element) => {
    for (const attribute of Array.from(element.attributes)) {
      const name = attribute.name.toLowerCase()
      const attributeValue = attribute.value.trim().toLowerCase()
      if (name.startsWith('on') || ['action', 'formaction', 'target', 'download', 'srcdoc'].includes(name)) {
        element.removeAttribute(attribute.name)
      } else if (['href', 'src', 'xlink:href'].includes(name)) {
        const isSafeDataImage = name === 'src' && /^data:image\/(?:png|jpeg|gif|webp);base64,/i.test(attribute.value)
        const isSafeFragment = attributeValue.startsWith('#')
        if (!isSafeDataImage && !isSafeFragment) element.removeAttribute(attribute.name)
      } else if (name === 'style' && /(?:url\s*\(|expression\s*\(|@import)/i.test(attribute.value)) {
        element.removeAttribute(attribute.name)
      }
    }
  })
  return document.body.innerHTML
}

export function buildSandboxDocument(block: ExpressionUiBlock, nonce: string) {
  const html = sanitizeSandboxHtml(firstText(block.data, ['html', 'markup', 'content']))
  const css = sanitizeSandboxCss(firstText(block.data, ['css', 'styles']))
  const script = sanitizeSandboxScript(firstText(block.data, ['js', 'javascript', 'script']))
  const blockId = JSON.stringify(block.id)
  const safeNonce = JSON.stringify(nonce)
  return `<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; connect-src 'none'; form-action 'none'; navigate-to 'none'; frame-src 'none'; child-src 'none'; object-src 'none'; media-src 'none'; font-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>html{color-scheme:light}*{box-sizing:border-box}body{margin:0;padding:18px;background:#fff;color:#0f172a;font:14px/1.6 ui-sans-serif,system-ui,sans-serif}button,input,textarea,select{font:inherit}button{min-height:40px;border:1px solid #cbd5e1;border-radius:10px;background:#fff;padding:8px 12px;cursor:pointer}button:focus-visible,input:focus-visible{outline:2px solid #6366f1;outline-offset:2px}${css}</style></head>
<body><main data-expression-lab-widget>${html}</main><script>(()=>{'use strict';const channel=${JSON.stringify(SANDBOX_CHANNEL)};const blockId=${blockId};const nonce=${safeNonce};const emit=(type,payload={})=>{if(!${JSON.stringify([...ALLOWED_EVENT_TYPES])}.includes(type))return;parent.postMessage({channel,block_id:blockId,nonce,type,payload},'*')};Object.defineProperty(window,'binnagent',{value:Object.freeze({emit}),writable:false});for(const key of ['fetch','XMLHttpRequest','WebSocket','EventSource']){try{Object.defineProperty(window,key,{value:undefined,writable:false})}catch{}}try{Object.defineProperty(navigator,'sendBeacon',{value:undefined})}catch{}try{${escapeScript(script)};emit('ready',{height:document.documentElement.scrollHeight})}catch(error){emit('change',{error:'widget_runtime_error'});emit('ready',{height:document.documentElement.scrollHeight,runtime_error:true})}})();</script></body></html>`
}

export function isAllowedSandboxMessage(
  value: unknown,
  blockId: string,
  nonce: string,
  configuredEvents?: ReadonlySet<string>,
): value is AllowedSandboxMessage {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const message = value as Record<string, unknown>
  if (message.channel !== SANDBOX_CHANNEL || message.block_id !== blockId || message.nonce !== nonce) return false
  if (typeof message.type !== 'string' || !ALLOWED_EVENT_TYPES.has(message.type)) return false
  if (!['ready', 'resize'].includes(message.type) && configuredEvents && !configuredEvents.has(message.type)) return false
  if (!message.payload || typeof message.payload !== 'object' || Array.isArray(message.payload)) return false
  const payload = message.payload as Record<string, unknown>
  if (Object.keys(payload).length > 20) return false
  try {
    if (JSON.stringify(payload).length > 8_192) return false
  } catch {
    return false
  }
  if (Object.values(payload).some((item) => typeof item === 'string' && item.length > 2_000)) return false
  if (message.type === 'action' && typeof payload.action_id !== 'string') return false
  if (message.type === 'resize' && (typeof payload.height !== 'number' || !Number.isFinite(payload.height))) return false
  return true
}

function sanitizeSandboxCss(value: string) {
  return value
    .replace(/@import[\s\S]*?;/gi, '')
    .replace(/url\s*\([^)]*\)/gi, 'none')
    .replace(/expression\s*\([^)]*\)/gi, '')
    .replace(/@font-face[\s\S]*?}/gi, '')
    .slice(0, 20_000)
}

function sanitizeSandboxScript(value: string) {
  const forbidden = /\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|indexedDB|localStorage|sessionStorage|cookie|parent|top|opener|location|documentURI|baseURI|eval|Function|importScripts|open)\b|\bimport\s*\(|while\s*\(\s*true\s*\)|for\s*\(\s*;\s*;\s*\)/i
  if (forbidden.test(value)) return `binnagent.emit('change',{error:'blocked_script'});`
  return value.slice(0, 20_000)
}

function escapeScript(value: string) {
  return value.replace(/<\/script/gi, '<\\/script')
}

function escapeHtml(value: string) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;')
}

function clampHeight(value: number) {
  return Math.max(MIN_SANDBOX_HEIGHT, Math.min(MAX_SANDBOX_HEIGHT, Math.round(value)))
}

function clampTimeout(value: number) {
  return Math.max(500, Math.min(10_000, Math.round(value)))
}

function cryptoNonce() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return Math.random().toString(36).slice(2)
}
