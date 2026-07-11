import { useMemo, useState } from 'react'
import {
  ArrowRight,
  BookOpenCheck,
  Check,
  CheckCircle2,
  ClipboardCopy,
  GitCompareArrows,
  LoaderCircle,
  Plus,
  RotateCcw,
  Save,
  Sparkles,
  XCircle,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type {
  ExpressionLabAttempt,
  ExpressionAttemptResult,
  ExpressionSystemAction,
  ExpressionUiBlock,
} from '@/services/expressionLabApi'
import {
  asRecord,
  asRecords,
  asStrings,
  displayValue,
  firstArray,
  firstText,
  numberValue,
  textValue,
} from './blockData'
import { findExpressionAction } from './actionMatching'
import { answerFromAttempt, resultFromAttempt } from './attemptState'

export interface ExpressionBlockProps {
  block: ExpressionUiBlock
  attempts: ExpressionLabAttempt[]
  actions: ExpressionSystemAction[]
  actionStates: Record<string, string>
  onAction: (action: ExpressionSystemAction) => void
  onCopy: (text: string, action?: ExpressionSystemAction) => void
  onAttempt: (blockId: string, questionId: string, answer: unknown) => Promise<ExpressionAttemptResult>
}

export function ExpressionVariantsBlock(props: ExpressionBlockProps) {
  const { block, actions, actionStates, onAction, onCopy } = props
  const items = asRecords(firstArray(block.data, ['variants', 'expressions', 'items', 'options']))
  return (
    <div className="space-y-0">
      {items.map((item, index) => {
        const text = firstText(item, ['text', 'expression', 'sentence'])
        const meaning = firstText(item, ['chinese_explanation', 'chinese_meaning', 'meaning', 'translation'])
        const whyItWorks = firstText(item, ['why_it_works', 'why', 'explanation'])
        const useWhen = firstText(item, ['use_when', 'usage_note', 'context', 'usage_scene', 'scene'])
        const avoidWhen = firstText(item, ['avoid_when'])
        const keyPattern = firstText(item, ['key_pattern', 'pattern', 'template'])
        const example = firstText(item, ['example', 'example_sentence'])
        const exampleTranslation = firstText(item, ['example_translation', 'example_chinese'])
        const actionId = firstText(item, ['action_id', 'spec_action_id'])
        const saveAction = findExpressionAction(actions, 'save_writing_phrase', text, actionId)
        const copyAction = findExpressionAction(actions, 'copy_expression', text, actionId)
        const isRecommended = index === 0
        return (
          <article key={`${text}-${index}`} className={`flex min-w-0 flex-col ${isRecommended ? 'rounded-xl border border-indigo-200 bg-gradient-to-br from-indigo-50/75 via-white to-amber-50/35 p-4 sm:p-5' : 'border-t border-slate-100 px-1 py-5'}`}>
            <div className="flex flex-wrap gap-2 text-xs font-bold">
              {isRecommended ? <Tag tone="amber">当前场景首选</Tag> : <Tag tone="slate">备选 {index + 1}</Tag>}
              {firstText(item, ['tone', 'register']) ? <Tag tone={semanticToneForLabel(firstText(item, ['tone', 'register']))}>{firstText(item, ['tone', 'register'])}</Tag> : null}
              {asStrings(item.tone_tags).map((tag, tagIndex) => <Tag key={tag} tone={semanticToneForLabel(tag, tagIndex)}>{tag}</Tag>)}
            </div>
            <p lang="en" className={`mt-4 break-words font-black text-slate-950 [overflow-wrap:anywhere] ${isRecommended ? 'text-2xl leading-9 sm:text-[1.7rem]' : 'text-lg leading-8'}`}>{text || `表达 ${index + 1}`}</p>
            {meaning ? <p className={`mt-2 leading-6 ${isRecommended ? 'text-base font-bold text-slate-700' : 'text-sm text-slate-600'}`}>{meaning}</p> : null}
            {(useWhen || whyItWorks || keyPattern) ? (
              <dl className={`mt-4 grid gap-3 ${isRecommended ? 'sm:grid-cols-3' : 'sm:grid-cols-2'}`}>
                {useWhen ? <ExpressionNote label="什么时候用" value={useWhen} tone="sky" /> : null}
                {whyItWorks ? <ExpressionNote label="为什么自然" value={whyItWorks} tone="indigo" /> : null}
                {keyPattern ? <ExpressionNote label="可以迁移的结构" value={keyPattern} tone="amber" lang="en" /> : null}
              </dl>
            ) : null}
            {example ? (
              <div className="mt-4 rounded-lg border border-slate-200/80 bg-white/80 px-3.5 py-3">
                <p className="text-[11px] font-black uppercase tracking-wide text-slate-400">真实场景例句</p>
                <p lang="en" className="mt-1.5 text-sm font-bold leading-6 text-slate-900">{example}</p>
                {exampleTranslation ? <p className="mt-1 text-xs leading-5 text-slate-500">{exampleTranslation}</p> : null}
              </div>
            ) : null}
            {avoidWhen ? <p className="mt-3 text-xs leading-5 text-rose-700"><span className="font-black">不建议用于：</span>{avoidWhen}</p> : null}
            <div className="mt-auto flex flex-wrap gap-2 pt-4">
              <Button variant={isRecommended ? 'primary' : 'secondary'} className="px-3 py-2 text-xs" onClick={() => onCopy(text, copyAction)} disabled={!text}>
                <ClipboardCopy className="size-4" />{isRecommended ? '复制首选表达' : '复制'}
              </Button>
              {saveAction ? (
                <ActionButton action={saveAction} state={actionStates[saveAction.id]} onAction={onAction} />
              ) : null}
            </div>
          </article>
        )
      })}
      {items.length === 0 ? <BlockEmpty text="暂时没有可比较的表达，试试重新生成这个模块。" /> : null}
    </div>
  )
}

function ExpressionNote({ label, value, tone, lang }: { label: string; value: string; tone: 'sky' | 'indigo' | 'amber'; lang?: string }) {
  const classes = tone === 'sky' ? 'border-sky-100 bg-sky-50/70' : tone === 'amber' ? 'border-amber-100 bg-amber-50/70' : 'border-indigo-100 bg-indigo-50/70'
  return <div className={`rounded-lg border px-3 py-2.5 ${classes}`}><dt className="text-[11px] font-black text-slate-500">{label}</dt><dd lang={lang} className="mt-1 text-xs font-bold leading-5 text-slate-800">{value}</dd></div>
}

export function ToneSpectrumBlock({ block, onCopy, actions }: ExpressionBlockProps) {
  const items = asRecords(firstArray(block.data, ['items', 'points', 'expressions', 'variants']))
    .sort((left, right) => numberValue(left.position, 50) - numberValue(right.position, 50))
  const leftLabel = firstText(block.data, ['left_label', 'min_label'], '委婉')
  const rightLabel = firstText(block.data, ['right_label', 'max_label'], '直接')
  return (
    <div>
      <div className="flex items-center gap-3" aria-hidden="true">
        <span className="text-xs font-bold text-slate-500">{leftLabel}</span>
        <div className="relative h-2 flex-1 rounded-full bg-gradient-to-r from-sky-300 via-indigo-400 to-rose-400">
          {items.map((item, index) => {
            const fallback = items.length > 1 ? index * (100 / (items.length - 1)) : 50
            const position = Math.max(0, Math.min(100, numberValue(item.position, fallback)))
            return <span key={firstText(item, ['id'], `tone-${index}`)} title={`${firstText(item, ['label'], `表达 ${index + 1}`)} · ${Math.round(position)}`} className="absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-indigo-700 shadow" style={{ left: `${position}%` }} />
          })}
        </div>
        <span className="text-xs font-bold text-slate-500">{rightLabel}</span>
      </div>
      <ol className="mt-5 grid gap-3 md:grid-cols-3" aria-label={`${leftLabel}到${rightLabel}的表达对比`}>
        {items.map((item, index) => {
          const text = firstText(item, ['text', 'expression', 'sentence'])
          const label = firstText(item, ['label', 'tone', 'register'], `强度 ${index + 1}`)
          return (
            <li key={`${text}-${index}`} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-black uppercase tracking-wide text-primary">{label}</p>
              <p lang="en" className="mt-2 break-words text-sm font-black leading-6 text-slate-950 [overflow-wrap:anywhere]">{text}</p>
              {firstText(item, ['explanation', 'meaning', 'when_to_use']) ? <p className="mt-2 text-xs leading-5 text-slate-600">{firstText(item, ['explanation', 'meaning', 'when_to_use'])}</p> : null}
              <Button variant="ghost" className="mt-3 px-2 py-1.5 text-xs" onClick={() => onCopy(text, findExpressionAction(actions, 'copy_expression', text))} disabled={!text}>
                <ClipboardCopy className="size-3.5" />复制
              </Button>
            </li>
          )
        })}
      </ol>
      {items.length === 0 ? <BlockEmpty text="暂时没有语气对比。" /> : null}
    </div>
  )
}

export function SentenceDiffBlock({ block }: ExpressionBlockProps) {
  const changes = asRecords(firstArray(block.data, ['changes', 'segments', 'diff']))
  const original = firstText(block.data, ['original', 'original_sentence', 'before'])
  const corrected = firstText(block.data, ['corrected', 'corrected_sentence', 'after'])
  const summary = firstText(block.data, ['summary', 'explanation', 'error_explanation'])
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <DiffPanel label="原句" tone="error"><del lang="en">{original || '—'}</del></DiffPanel>
        <DiffPanel label="修正后" tone="success"><span lang="en">{corrected || '—'}</span></DiffPanel>
      </div>
      {changes.length > 0 ? (
        <ol className="space-y-2" aria-label="逐项修改说明">
          {changes.map((change, index) => {
            const operation = firstText(change, ['operation', 'type'], 'replace')
            const before = firstText(change, ['original', 'before', 'text'])
            const after = firstText(change, ['replacement', 'after'])
            return (
              <li key={index} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Tag tone={operationTagTone(operation)}>{changeOperationLabel(operation)}</Tag>
                  {before ? <del lang="en" className="rounded bg-rose-100 px-1.5 py-0.5 text-sm font-bold text-rose-800">{before}</del> : null}
                  {after ? <><ArrowRight className="size-4 text-slate-400" /><ins lang="en" className="rounded bg-emerald-100 px-1.5 py-0.5 text-sm font-bold text-emerald-800 no-underline">{after}</ins></> : null}
                </div>
                {textValue(change.explanation) ? <p className="mt-2 text-sm leading-6 text-slate-600">{textValue(change.explanation)}</p> : null}
              </li>
            )
          })}
        </ol>
      ) : null}
      {summary ? <div className="rounded-xl border border-indigo-100 bg-indigo-50/60 p-4"><p className="text-xs font-black uppercase tracking-wide text-indigo-700">修改总结</p><p className="mt-2 text-sm leading-6 text-indigo-950">{summary}</p></div> : null}
    </div>
  )
}

