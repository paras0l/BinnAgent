import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { UploadFailureDetails } from './UploadTextbookDialog'
import { IngestStatusPanel } from '@/pages/KnowledgeBasePage'
import type { KnowledgeIngestResult, KnowledgeIngestStatus } from '@/types'
import { formatFailedIngestMessage } from '@/utils/knowledgeIngest'

describe('UploadTextbookDialog failure details', () => {
  it('shows failed ingest blocking reasons and user suggestions', () => {
    const ingestResult: KnowledgeIngestResult = {
      source_id: 'source-1',
      status: 'failed',
      page_count: 12,
      unit_count: 0,
      knowledge_count: 0,
      message: '教材解析失败或 PDF 文本层不可用，知识库暂不可用，请查看失败原因。',
      quality_status: 'failed',
      blocking_reasons: ['PDF appears to be scanned and has no usable text layer.'],
      parser_report_summary: {
        page_count: 12,
        text_char_count: 0,
        unit_count: 0,
        rag_chunk_count: 0,
        is_scanned_pdf_suspected: true,
      },
    }

    const message = formatFailedIngestMessage(ingestResult)
    const html = renderToString(<UploadFailureDetails message={message} />).replaceAll('<!-- -->', '')

    expect(html).toContain('教材解析失败或 PDF 文本层不可用')
    expect(html).toContain('PDF 可能是扫描版，当前没有可用的文字层。')
    expect(html).toContain('当前版本不支持扫描版 PDF/OCR')
    expect(html).toContain('请换成可以复制文字的 PDF')
    expect(html).toContain('可读取文字：0 字')
  })

  it('renders queued ingest as parsing progress instead of completed copy', () => {
    const status: KnowledgeIngestStatus = {
      source_id: 'source-1',
      parser_run_id: 'run-1',
      processing_status: 'queued',
      stage: 'queued',
      progress: 0,
      quality_status: null,
      availability_status: 'unavailable',
      blocking_reasons: [],
      warnings: [],
      parser_report_summary: {},
      quality_summary: {},
      attempted_engines: [],
      fallback_used: false,
      error_message: null,
      can_open_knowledge_base: false,
      next_action: 'wait',
      message: '教材已进入后台解析，请稍后查看进度。',
    }

    const html = renderToString(<IngestStatusPanel status={status} />).replaceAll('<!-- -->', '')

    expect(html).toContain('教材正在解析')
    expect(html).toContain('等待开始')
    expect(html).toContain('教材已进入后台解析')
    expect(html).not.toContain('教材解析完成，知识库已可用')
  })
})
