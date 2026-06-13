import { useState } from 'react'
import { RotateCcw } from 'lucide-react'

interface VocabReviewCardProps {
  word: string
  definition?: string | null
  example?: string | null
  currentIndex: number
  totalCount: number
  onRate: (rating: 1 | 2 | 3 | 4) => void
}

export function VocabReviewCard({
  word,
  definition,
  example,
  currentIndex,
  totalCount,
  onRate,
}: VocabReviewCardProps) {
  const [isFlipped, setIsFlipped] = useState(false)

  const handleFlip = () => setIsFlipped(!isFlipped)

  const ratings = [
    { label: '忘记', value: 1 as const, color: 'bg-error' },
    { label: '模糊', value: 2 as const, color: 'bg-warning' },
    { label: '记住', value: 3 as const, color: 'bg-success' },
    { label: '熟练', value: 4 as const, color: 'bg-primary' },
  ]

  return (
    <div className="flex flex-col items-center gap-4">
      <div
        className="relative w-full max-w-md h-64 cursor-pointer perspective-1000"
        onClick={handleFlip}
      >
        <div
          className={`absolute inset-0 transition-transform duration-500 transform-style-3d ${
            isFlipped ? 'rotate-y-180' : ''
          }`}
        >
          <div className="absolute inset-0 flex flex-col items-center justify-center rounded-2xl border bg-card p-8 backface-hidden">
            <p className="text-4xl font-bold text-foreground">{word}</p>
            <div className="mt-4 flex items-center gap-2 text-muted-foreground">
              <RotateCcw className="h-4 w-4" />
              <span className="text-sm">点击翻转</span>
            </div>
          </div>

          <div className="absolute inset-0 flex flex-col items-center justify-center rounded-2xl border bg-card p-8 backface-hidden rotate-y-180">
            <p className="text-2xl font-bold text-foreground">{word}</p>
            <p className="mt-2 text-lg text-muted-foreground">
              {definition || '暂无释义，建议先补充词典信息'}
            </p>
            <p className="mt-4 text-sm text-muted-foreground italic">
              {example ? `"${example}"` : '暂无例句'}
            </p>
          </div>
        </div>
      </div>

      {isFlipped && (
        <div className="flex gap-2">
          {ratings.map((rating) => (
            <button
              key={rating.value}
              onClick={() => onRate(rating.value)}
              className={`px-4 py-2 rounded-lg text-primary-foreground transition-colors ${rating.color}`}
            >
              {rating.label}
            </button>
          ))}
        </div>
      )}

      <p className="text-sm text-muted-foreground">
        第 {currentIndex + 1} 个 / 共 {totalCount} 个
      </p>
    </div>
  )
}
