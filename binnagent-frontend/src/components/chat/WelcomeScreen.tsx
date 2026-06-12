import { Bot, BookOpen, MessageSquare, Mic } from 'lucide-react'

interface WelcomeScreenProps {
  onStartLesson: () => void
  onReviewVocab: () => void
  onPracticeSpeaking: () => void
}

export function WelcomeScreen({ onStartLesson, onReviewVocab, onPracticeSpeaking }: WelcomeScreenProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-8 p-8">
      <div className="flex size-20 items-center justify-center rounded-full bg-primary/10">
        <Bot className="h-10 w-10 text-primary" />
      </div>
      
      <div className="text-center">
        <h2 className="text-2xl font-bold text-foreground">你好！我是 BinnAgent</h2>
        <p className="mt-2 text-muted-foreground">你的 AI 英语学习伙伴</p>
      </div>

      <div className="flex flex-col gap-3 w-full max-w-md">
        <button
          onClick={onStartLesson}
          className="flex items-center gap-3 rounded-xl border p-4 text-left transition-colors hover:bg-muted"
        >
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10">
            <MessageSquare className="h-5 w-5 text-primary" />
          </div>
          <div>
            <p className="font-medium text-foreground">开始一节对话课</p>
            <p className="text-sm text-muted-foreground">和 AI 进行英语对话练习</p>
          </div>
        </button>

        <button
          onClick={onReviewVocab}
          className="flex items-center gap-3 rounded-xl border p-4 text-left transition-colors hover:bg-muted"
        >
          <div className="flex size-10 items-center justify-center rounded-lg bg-success/10">
            <BookOpen className="h-5 w-5 text-success" />
          </div>
          <div>
            <p className="font-medium text-foreground">复习今天词汇</p>
            <p className="text-sm text-muted-foreground">使用间隔重复法复习单词</p>
          </div>
        </button>

        <button
          onClick={onPracticeSpeaking}
          className="flex items-center gap-3 rounded-xl border p-4 text-left transition-colors hover:bg-muted"
        >
          <div className="flex size-10 items-center justify-center rounded-lg bg-accent/10">
            <Mic className="h-5 w-5 text-accent" />
          </div>
          <div>
            <p className="font-medium text-foreground">练习口语场景</p>
            <p className="text-sm text-muted-foreground">模拟真实场景进行口语练习</p>
          </div>
        </button>
      </div>
    </div>
  )
}
