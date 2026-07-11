import { XiaobingAvatar } from '@/components/ui/XiaobingAvatar'

export function TypingIndicator() {
  return (
    <div className="flex items-center gap-3 px-4 py-2" aria-live="polite" aria-label="AI 正在输入">
      <XiaobingAvatar className="size-8 border border-sky-100 bg-sky-50 shadow-sm" />
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
