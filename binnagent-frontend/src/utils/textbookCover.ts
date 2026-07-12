import type { KnowledgeBaseOverview } from '@/types'

type TextbookSource = KnowledgeBaseOverview['source']

export interface TextbookCoverAsset {
  src: string
  alt: string
  fit: 'contain' | 'legacy-crop'
}

export function resolveTextbookCover(source: TextbookSource): TextbookCoverAsset | null {
  if (source.grade !== 'grade-7' || source.volume !== 'upper') return null

  const isChangsha2024 = source.city === '长沙市' || source.title.startsWith('长沙市英语')
  if (isChangsha2024) {
    return {
      src: '/grade7-english-upper-2024-cover.png',
      alt: `${source.title}封面`,
      fit: 'contain',
    }
  }

  return {
    src: '/grade7-english-upper-cover.png',
    alt: `${source.publisher || '人民教育出版社（PEP）'} · ${source.title}封面`,
    fit: 'legacy-crop',
  }
}