export function PatternDiagramBlock({ block }: ExpressionBlockProps) {
  const rawNodes = asRecords(firstArray(block.data, ['nodes', 'parts', 'slots']))
  const template = firstText(block.data, ['template', 'pattern', 'formula'])
  const nodes = rawNodes.length > 0
    ? rawNodes
    : template.split(/(\[[^\]]+\])/).filter(Boolean).map((label) => ({ label }))
  const width = Math.max(320, nodes.length * 190)
  return (
    <div>
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-4">
        <svg role="img" aria-label={template || '句型结构图'} viewBox={`0 0 ${width} 110`} className="h-28 min-w-full" style={{ width }}>
          <defs>
            <marker id={`arrow-${block.id}`} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="#94a3b8" />
            </marker>
          </defs>
          {nodes.map((node, index) => {
            const x = 10 + index * 190
            const label = firstText(node, ['label', 'text', 'value', 'name'], `部分 ${index + 1}`)
            const placeholder = 'placeholder' in node ? node.placeholder : undefined
            const isSlot = label.includes('[') || firstText(node, ['kind']) === 'slot' || placeholder === true || typeof placeholder === 'string'
            return (
              <g key={`${label}-${index}`}>
                {index > 0 ? <line x1={x - 40} y1="55" x2={x - 10} y2="55" stroke="#94a3b8" strokeWidth="2" markerEnd={`url(#arrow-${block.id})`} /> : null}
                <rect x={x} y="20" width="150" height="70" rx="12" fill={isSlot ? '#eef2ff' : '#ffffff'} stroke={isSlot ? '#818cf8' : '#cbd5e1'} strokeWidth="2" />
                <text x={x + 75} y="52" textAnchor="middle" fill="#0f172a" fontSize="13" fontWeight="700">{shorten(label, 20)}</text>
                {firstText(node, ['description', 'meaning']) ? <text x={x + 75} y="72" textAnchor="middle" fill="#64748b" fontSize="10">{shorten(firstText(node, ['description', 'meaning']), 24)}</text> : null}
              </g>
            )
          })}
        </svg>
      </div>
      {template ? <p className="mt-3 rounded-lg bg-indigo-50 px-3 py-2 font-mono text-sm font-bold leading-6 text-indigo-900">{template}</p> : null}
      {firstText(block.data, ['explanation', 'usage']) ? <p className="mt-3 text-sm leading-6 text-slate-600">{firstText(block.data, ['explanation', 'usage'])}</p> : null}
    </div>
  )
}

