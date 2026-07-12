import { describe, expect, it } from 'vitest'
import appSource from '@/App.tsx?raw'
import actionBarSource from '@/components/expression-lab/ExpressionActionBar.tsx?raw'
import dashboardSource from './DashboardPage.tsx?raw'
import exploreSource from './ExplorePage.tsx?raw'
import expressionLabSource from './ExpressionLabPage.tsx?raw'
import groupSignalsSource from './GroupLearningSignalsPage.tsx?raw'

describe('Expression Lab product entry contracts', () => {
  it('keeps the expression lab out of Explore while preserving other product entries', () => {
    expect(exploreSource).toContain("'expression-lab'")
    expect(exploreSource).not.toContain("title: '英语表达实验室'")
    expect(exploreSource).not.toContain('onOpenExpressionLab')
  })

  it('routes the five specified group learning signals into the lab as the primary action', () => {
    expect(groupSignalsSource).toContain(
      "['expression_gap', 'grammar_error', 'good_sentence', 'desired_vocabulary', 'desired_grammar']",
    )
    expect(groupSignalsSource).toContain('打开表达实验室')
    expect(groupSignalsSource).toContain('完成学习后可选择保存')
    expect(groupSignalsSource).toContain('sourceSignal: {')
    expect(groupSignalsSource).toContain('signalType: signal.type')
    expect(groupSignalsSource).toContain('text: signal.sourceText')
  })

  it('keeps a secondary learning-center entry without adding a main navigation tab', () => {
    expect(dashboardSource).toContain('英语表达实验室')
    expect(dashboardSource).toContain('继续处理')
    expect(dashboardSource).toContain('打开实验室')
    expect(appSource).toContain("type ExpressionLabReturnTo = 'explore' | 'dashboard' | 'group-signals'")
    expect(appSource).not.toContain("| 'expression-lab'\n")
  })

  it('supports deep-linked sessions and restores the correct return workspace', () => {
    expect(appSource).toContain("window.history.pushState")
    expect(appSource).toContain("expressionLabPath(next.sessionId)")
    expect(appSource).toContain("window.addEventListener('popstate'")
    expect(appSource).toContain("returnTo === 'group-signals'")
    expect(appSource).toContain("returnTo === 'dashboard'")
    expect(appSource).toContain('{expressionLabLaunch ? null : profileSetupBanner}')
  })
})

describe('Expression Lab stable workspace contract', () => {
  it('offers all required input controls and preserves drafts', () => {
    expect(expressionLabSource).toContain("'zh_intent'")
    expect(expressionLabSource).toContain("'en_draft'")
    expect(expressionLabSource).toContain("'good_sentence'")
    expect(expressionLabSource).toContain("'learning_target'")
    expect(expressionLabSource).toContain('使用场景')
    expect(expressionLabSource).toContain('目标风格')
    expect(expressionLabSource).toContain('当前水平')
    expect(expressionLabSource).toContain('生成 1–3 道小练习')
    expect(expressionLabSource).toContain("DRAFT_STORAGE_PREFIX = 'binnExpressionLabDraft:v1:'")
  })

  it('keeps generation, evidence, completion, exit-and-keep, and delete flows in the fixed shell', () => {
    expect(expressionLabSource).toContain('<ExpressionBlockSkeleton')
    expect(expressionLabSource).toContain('<ExpressionEvidenceDrawer')
    expect(expressionLabSource).toContain('<ExpressionActionBar')
    expect(expressionLabSource).toContain('completeExpressionLabSession')
    expect(expressionLabSource).toContain('deleteExpressionLabSession')
    expect(actionBarSource).toContain('退出并保留')
    expect(actionBarSource).toContain('再练一组')
  })
})
