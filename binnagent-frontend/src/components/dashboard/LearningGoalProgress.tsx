import { CalendarCheck, CheckCircle2, CircleDot, Target } from 'lucide-react'

interface LearningGoalProgressProps {
  dailyGoal: { label?: string; completed: number; total: number }
  weeklyGoal: { label?: string; completed: number; total: number }
}

export function LearningGoalProgress({ dailyGoal, weeklyGoal }: LearningGoalProgressProps) {
  const toPercent = (completed: number, total: number) => {
    if (total <= 0) return 0
    return Math.max(0, Math.min(100, Math.round((completed / total) * 100)))
  }

  const goals = [
    {
      title: '今日目标',
      goal: dailyGoal,
      icon: CalendarCheck,
    },
    {
      title: '本周目标',
      goal: weeklyGoal,
      icon: Target,
    },
  ]

  return (
    <section className="rounded-xl border bg-card p-6">
      <h3 className="mb-4 text-lg font-semibold text-foreground">学习目标</h3>
      <div className="grid gap-4 md:grid-cols-2">
        {goals.map(({ title, goal, icon: Icon }) => {
          const percent = toPercent(goal.completed, goal.total)
          const remaining = Math.max(goal.total - goal.completed, 0)
          const isComplete = goal.total > 0 && goal.completed >= goal.total
          const StatusIcon = isComplete ? CheckCircle2 : CircleDot

          return (
            <article
              key={title}
              className={`rounded-xl border p-4 transition-colors ${
                isComplete
                  ? 'border-success/30 bg-success/10'
                  : 'border-warning/30 bg-warning/5'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div
                    className={`flex size-10 items-center justify-center rounded-lg ${
                      isComplete ? 'bg-success/15 text-success' : 'bg-warning/15 text-warning'
                    }`}
                  >
                    <Icon className="h-5 w-5" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-foreground">{title}</h4>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {goal.label || `完成 ${goal.total} 次学习任务`}
                    </p>
                  </div>
                </div>
                <div
                  className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
                    isComplete
                      ? 'bg-success text-success-foreground'
                      : 'bg-warning/15 text-warning'
                  }`}
                >
                  <StatusIcon className="h-3.5 w-3.5" />
                  {isComplete ? '已完成' : `还差 ${remaining} 次`}
                </div>
              </div>

              <div className="mt-4">
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="font-medium text-foreground">
                    {goal.completed}/{goal.total}
                  </span>
                  <span className={isComplete ? 'text-success' : 'text-muted-foreground'}>
                    {percent}%
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    className={`h-full transition-all duration-500 ${
                      isComplete ? 'bg-success' : 'bg-warning'
                    }`}
                    style={{ width: `${percent}%` }}
                  />
                </div>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