export function UsageComparisonBlock({ block }: ExpressionBlockProps) {
  const items = asRecords(firstArray(block.data, ['items', 'comparisons', 'expressions', 'rows']))
  const columns = [
    ['表达', ['expression', 'text', 'term']],
    ['含义', ['meaning', 'definition']],
    ['语域', ['register', 'tone']],
    ['适用场景', ['context', 'usage', 'when_to_use']],
    ['常见搭配', ['collocations', 'common_collocations']],
    ['不建议用于', ['avoid_when', 'avoid']],
  ] as const
  return (
    <div>
      <div className="hidden overflow-x-auto rounded-xl border border-slate-200 md:block">
        <table className="w-full min-w-[760px] border-collapse text-left text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500"><tr>{columns.map(([label]) => <th key={label} className="border-b px-3 py-3 font-black">{label}</th>)}</tr></thead>
          <tbody>{items.map((item, index) => <tr key={index} className="align-top odd:bg-white even:bg-slate-50/50">{columns.map(([label, keys]) => <td key={label} className="border-b border-slate-100 px-3 py-3 leading-6 text-slate-700">{displayValue(keys.map((key) => item[key]).find((value) => displayValue(value))) || '—'}</td>)}</tr>)}</tbody>
        </table>
      </div>
      <div className="grid gap-3 md:hidden">
        {items.map((item, index) => (
          <article key={index} className="rounded-xl border border-slate-200 bg-white p-4">
            <p lang="en" className="font-black text-slate-950">{firstText(item, ['expression', 'text', 'term'], `表达 ${index + 1}`)}</p>
            <dl className="mt-3 space-y-2">{columns.slice(1).map(([label, keys]) => <ComparisonRow key={label} label={label} value={displayValue(keys.map((key) => item[key]).find((value) => displayValue(value))) || '—'} />)}</dl>
          </article>
        ))}
      </div>
      {items.length === 0 ? <BlockEmpty text="暂时没有用法对比。" /> : null}
    </div>
  )
}

