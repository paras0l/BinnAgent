import { renderToString } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import {
  CapabilityRecommendationCard,
  type CapabilityRecommendation,
} from './CapabilityRecommendationCard'

const recommendation: CapabilityRecommendation = {
  recommendation_id: 'caprec:test',
  capability_id: 'grammar-explain',
  feature_id: 'grammar-explain',
  title: '语法微知识点',
  reason: '本次练习暴露了语法规则混淆，适合马上补一个专项入口。',
  priority_score: 0.86,
  category: 'grammar',
  action: 'tool',
  tool_target: 'grammar',
  evidence_refs: [{ type: 'exercise_question', id: 'question-1' }],
}

describe('CapabilityRecommendationCard', () => {
  it('renders title, reason, action button, and evidence count', () => {
    const html = renderToString(
      <CapabilityRecommendationCard
        recommendation={recommendation}
        onOpen={vi.fn()}
        onDismiss={vi.fn()}
      />
    ).replaceAll('<!-- -->', '')

    expect(html).toContain('语法微知识点')
    expect(html).toContain('语法规则混淆')
    expect(html).toContain('打开入口')
    expect(html).toContain('暂不需要')
    expect(html).toContain('evidence_refs: 1')
  })
})
