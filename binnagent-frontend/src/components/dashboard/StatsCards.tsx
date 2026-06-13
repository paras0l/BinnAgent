import { BookOpen, Flame, Target, BookMarked } from 'lucide-react'

interface StatsCardsProps {
  todayReviews: number
  streakDays: number
  accuracy: number
  totalVocab: number
}

export function StatsCards({ todayReviews, streakDays, accuracy, totalVocab }: StatsCardsProps) {
  const stats = [
    {
      title: '今日复习',
      value: todayReviews,
      icon: BookOpen,
      color: 'text-primary',
      bgColor: 'bg-primary/10',
    },
    {
      title: '连续天数',
      value: `${streakDays}天`,
      icon: Flame,
      color: 'text-warning',
      bgColor: 'bg-warning/10',
    },
    {
      title: '正确率',
      value: `${accuracy}%`,
      icon: Target,
      color: 'text-success',
      bgColor: 'bg-success/10',
    },
    {
      title: '总词汇量',
      value: totalVocab,
      icon: BookMarked,
      color: 'text-accent',
      bgColor: 'bg-accent/10',
    },
  ]

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat) => (
        <div
          key={stat.title}
          className="rounded-xl border p-6 shadow-sm transition-all hover:shadow-md"
        >
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-muted-foreground">{stat.title}</p>
            <div className={`rounded-lg p-2 ${stat.bgColor}`}>
              <stat.icon className={`h-4 w-4 ${stat.color}`} />
            </div>
          </div>
          <div className="mt-3">
            <p className="text-3xl font-bold tracking-tight">{stat.value}</p>
          </div>
        </div>
      ))}
    </div>
  )
}
