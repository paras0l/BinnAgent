import { RotateCcw, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { ReadingWorkshopPage } from '@/pages/ReadingWorkshopPage'
import {
  READING_REVIEW_LEARNER,
  READING_REVIEW_MATERIAL,
  READING_REVIEW_PROFILE,
} from './readingReviewFixtures'

export function ReadingWorkshopReviewApp() {
  const resetReview = () => {
    for (const key of Object.keys(localStorage)) {
      if (
        key.startsWith('binnagent:reading-workshop-draft:')
        || key.startsWith('binnExerciseAttempts:')
      ) {
        localStorage.removeItem(key)
      }
    }
    window.location.reload()
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <aside className="sticky top-0 z-50 border-b border-indigo-200 bg-white/95 px-4 py-3 shadow-sm backdrop-blur" aria-label="团队验收说明">
        <div className="mx-auto flex max-w-[1600px] flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-xl bg-indigo-100 text-indigo-700">
              <ShieldCheck className="size-5" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-black text-slate-950">团队验收环境 · 隔离示例数据</p>
              <p className="mt-0.5 text-xs leading-5 text-slate-600">
                可验证材料保存、泛读证据、逐句精读、阅读助手、完成门槛与刷新恢复；所有操作只保存在当前浏览器。
              </p>
            </div>
          </div>
          <Button variant="secondary" className="shrink-0 justify-center" onClick={resetReview}>
            <RotateCcw className="size-4" aria-hidden="true" />
            重置验收数据
          </Button>
        </div>
      </aside>

      <ReadingWorkshopPage
        learner={READING_REVIEW_LEARNER}
        learnerProfile={READING_REVIEW_PROFILE}
        initialMaterial={READING_REVIEW_MATERIAL}
        initialMaterialId={READING_REVIEW_MATERIAL.id}
        initialSourceLabel="BinnAgent 团队验收示例 · 城市与自然"
        readingTrackMode
        backLabel="返回验收说明"
        onBack={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
      />
    </div>
  )
}