export function VocabularyFocusBlock({ block, actions, actionStates, onAction }: ExpressionBlockProps) {
  const items = asRecords(firstArray(block.data, ['entries', 'items', 'words', 'vocabulary', 'terms']))
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {items.map((item, index) => {
        const word = firstText(item, ['word', 'term', 'phrase', 'text'])
        const saveAction = findExpressionAction(actions, 'save_vocabulary', word, firstText(item, ['action_id', 'spec_action_id']))
        return (
          <article key={`${word}-${index}`} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0"><p lang="en" className="break-words text-xl font-black text-slate-950 [overflow-wrap:anywhere]">{word}</p><p className="mt-1 text-sm leading-6 text-slate-600">{firstText(item, ['meaning', 'definition', 'chinese_meaning'])}</p></div>
              {saveAction ? <ActionButton action={saveAction} state={actionStates[saveAction.id]} onAction={onAction} compact /> : null}
            </div>
            <DetailList item={item} rows={[
              ['常见搭配', ['collocations', 'common_collocations']],
              ['例句', ['example', 'examples']],
              ['近义词', ['synonyms']],
              ['推荐原因', ['reason', 'recommendation_reason']],
            ]} />
          </article>
        )
      })}
      {items.length === 0 ? <BlockEmpty text="暂时没有需要展开的词汇。" /> : null}
    </div>
  )
}

