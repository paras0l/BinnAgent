interface LearningGoalProgressProps {
  dailyGoal: { completed: number; total: number }
  weeklyGoal: { completed: number; total: number }
}

export function LearningGoalProgress({ dailyGoal, weeklyGoal }: LearningGoalProgressProps) {
  const toPercent = (completed: number, total: number) => {
    if (total <= 0) return 0
    return Math.max(0, Math.min(100, Math.round((completed / total) * 100)))
  }
  const dailyPercent = toPercent(dailyGoal.completed, dailyGoal.total)
  const weeklyPercent = toPercent(weeklyGoal.completed, weeklyGoal.total)

  return (
    <div className="rounded-xl border bg-card p-6">
      <h3 className="text-lg font-semibold text-foreground mb-4">学习目标</h3>
      <div className="space-y-4">
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-foreground">今日目标</span>
            <span className="text-sm text-muted-foreground">
              完成 {dailyGoal.completed}/{dailyGoal.total}
            </span>
          </div>
          <div className="h-2 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-500"
              style={{ width: `${dailyPercent}%` }}
            />
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-foreground">本周目标</span>
            <span className="text-sm text-muted-foreground">
              完成 {weeklyGoal.completed}/{weeklyGoal.total}
            </span>
          </div>
          <div className="h-2 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-500"
              style={{ width: `${weeklyPercent}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
