import { useState } from 'react'
import type { FormEvent } from 'react'
import { Bot, Loader2 } from 'lucide-react'
import type { Learner } from '@/types'
import { useToast } from '@/hooks/useToast'

interface LoginPageProps {
  onLogin: (learner: Learner) => void
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const { showToast } = useToast()
  const [nickname, setNickname] = useState('')
  const [email, setEmail] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const trimmedNickname = nickname.trim()
    const trimmedEmail = email.trim()
    if (!trimmedNickname) {
      showToast('请输入昵称', { variant: 'warning' })
      return
    }

    setIsSubmitting(true)
    try {
      const response = await fetch('/api/learners/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nickname: trimmedNickname,
          email: trimmedEmail || null,
        }),
      })

      if (!response.ok) throw new Error('Login failed')

      const learner: Learner = await response.json()
      localStorage.setItem('binnLearnerId', learner.id)
      localStorage.setItem('binnLearner', JSON.stringify(learner))
      onLogin(learner)
    } catch (err) {
      console.error('Learner login failed:', err)
      showToast('暂时无法进入学习空间，请稍后重试。', { variant: 'error' })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-6 py-10">
      <div className="w-full max-w-md rounded-xl border bg-card p-6 shadow-sm">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground">BinnAgent</h1>
            <p className="text-sm text-muted-foreground">进入你的英语学习空间</p>
          </div>
        </div>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-foreground">昵称</span>
            <input
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
              placeholder="例如：Alex"
              maxLength={100}
            />
          </label>

          <label className="block">
            <span className="mb-1 block text-sm font-medium text-foreground">邮箱（可选）</span>
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary"
              placeholder="用于在下次打开时恢复学习记录"
              type="email"
              maxLength={255}
            />
          </label>

          <button
            type="submit"
            disabled={isSubmitting}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
            进入学习
          </button>
        </form>
      </div>
    </main>
  )
}