export function GrammarFocusBlock({ block, actions, actionStates, onAction }: ExpressionBlockProps) {
  const items = asRecords(firstArray(block.data, ['items', 'grammar_points', 'rules', 'points']))
  const normalizedItems = items.length > 0 ? items : [block.data]
  return (
    <div className="grid gap-3">
      {normalizedItems.map((item, index) => {
        const title = firstText(item, ['topic', 'title', 'name', 'grammar_point'], `语法点 ${index + 1}`)
        const minimalPairs = asRecords(item.minimal_pairs)
        const saveAction = findExpressionAction(actions, 'save_grammar_point', title, firstText(item, ['action_id', 'spec_action_id']))
        return (
          <article key={`${title}-${index}`} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0"><p className="font-black text-slate-950">{title}</p><p className="mt-2 text-sm leading-6 text-slate-600">{firstText(item, ['rule', 'explanation', 'description', 'rule_text'])}</p></div>
              {saveAction ? <ActionButton action={saveAction} state={actionStates[saveAction.id]} onAction={onAction} /> : null}
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {firstText(item, ['error', 'incorrect']) ? <DiffPanel label="常见错误" tone="error"><span lang="en">{firstText(item, ['error', 'incorrect'])}</span></DiffPanel> : null}
              {firstText(item, ['correction', 'correct']) ? <DiffPanel label="正确表达" tone="success"><span lang="en">{firstText(item, ['correction', 'correct'])}</span></DiffPanel> : null}
            </div>
            {minimalPairs.length > 0 ? (
              <div className="mt-4 space-y-2">
                <p className="text-xs font-black uppercase tracking-wide text-slate-500">最小对比</p>
                {minimalPairs.map((pair, pairIndex) => (
                  <div key={pairIndex} className="grid gap-2 rounded-xl bg-slate-50 p-3 md:grid-cols-2">
                    <p lang="en" className="text-sm font-bold text-rose-800"><span className="mr-2 text-xs text-rose-500">错误</span>{firstText(pair, ['wrong', 'error'])}</p>
                    <p lang="en" className="text-sm font-bold text-emerald-800"><span className="mr-2 text-xs text-emerald-600">正确</span>{firstText(pair, ['correct', 'correction'])}</p>
                    {firstText(pair, ['explanation']) ? <p className="text-xs leading-5 text-slate-600 md:col-span-2">{firstText(pair, ['explanation'])}</p> : null}
                  </div>
                ))}
              </div>
            ) : null}
          </article>
        )
      })}
    </div>
  )
}

