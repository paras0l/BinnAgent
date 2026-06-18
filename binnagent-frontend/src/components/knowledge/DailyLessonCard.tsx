import { ArrowRight, CalendarDays, Check, Clock3 } from 'lucide-react'
import type { KnowledgeBaseOverview } from '@/types'

interface DailyLessonCardProps {
  unit: KnowledgeBaseOverview['current_unit']
  lesson: KnowledgeBaseOverview['daily_lesson']
  onContinue: () => void
}

export function DailyLessonCard({ unit, lesson, onContinue }: DailyLessonCardProps) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.03)] md:p-6">
      <div className="flex items-center gap-2 text-slate-950">
        <CalendarDays className="size-5 text-indigo-600" />
        <h2 className="text-base font-extrabold">继续今日课程</h2>
      </div>

      <div className="mt-5 flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 items-center gap-4">
          <div className="flex size-20 shrink-0 items-center justify-center rounded-xl bg-indigo-600 px-3 text-center text-base font-extrabold leading-tight text-white shadow-sm">
            {unit.title}
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h3 className="truncate text-xl font-extrabold tracking-tight text-slate-950">
                {unit.title}
              </h3>
              <span className="text-base font-bold text-slate-800">{unit.subtitle}</span>
            </div>
            <p className="mt-2 flex items-center gap-1.5 text-sm text-slate-600">
              <Clock3 className="size-4" />
              {lesson.estimated_minutes} 分钟
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onContinue}
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-6 text-sm font-extrabold text-white shadow-sm transition-colors hover:bg-indigo-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
        >
          继续学习
          <ArrowRight className="size-4" />
        </button>
      </div>

      <ol className="mt-5 grid gap-3 md:grid-cols-3">
        {lesson.parts.map((part, index) => (
          <li
            key={part.id}
            className="relative flex items-center gap-3 rounded-xl border border-slate-200 px-4 py-3.5"
          >
            <span className={`flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-extrabold ${
              part.completed ? 'bg-emerald-500 text-white' : 'bg-indigo-50 text-indigo-600'
            }`}>
              {part.completed ? <Check className="size-4" strokeWidth={3} /> : index + 1}
            </span>
            <span>
              <span className="block text-sm font-bold text-slate-800">{part.title}</span>
              <span className="mt-0.5 block text-xs text-slate-500">约 {part.estimated_minutes} 分钟</span>
            </span>
            {index < lesson.parts.length - 1 ? (
              <ArrowRight className="absolute -right-5 z-10 hidden size-4 text-slate-400 md:block" />
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  )
}
