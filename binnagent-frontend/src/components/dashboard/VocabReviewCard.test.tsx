import { renderToString } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { VocabReviewCard } from './VocabReviewCard'

describe('VocabReviewCard', () => {
  it('describes the flip action and review position', () => {
    const html = renderToString(
      <VocabReviewCard
        word="significant"
        currentIndex={1}
        totalCount={4}
        onRate={vi.fn()}
      />,
    ).replaceAll('<!-- -->', '')

    expect(html).toContain('aria-label="significant，点击查看释义"')
    expect(html).toContain('第 2 个')
    expect(html).toContain('共 4 个')
  })
})
