import { Bot } from 'lucide-react'

export function TypingIndicator() {
  return (
    <div className="flex items-center gap-3 px-4 py-2" aria-live="polite" aria-label="AI 正在输入">
      <div className="flex size-8 items-center justify-center rounded-full bg-accent/20">
        <Bot className="h-4 w-4 text-accent" />
      </div>
      <div className="flex gap-1">
        {[0, 1, 2].map(i => (
          <span
            key={i}
            className="size-2 animate-bounce rounded-full bg-muted-foreground/40 motion-reduce:animate-none"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
      </div>
    </div>
  )
}
