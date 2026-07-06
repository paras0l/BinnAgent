import type {
  FailedKnowledgeSourceDetail,
  KnowledgeIngestResult,
  KnowledgeIngestStatus,
} from '@/types'

type IngestSignalSource = KnowledgeIngestResult | FailedKnowledgeSourceDetail | KnowledgeIngestStatus

export function formatFailedIngestMessage(result: KnowledgeIngestResult) {
  const reasons = normalizeBlockingReasons(result.blocking_reasons ?? [])
  const summary = result.parser_report_summary ?? {}
  const metrics = [
    typeof summary.page_count === 'number' ? `页数：${summary.page_count}` : null,
    typeof summary.text_char_count === 'number' ? `可读取文字：${summary.text_char_count} 字` : null,
    typeof summary.unit_count === 'number' ? `单元：${summary.unit_count}` : null,
    typeof summary.rag_chunk_count === 'number' ? `素材片段：${summary.rag_chunk_count}` : null,
  ].filter(Boolean)
  const suggestions = hasScannedPdfSignal(result)
    ? ['系统会尝试本地 OCR 处理扫描版 PDF。', '如果仍不可用，请换成已 OCR、可复制文字的 PDF。']
    : ['请换成文字更清晰、可复制文字的 PDF，或稍后重试。']
  return [
    result.message || '教材解析失败，知识库暂不可用。',
    reasons.length ? `失败原因：\n${reasons.map((reason) => `- ${reason}`).join('\n')}` : null,
    metrics.length ? `解析信息：${metrics.join('，')}` : null,
    `建议：\n${suggestions.map((item) => `- ${item}`).join('\n')}`,
  ].filter(Boolean).join('\n\n')
}

export function normalizeBlockingReasons(reasons: string[]) {
  return reasons.map((reason) => {
    const normalized = reason.toLowerCase()
    if (normalized.includes('scanned') || normalized.includes('text layer')) {
      return 'PDF 可能是扫描版，当前没有可用的文字层。'
    }
    if (normalized.includes('no textbook units')) return '没有识别到可用的教材单元。'
    if (normalized.includes('parser run failed')) return '解析流程执行失败。'
    return reason
  })
}

export function hasScannedPdfSignal(result: IngestSignalSource) {
  const reasons = result.blocking_reasons ?? []
  const summary = result.parser_report_summary ?? {}
  const joined = reasons.join(' ').toLowerCase()
  return Boolean(
    summary.is_scanned_pdf_suspected
    || summary.has_text_layer === false
    || summary.needs_ocr === true
    || joined.includes('scanned')
    || joined.includes('text layer')
  )
}
