import { renderToString } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { LearningGoalProgress } from './LearningGoalProgress'

describe('LearningGoalProgress', () => {
  it('exposes progress values to assistive technology', () => {
    const html = renderToString(
      <LearningGoalProgress
        dailyGoal={{ completed: 1, total: 4 }}
        weeklyGoal={{ completed: 5, total: 5 }}
      />,
    )

    expect(html).toContain('aria-label="今日目标进度"')
    expect(html).toContain('aria-valuenow="25"')
    expect(html).toContain('aria-label="本周目标进度"')
    expect(html).toContain('aria-valuenow="100"')
  })
})
