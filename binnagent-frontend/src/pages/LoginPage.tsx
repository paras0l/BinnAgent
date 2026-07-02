import { useState } from 'react'
import type { FormEvent } from 'react'
import { Bot, Loader2 } from 'lucide-react'
import type { Learner } from '@/types'
import { useToast } from '@/hooks/useToast'
import { Button } from '@/components/ui/Button'
import { FormField } from '@/components/ui/FormField'
import { SurfaceCard } from '@/components/ui/SurfaceCard'

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
    <main className="min-h-screen bg-[#f6f7f9] px-6 py-10">
      <div className="mx-auto grid min-h-[calc(100vh-5rem)] w-full max-w-[1180px] items-center gap-6 lg:grid-cols-[1fr_440px]">
        <section>
          <div className="flex items-center gap-3">
            <div className="flex size-12 items-center justify-center rounded-[13px] bg-primary/10 text-primary">
              <Bot className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm font-black uppercase tracking-wide text-primary">BinnAgent</p>
              <h1 className="mt-2 text-4xl font-black tracking-tight text-slate-950">创建你的英语学习空间</h1>
            </div>
          </div>
          <p className="mt-5 max-w-2xl text-sm leading-6 text-slate-600">
            围绕词汇、教材、写作和学习状态持续练习。进入后系统会根据你的练习记录安排复习，并解释推荐原因。
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {['今日学习路径', '词汇复习计划', '写作表达资产', '学习状态跟踪'].map((item) => (
              <div key={item} className="rounded-[13px] border border-slate-200 bg-white p-4 text-sm font-bold text-slate-700 shadow-[0_4px_14px_rgba(15,23,42,0.05)]">
                {item}
              </div>
            ))}
          </div>
        </section>

      <SurfaceCard className="w-full">
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
          <FormField
            label="昵称"
            value={nickname}
            onChange={(event) => setNickname(event.target.value)}
            placeholder="例如：Alex"
            maxLength={100}
          />

          <FormField
            label="邮箱（可选）"
            description="用于在下次打开时恢复学习记录。"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="alex@example.com"
            type="email"
            maxLength={255}
          />

          <Button
            type="submit"
            disabled={isSubmitting}
            className="w-full"
          >
            {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
            进入学习空间
          </Button>
        </form>
      </SurfaceCard>
      </div>
    </main>
  )
}