export function MicroPracticeBlock({ block, attempts, onAttempt }: ExpressionBlockProps) {
  const questions = asRecords(firstArray(block.data, ['questions', 'items', 'exercises']))
  const normalizedQuestions = questions.length > 0 ? questions : [block.data]
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [results, setResults] = useState<Record<string, ExpressionAttemptResult | null>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [showHint, setShowHint] = useState(false)
  const question = normalizedQuestions[Math.min(currentIndex, normalizedQuestions.length - 1)] ?? {}
  const questionId = firstText(question, ['id', 'question_id'], `${block.id}-q${currentIndex + 1}`)
  const options = asStrings(firstArray(question, ['options', 'choices']))
  const storedAttempt = [...attempts].reverse().find((attempt) => (
    attempt.block_id === block.id && attempt.question_id === questionId
  ))
  const answer = answers[questionId] ?? answerFromAttempt(storedAttempt)
  const result = questionId in results ? results[questionId] : resultFromAttempt(storedAttempt)

  const submit = async () => {
    if (!answer.trim() || isSubmitting) return
    setIsSubmitting(true)
    try {
      const submitted = await onAttempt(block.id, questionId, answer.trim())
      setResults((current) => ({
        ...current,
        [questionId]: submitted,
      }))
    } finally {
      setIsSubmitting(false)
    }
  }

  const next = () => {
    setCurrentIndex((value) => Math.min(value + 1, normalizedQuestions.length - 1))
    setShowHint(false)
  }

  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <Tag tone="sky">{firstText(question, ['type', 'exercise_type'], '表达练习')}</Tag>
        <span className="text-xs font-bold text-slate-500">{currentIndex + 1} / {normalizedQuestions.length}</span>
      </div>
      <p className="mt-4 text-lg font-black leading-8 text-slate-950">{firstText(question, ['prompt', 'stem', 'question'], '请使用本次表达完成练习。')}</p>
      {firstText(block.data, ['instructions']) ? <p className="mt-2 text-sm leading-6 text-slate-500">{firstText(block.data, ['instructions'])}</p> : null}
      {firstText(question, ['context', 'scenario']) ? <p className="mt-2 rounded-lg bg-sky-50 px-3 py-2 text-sm leading-6 text-sky-800">{firstText(question, ['context', 'scenario'])}</p> : null}
      {options.length > 0 ? (
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {options.map((option) => <button key={option} type="button" aria-pressed={answer === option} disabled={Boolean(result)} onClick={() => setAnswers((current) => ({ ...current, [questionId]: option }))} className={`rounded-xl border px-4 py-3 text-left text-sm font-bold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${answer === option ? 'border-primary bg-primary/10 text-primary' : 'border-slate-200 bg-white text-slate-700 hover:border-primary/40'}`}>{option}</button>)}
        </div>
      ) : (
        <label className="mt-4 block text-sm font-bold text-slate-700">我的答案<textarea name={`expression_attempt_${questionId}`} value={answer} onChange={(event) => setAnswers((current) => ({ ...current, [questionId]: event.target.value }))} disabled={Boolean(result)} rows={3} className="mt-2 w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm leading-6 outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/20" placeholder="输入你的表达…" /></label>
      )}
      {firstText(question, ['hint']) && !result ? (
        <div className="mt-3">
          <Button variant="ghost" className="px-3 py-2 text-xs" onClick={() => setShowHint((value) => !value)}><Sparkles className="size-4" />{showHint ? '收起提示' : '给我一个提示'}</Button>
          {showHint ? <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-sm leading-6 text-amber-900">{firstText(question, ['hint'])}</p> : null}
        </div>
      ) : null}
      {result ? (
        <div aria-live="polite" className={`mt-4 rounded-xl border p-4 ${result.is_correct ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-rose-200 bg-rose-50 text-rose-800'}`}>
          <div className="flex items-center gap-2 font-black">{result.is_correct ? <CheckCircle2 className="size-5" /> : <XCircle className="size-5" />}{result.is_correct ? '回答正确' : '继续调整会更自然'} · {Math.round(result.score)} 分</div>
          <p className="mt-2 text-sm leading-6">{feedbackText(result.feedback)}</p>
          {result.next_recommendations?.length ? <ul className="mt-2 space-y-1 text-sm">{result.next_recommendations.map((item, index) => <li key={`${displayValue(item)}-${index}`}>• {firstText(item, ['message', 'reason', 'label', 'title'], displayValue(item))}</li>)}</ul> : null}
        </div>
      ) : null}
      <div className="mt-5 flex flex-wrap gap-2">
        <Button onClick={() => void submit()} disabled={!answer.trim() || isSubmitting || Boolean(result)}>{isSubmitting ? <LoaderCircle className="size-4 animate-spin" /> : <Check className="size-4" />}{isSubmitting ? '提交中…' : '提交答案'}</Button>
        {result && currentIndex < normalizedQuestions.length - 1 ? <Button variant="secondary" onClick={next}>下一题<ArrowRight className="size-4" /></Button> : null}
        {result ? <Button variant="ghost" onClick={() => { setAnswers((current) => ({ ...current, [questionId]: '' })); setResults((current) => ({ ...current, [questionId]: null })) }}><RotateCcw className="size-4" />再答一次</Button> : null}
      </div>
    </div>
  )
}

export function TransferBuilderBlock({ block, actions, actionStates, onAction, onCopy }: ExpressionBlockProps) {
  const slots = asRecords(firstArray(block.data, ['slots', 'fields', 'variables']))
  const template = firstText(block.data, ['template', 'pattern'])
  const initialValues = useMemo(() => Object.fromEntries(slots.map((slot, index) => [slotKey(slot, index), firstText(slot, ['default', 'value'])])), [slots])
  const [values, setValues] = useState<Record<string, string>>(initialValues)

  const preview = slots.reduce((result, slot, index) => {
    const key = slotKey(slot, index)
    return replaceTransferSlot(result, slot, key, values[key] ?? '')
  }, template)
  const baseSaveAction = findExpressionAction(actions, 'save_writing_phrase', preview) ?? findExpressionAction(actions, 'save_writing_phrase', template)
  const saveAction = baseSaveAction ? { ...baseSaveAction, payload: { ...baseSaveAction.payload, text: preview } } : undefined

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.8fr)]">
      <div className="space-y-3">
        {slots.map((slot, index) => {
          const key = slotKey(slot, index)
          return <label key={key} className="block text-sm font-bold text-slate-700">{firstText(slot, ['label', 'name'], `替换内容 ${index + 1}`)}<input name={`transfer_${block.id}_${key}`} value={values[key] ?? ''} onChange={(event) => setValues((current) => ({ ...current, [key]: event.target.value }))} className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/20" placeholder={asStrings(slot.examples)[0] || firstText(slot, ['placeholder', 'hint', 'example'], '输入替换内容')} /></label>
        })}
        {slots.length === 0 ? <BlockEmpty text="这个迁移模板暂时没有可替换槽位。" /> : null}
      </div>
      <div className="flex flex-col rounded-xl border border-indigo-100 bg-indigo-50/60 p-4">
        <p className="text-xs font-black uppercase tracking-wide text-indigo-700">实时预览</p>
        <p aria-live="polite" lang="en" className="mt-3 break-words text-lg font-black leading-8 text-indigo-950 [overflow-wrap:anywhere]">{firstText(block.data, ['preview_prefix'])}{preview || template}</p>
        {firstText(block.data, ['example']) ? <p lang="en" className="mt-3 text-sm leading-6 text-indigo-800">示例：{firstText(block.data, ['example'])}</p> : null}
        <div className="mt-auto flex flex-wrap gap-2 pt-5">
          <Button variant="secondary" className="px-3 py-2 text-xs" onClick={() => onCopy(preview)} disabled={!preview}><ClipboardCopy className="size-4" />复制</Button>
          {saveAction ? <ActionButton action={saveAction} state={actionStates[saveAction.id]} onAction={onAction} /> : null}
        </div>
      </div>
    </div>
  )
}

