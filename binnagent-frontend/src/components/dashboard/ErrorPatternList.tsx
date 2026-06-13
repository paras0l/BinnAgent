import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

interface ErrorPattern {
  id: string
  name: string
  count: number
  example?: string | null
}

interface ErrorPatternListProps {
  patterns: ErrorPattern[]
}

export function ErrorPatternList({ patterns }: ErrorPatternListProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  return (
    <div className="rounded-xl border bg-card p-6">
      <h3 className="text-lg font-semibold text-foreground mb-4">错误模式分析</h3>
      <div className="space-y-2">
        {patterns.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            暂无错因记录。完成对话、写作批改或词汇复习后，这里会逐步沉淀你的薄弱点。
          </p>
        ) : patterns.map((pattern) => (
          <div
            key={pattern.id}
            className="rounded-lg border p-4 cursor-pointer transition-colors hover:bg-muted"
            onClick={() => setExpandedId(expandedId === pattern.id ? null : pattern.id)}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="font-medium text-foreground">{pattern.name}</span>
                <span className="text-sm text-muted-foreground">({pattern.count}次)</span>
              </div>
              {expandedId === pattern.id ? (
                <ChevronUp className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              )}
            </div>
            {expandedId === pattern.id && (
              <p className="mt-2 text-sm text-muted-foreground">
                {pattern.example || '还没有可展示的例句证据。'}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
