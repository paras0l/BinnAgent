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

  it('accepts async exercise generation and polls the persistent pool', () => {
    expect(source).toContain("response.status === 202")
    expect(source).toContain('/exercise-pool')
    expect(source).toContain('retry_after_seconds')
    expect(source).toContain('题目已进入后台生成队列')
  })

  it('can recover a daily challenge without restarting the classroom', () => {
    expect(source).toContain('handlePrepareDailyChallenge')
    expect(source).toContain('评分挑战已准备好，可以作答了。')
    expect(source).toContain('onPrepareChallenge={() => void handlePrepareDailyChallenge()}')
  })

  it('shows capability boosters above the full-screen classroom', () => {
    expect(source).toContain('<div className="fixed inset-0 z-[140]">')
  })

  it('supports confirming a unit skip and resetting it for relearning', () => {
    expect(source).toContain('跳过这个单元？')
    expect(source).toContain('确认跳过')
    expect(source).toContain("updateUnitProgress('skip'")
    expect(source).toContain("updateUnitProgress('relearn'")
    expect(source).toContain("currentCurriculumNode?.progress_override")
    expect(source).toContain("? '继续今天的教材课'")
    expect(source).toContain(": '开始今天的教材课'")
  })

  it('keeps the unit material word list separate from vocabulary practice', () => {
    const materialsSection = source.slice(
      source.indexOf('function UnitMaterialsSection'),
      source.indexOf('interface MaterialDetail'),
    )

    expect(materialsSection).toContain("actionLabel: '查看全部词汇'")
    expect(materialsSection).toContain("actionType: 'details'")
    expect(materialsSection).toContain('detailItems: vocabularySection?.items ?? []')
    expect(materialsSection).toContain("actionLabel: '查看题目列表'")
    expect(materialsSection).toContain("actionType: 'exercise-list'")
    expect(materialsSection).toContain('fetchExercisesForTarget(')
    expect(materialsSection).not.toContain('vocabularyPracticeEntry(vocabulary)')
    expect(materialsSection).not.toContain("onStartVocabulary('new')")
    expect(materialsSection).not.toContain('onStartExercise')
  })

  it('shows the 2024 upper-volume cover without cropping it', () => {
    const cover = source.slice(
      source.indexOf('function TextbookCover'),
      source.indexOf('function UnitProgressBar'),
    )

    expect(cover).toContain('resolveTextbookCover(overview.source)')
    expect(cover).toContain('object-contain object-center')
    expect(cover).toContain('object-[78%_center]')
  })
})