function ActionButton({ action, state, onAction, compact = false }: { action: ExpressionSystemAction; state?: string; onAction: (action: ExpressionSystemAction) => void; compact?: boolean }) {
  const saved = state === 'saved' || action.status === 'saved'
  const saving = state === 'saving'
  const failed = state === 'failed'
  return <Button variant={failed ? 'secondary' : 'primary'} className={compact ? 'shrink-0 px-3 py-2 text-xs' : 'px-3 py-2 text-xs'} onClick={() => onAction(action)} disabled={saved || saving}>{saving ? <LoaderCircle className="size-4 animate-spin" /> : saved ? <Check className="size-4" /> : failed ? <RotateCcw className="size-4" /> : <Save className="size-4" />}{saving ? '保存中' : saved ? '已保存' : failed ? '重试' : action.label}</Button>
}

const DECORATIVE_TAG_TONES = ['indigo', 'sky', 'violet', 'amber', 'rose'] as const

function Tag({ children, tone = 'indigo' }: { children: React.ReactNode; tone?: 'indigo' | 'slate' | 'green' | 'sky' | 'violet' | 'amber' | 'rose' }) {
  const classes = TAG_TONE_CLASSES[tone]
  return <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-black leading-4 ring-1 ring-inset ${classes}`}>{children}</span>
}

function BlockEmpty({ text }: { text: string }) {
  return <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5 text-center text-sm text-slate-500">{text}</div>
}

function DiffPanel({ children, label, tone }: { children: React.ReactNode; label: string; tone: 'error' | 'success' }) {
  return <div className={`rounded-xl border p-4 ${tone === 'error' ? 'border-rose-200 bg-rose-50' : 'border-emerald-200 bg-emerald-50'}`}><p className={`text-xs font-black uppercase tracking-wide ${tone === 'error' ? 'text-rose-700' : 'text-emerald-700'}`}>{label}</p><p className={`mt-2 break-words text-sm font-bold leading-7 [overflow-wrap:anywhere] ${tone === 'error' ? 'text-rose-900' : 'text-emerald-900'}`}>{children}</p></div>
}

function ComparisonRow({ label, value }: { label: string; value: string }) {
  return <div className="grid grid-cols-[76px_minmax(0,1fr)] gap-2"><dt className="text-xs font-bold text-slate-500">{label}</dt><dd className="text-xs leading-5 text-slate-700">{value}</dd></div>
}

function DetailList({ item, rows }: { item: Record<string, unknown>; rows: Array<[string, string[]]> }) {
  return <dl className="mt-4 space-y-2">{rows.map(([label, keys]) => { const value = displayValue(keys.map((key) => item[key]).find((candidate) => displayValue(candidate))); return value ? <div key={label} className="grid gap-1 sm:grid-cols-[76px_minmax(0,1fr)]"><dt className="text-xs font-black text-slate-500">{label}</dt><dd className="text-sm leading-6 text-slate-700">{value}</dd></div> : null })}</dl>
}

function slotKey(slot: Record<string, unknown>, index: number) {
  return firstText(slot, ['id', 'key', 'name'], `slot-${index + 1}`)
}

function replaceTransferSlot(template: string, slot: Record<string, unknown>, key: string, value: string) {
  const replacement = value.trim()
  if (!replacement) return template
  const label = firstText(slot, ['label', 'name'])
  const configured = firstText(slot, ['placeholder', 'token'])
  const tokens = new Set([configured, `[${key}]`, `{{${key}}}`, label ? `[${label}]` : '', label ? `{{${label}}}` : ''].filter(Boolean))
  return [...tokens].reduce((result, token) => result.replaceAll(token, replacement), template)
}

function changeOperationLabel(operation: string) {
  if (['delete', 'removed'].includes(operation)) return '删除'
  if (['add', 'insert', 'added'].includes(operation)) return '新增'
  if (operation === 'replace') return '替换'
  return '调整'
}

function operationTagTone(operation: string): TagTone {
  if (['delete', 'removed'].includes(operation)) return 'rose'
  if (['add', 'insert', 'added'].includes(operation)) return 'sky'
  if (operation === 'replace') return 'violet'
  return 'amber'
}

function feedbackText(value: unknown) {
  if (typeof value === 'string') return value
  const record = asRecord(value)
  return firstText(record, ['message', 'explanation', 'feedback'], displayValue(value) || '已记录本次练习。')
}

function shorten(value: string, max: number) {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value
}

export function BlockTypeBadge({ type }: { type: string }) {
  const icon = type === 'sentence_diff' ? <GitCompareArrows className="size-4" /> : type === 'micro_practice' ? <BookOpenCheck className="size-4" /> : type.includes('focus') ? <Plus className="size-4" /> : <Sparkles className="size-4" />
  const tone = BLOCK_TYPE_TONES[type] ?? 'indigo'
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-black leading-4 ring-1 ring-inset ${TAG_TONE_CLASSES[tone]}`}>{icon}{blockTypeLabel(type)}</span>
}

