import { describe, expect, it } from 'vitest'
import source from './KnowledgeBasePage.tsx?raw'

describe('KnowledgeBasePage daily learning layout', () => {
  it('keeps the learner-facing daily page compact and task-first', () => {
    expect(source).toContain("type KnowledgeWorkspace = 'today' | 'unit' | 'exercises'")
    expect(source).toContain("{ id: 'today', label: '今日任务' }")
    expect(source).toContain('切换教材或添加资料')
    expect(source).not.toContain('KnowledgeLearningOverview')
    expect(source).not.toContain('RAG 片段')
    expect(source).not.toContain('待校对')
    expect(source).not.toContain('解析与索引覆盖')
  })

  it('does not route today learning through listening steps yet', () => {
    expect(source).not.toContain('跟读与听力')
    expect(source).not.toContain('Headphones')
    expect(source).not.toContain('onStartPronunciation')
  })
})
