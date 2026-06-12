import { useState } from 'react'
import { StatsCards } from '@/components/dashboard/StatsCards'
import { VocabReviewCard } from '@/components/dashboard/VocabReviewCard'
import { ErrorPatternList } from '@/components/dashboard/ErrorPatternList'
import { LearningGoalProgress } from '@/components/dashboard/LearningGoalProgress'

const sampleVocab = [
  { word: 'abundant', definition: '丰富的', example: 'The country has abundant natural resources.' },
  { word: 'elaborate', definition: '精心制作的', example: 'She gave an elaborate explanation of the theory.' },
  { word: 'substantial', definition: '大量的', example: 'They made substantial progress on the project.' },
]

const sampleErrors = [
  { id: '1', name: '时态混淆', count: 3, example: 'She go → She goes' },
  { id: '2', name: '冠词缺失', count: 2, example: 'I want book → I want a book' },
  { id: '3', name: '主谓不一致', count: 1, example: 'They goes → They go' },
]

export function DashboardPage() {
  const [currentVocabIndex, setCurrentVocabIndex] = useState(0)
  const currentVocab = sampleVocab[currentVocabIndex]

  const handleRate = (rating: 1 | 2 | 3 | 4) => {
    console.log('Rated:', rating)
    setCurrentVocabIndex(prev => (prev + 1) % sampleVocab.length)
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <StatsCards
        todayReviews={12}
        streakDays={5}
        accuracy={85}
        totalVocab={156}
      />

      <VocabReviewCard
        key={currentVocab.word}
        word={currentVocab.word}
        definition={currentVocab.definition}
        example={currentVocab.example}
        currentIndex={currentVocabIndex}
        totalCount={sampleVocab.length}
        onRate={handleRate}
      />

      <ErrorPatternList patterns={sampleErrors} />

      <LearningGoalProgress
        dailyGoal={{ completed: 8, total: 10 }}
        weeklyGoal={{ completed: 5, total: 10 }}
      />
    </div>
  )
}