type TagTone = 'indigo' | 'slate' | 'green' | 'sky' | 'violet' | 'amber' | 'rose'

const TAG_TONE_CLASSES: Record<TagTone, string> = {
  amber: 'bg-amber-100/75 text-amber-800 ring-amber-200/80',
  green: 'bg-emerald-100/75 text-emerald-800 ring-emerald-200/80',
  indigo: 'bg-indigo-100/80 text-indigo-800 ring-indigo-200/80',
  rose: 'bg-rose-100/75 text-rose-800 ring-rose-200/80',
  sky: 'bg-sky-100/80 text-sky-800 ring-sky-200/80',
  slate: 'bg-slate-100 text-slate-700 ring-slate-200',
  violet: 'bg-violet-100/80 text-violet-800 ring-violet-200/80',
}

const BLOCK_TYPE_TONES: Record<string, TagTone> = {
  expression_variants: 'indigo',
  tone_spectrum: 'violet',
  sentence_diff: 'sky',
  pattern_diagram: 'amber',
  usage_comparison: 'rose',
  vocabulary_focus: 'sky',
  grammar_focus: 'violet',
  micro_practice: 'amber',
  transfer_builder: 'rose',
  sandbox_widget: 'indigo',
}

function semanticToneForLabel(label: string, fallbackIndex = 0): TagTone {
  const normalized = label.toLocaleLowerCase()
  if (/委婉|温和|友好|亲切|warm|soft|gentle|polite/.test(normalized)) return 'rose'
  if (/正式|严谨|学术|书面|formal|academic/.test(normalized)) return 'violet'
  if (/自然|日常|口语|轻松|natural|casual|spoken/.test(normalized)) return 'sky'
  if (/直接|强调|坚定|有力|direct|strong|firm/.test(normalized)) return 'amber'
  if (/中性|通用|neutral|general/.test(normalized)) return 'indigo'
  return DECORATIVE_TAG_TONES[fallbackIndex % DECORATIVE_TAG_TONES.length]
}

function blockTypeLabel(type: string) {
  const labels: Record<string, string> = {
    expression_variants: '表达方案', tone_spectrum: '语气光谱', sentence_diff: '句子修复', pattern_diagram: '句型结构', usage_comparison: '用法对比', vocabulary_focus: '词汇聚焦', grammar_focus: '语法聚焦', micro_practice: '小练习', transfer_builder: '迁移造句', sandbox_widget: '互动组件',
  }
  return labels[type] ?? '生成模块'
}
