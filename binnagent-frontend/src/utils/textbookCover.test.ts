import { describe, expect, it } from 'vitest'
import type { KnowledgeBaseOverview } from '@/types'
import { resolveTextbookCover } from './textbookCover'

function source(overrides: Partial<KnowledgeBaseOverview['source']>): KnowledgeBaseOverview['source'] {
  return {
    id: 'source-1',
    title: '英语 七年级上册',
    filename: 'textbook.pdf',
    publisher: '人民教育出版社（PEP）',
    edition: '人教版',
    grade: 'grade-7',
    volume: 'upper',
    status: 'published',
    unit_count: 12,
    knowledge_count: 538,
    progress: 0,
    ...overrides,
  }
}

describe('resolveTextbookCover', () => {
  it('keeps the original PEP upper-volume cover', () => {
    expect(resolveTextbookCover(source({ city: null }))).toMatchObject({
      src: '/grade7-english-upper-cover.png',
      fit: 'legacy-crop',
    })
  })

  it('uses the dedicated cover only for the Changsha 2024 textbook', () => {
    expect(resolveTextbookCover(source({
      title: '长沙市英语 七年级上册（新目标·2024版）',
      city: '长沙市',
      edition_year: 2024,
    }))).toMatchObject({
      src: '/grade7-english-upper-2024-cover.png',
      fit: 'contain',
    })
  })
})
