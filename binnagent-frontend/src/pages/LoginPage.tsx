import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import {
  ArrowLeft,
  Bot,
  KeyRound,
  Loader2,
  Mail,
  ShieldCheck,
  UserPlus,
  Users,
} from 'lucide-react'
import type { Learner } from '@/types'
import { useToast } from '@/hooks/useToast'
import { Button } from '@/components/ui/Button'
import { FormField } from '@/components/ui/FormField'
import { StatusBanner } from '@/components/ui/StatusBanner'
import { SurfaceCard } from '@/components/ui/SurfaceCard'

interface LoginPageProps {
  learnerToBind?: Learner | null
  onLogin: (learner: Learner) => void
}

interface LearnerAccount {
  id: string
  nickname: string
}

type LoginView = 'email' | 'verify' | 'accounts' | 'register'

export function LoginPage({ learnerToBind = null, onLogin }: LoginPageProps) {
  const { showToast } = useToast()
  const [view, setView] = useState<LoginView>('email')
  const [email, setEmail] = useState('')
  const [confirmedEmail, setConfirmedEmail] = useState('')
  const [accounts, setAccounts] = useState<LearnerAccount[]>([])
  const [nickname, setNickname] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [verificationToken, setVerificationToken] = useState('')
  const [resendSeconds, setResendSeconds] = useState(0)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [activeAccountId, setActiveAccountId] = useState<string | null>(null)

  useEffect(() => {
    if (resendSeconds <= 0) return
    const timeout = window.setTimeout(
      () => setResendSeconds((seconds) => Math.max(0, seconds - 1)),
      1000,
    )
    return () => window.clearTimeout(timeout)
  }, [resendSeconds])

  const completeLogin = (learner: Learner) => {
    try {
      localStorage.setItem('binnLearnerId', learner.id)
      localStorage.setItem('binnLearner', JSON.stringify(learner))
    } catch {
      // Private browsers may deny storage; the in-memory session remains usable.
    }
    onLogin(learner)
  }

  const handleEmailSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const normalizedEmail = email.trim().toLowerCase()
    if (!normalizedEmail) {
      showToast('请输入邮箱', { variant: 'warning' })
      return
    }

    await requestVerificationCode(normalizedEmail)
  }

  const requestVerificationCode = async (normalizedEmail: string) => {
    setIsSubmitting(true)
    try {
      const response = await fetch('/api/email-verifications', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: normalizedEmail }),
      })
      if (!response.ok) throw new Error(await responseMessage(response, '验证码发送失败'))
      const result = await response.json() as { resend_after_seconds: number }
      setConfirmedEmail(normalizedEmail)
      setVerificationCode('')
      setVerificationToken('')
      setResendSeconds(result.resend_after_seconds)
      setView('verify')
      showToast('验证码已发送，请检查邮箱。', { variant: 'success' })
    } catch (error) {
      console.error('Email verification request failed:', error)
      showToast(error instanceof Error ? error.message : '暂时无法发送验证码，请稍后重试。', { variant: 'error' })
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleVerificationSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!/^\d{6}$/.test(verificationCode)) {
      showToast('请输入 6 位数字验证码', { variant: 'warning' })
      return
    }

    setIsSubmitting(true)
    try {
      const confirmResponse = await fetch('/api/email-verifications/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: confirmedEmail, code: verificationCode }),
      })
      if (!confirmResponse.ok) {
        throw new Error(await responseMessage(confirmResponse, '验证码校验失败'))
      }
      const confirmation = await confirmResponse.json() as { verification_token: string }
      const token = confirmation.verification_token
      setVerificationToken(token)

      if (learnerToBind) {
        const bindResponse = await fetch(`/api/learners/${learnerToBind.id}/email`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: confirmedEmail, verification_token: token }),
        })
        if (!bindResponse.ok) throw new Error(await responseMessage(bindResponse, '邮箱绑定失败'))
        completeLogin(await bindResponse.json() as Learner)
        return
      }

      const lookupResponse = await fetch('/api/learners/lookup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: confirmedEmail, verification_token: token }),
      })
      if (!lookupResponse.ok) throw new Error(await responseMessage(lookupResponse, '邮箱查询失败'))
      const result = await lookupResponse.json() as { email: string; accounts: LearnerAccount[] }
      setAccounts(result.accounts)
      setView(result.accounts.length > 0 ? 'accounts' : 'register')
    } catch (error) {
      console.error('Email verification confirmation failed:', error)
      const message = error instanceof Error && error.message === 'Verification code is invalid or expired'
        ? '验证码错误或已失效，请重试。'
        : error instanceof Error ? error.message : '暂时无法验证邮箱，请稍后重试。'
      showToast(message, { variant: 'error' })
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleAccountLogin = async (account: LearnerAccount) => {
    setActiveAccountId(account.id)
    try {
      const response = await fetch('/api/learners/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: confirmedEmail,
          learner_id: account.id,
          verification_token: verificationToken,
        }),
      })
      if (!response.ok) throw new Error(await responseMessage(response, '登录失败'))
      completeLogin(await response.json() as Learner)
    } catch (error) {
      console.error('Learner login failed:', error)
      showToast(error instanceof Error ? error.message : '暂时无法登录，请稍后重试。', { variant: 'error' })
    } finally {
      setActiveAccountId(null)
    }
  }

  const handleRegistration = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmedNickname = nickname.trim()
    const normalizedInviteCode = inviteCode.trim().toUpperCase()
    if (!trimmedNickname || !normalizedInviteCode) {
      showToast('请输入昵称和邀请码', { variant: 'warning' })
      return
    }

    setIsSubmitting(true)
    try {
      const response = await fetch('/api/learners', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nickname: trimmedNickname,
          email: confirmedEmail,
          invite_code: normalizedInviteCode,
          verification_token: verificationToken,
        }),
      })
      if (!response.ok) throw new Error(await responseMessage(response, '注册失败'))
      completeLogin(await response.json() as Learner)
    } catch (error) {
      console.error('Learner registration failed:', error)
      const message = error instanceof Error && error.message === 'Invalid invitation code'
        ? '邀请码无效，请向邀请人确认后重试。'
        : error instanceof Error ? error.message : '暂时无法注册，请稍后重试。'
      showToast(message, { variant: 'error' })
    } finally {
      setIsSubmitting(false)
    }
  }

  const restartEmailLookup = () => {
    setView('email')
    setAccounts([])
    setConfirmedEmail('')
    setNickname('')
    setInviteCode('')
    setVerificationCode('')
    setVerificationToken('')
    setResendSeconds(0)
  }

  const isEmailView = view === 'email'

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
              <div
                key={item}
                className="rounded-[13px] border border-slate-200 bg-white p-4 text-sm font-bold text-slate-700 shadow-[0_4px_14px_rgba(15,23,42,0.05)] transition-[border-color,box-shadow,transform] duration-150 hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-[0_10px_24px_rgba(15,23,42,0.08)]"
              >
                {item}
              </div>
            ))}
          </div>
        </section>

        <SurfaceCard className="w-full">
          <div className="mb-6 flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
              {view === 'register' ? <UserPlus className="h-5 w-5" /> : view === 'verify' ? <ShieldCheck className="h-5 w-5" /> : <Mail className="h-5 w-5" />}
            </div>
            <div>
              <h2 className="text-xl font-bold text-foreground">
                {view === 'verify' ? '验证邮箱' : learnerToBind ? '绑定邮箱后继续' : view === 'register' ? '注册新学习者' : view === 'accounts' ? '选择学习者' : '邮箱登录'}
              </h2>
              <p className="text-sm text-muted-foreground">
                {view === 'verify' ? confirmedEmail : learnerToBind ? `当前学习者：${learnerToBind.nickname}` : view === 'email' ? '验证邮箱后查询学习者账号' : confirmedEmail}
              </p>
            </div>
          </div>

          {isEmailView ? (
            <form className="space-y-4" onSubmit={handleEmailSubmit}>
              {learnerToBind ? (
                <StatusBanner tone="warning" title="需要完成账号升级">
                  旧账号必须绑定邮箱，之后才能继续进入学习空间。
                </StatusBanner>
              ) : null}
              <FormField
                label="邮箱"
                description="同一邮箱可以绑定并管理多个学习者。"
                name="learner_email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="alex@example.com"
                type="email"
                required
                spellCheck={false}
                maxLength={255}
              />
              <Button type="submit" disabled={isSubmitting} className="w-full">
                {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {learnerToBind ? '发送验证码并绑定' : '发送邮箱验证码'}
              </Button>
            </form>
          ) : null}

          {view === 'verify' ? (
            <form className="space-y-4" onSubmit={handleVerificationSubmit}>
              <StatusBanner title="验证码已发送">
                请输入邮件中的 6 位验证码。验证码 10 分钟内有效。
              </StatusBanner>
              <FormField
                label="邮箱验证码"
                description="如果没有收到，请检查垃圾邮件或等待一分钟后重发。"
                name="email_verification_code"
                autoComplete="one-time-code"
                inputMode="numeric"
                pattern="[0-9]{6}"
                value={verificationCode}
                onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                required
                spellCheck={false}
                maxLength={6}
              />
              <Button type="submit" disabled={isSubmitting} className="w-full">
                {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="size-4" />}
                验证并继续
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={isSubmitting || resendSeconds > 0}
                className="w-full"
                onClick={() => void requestVerificationCode(confirmedEmail)}
              >
                {resendSeconds > 0 ? `${resendSeconds} 秒后可重发` : '重新发送验证码'}
              </Button>
              <BackToEmailButton onClick={restartEmailLookup} />
            </form>
          ) : null}

          {view === 'accounts' && !learnerToBind ? (
            <div className="space-y-4">
              <StatusBanner title="找到学习者">
                请选择要进入的学习空间，也可以继续注册新的学习者。
              </StatusBanner>
              <div className="space-y-2" role="list" aria-label="学习者账号">
                {accounts.map((account) => (
                  <button
                    key={account.id}
                    type="button"
                    role="listitem"
                    disabled={activeAccountId !== null}
                    onClick={() => void handleAccountLogin(account)}
                    className="flex w-full items-center gap-3 rounded-lg border border-slate-200 px-3 py-3 text-left transition hover:border-primary/40 hover:bg-primary/5 focus-visible:outline-2 focus-visible:outline-primary disabled:cursor-wait disabled:opacity-60"
                  >
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-600">
                      {activeAccountId === account.id ? <Loader2 className="size-4 animate-spin" /> : <Users className="size-4" />}
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-black text-slate-950">{account.nickname}</span>
                      <span className="block text-xs text-slate-500">账号 {account.id.slice(0, 8)}</span>
                    </span>
                  </button>
                ))}
              </div>
              <Button type="button" variant="secondary" className="w-full" onClick={() => setView('register')}>
                <UserPlus className="size-4" />
                使用邀请码注册新学习者
              </Button>
              <BackToEmailButton onClick={restartEmailLookup} />
            </div>
          ) : null}

          {view === 'register' && !learnerToBind ? (
            <form className="space-y-4" onSubmit={handleRegistration}>
              <StatusBanner tone={accounts.length === 0 ? 'warning' : 'info'}>
                {accounts.length === 0 ? '该邮箱下还没有学习者，请使用邀请码完成首次注册。' : '新学习者会拥有独立学习记录和自己的邀请码。'}
              </StatusBanner>
              <FormField
                label="昵称"
                name="learner_nickname"
                autoComplete="name"
                value={nickname}
                onChange={(event) => setNickname(event.target.value)}
                placeholder="例如：Alex"
                required
                maxLength={100}
              />
              <FormField label="邀请码" description="向邀请你加入的用户获取；邀请码可重复邀请多个新用户。">
                <span className="relative block">
                  <KeyRound className="pointer-events-none absolute left-3 top-2.5 size-4 text-slate-400" />
                  <input
                    className="w-full rounded-lg border border-slate-200 bg-white py-2 pr-3 pl-9 text-sm uppercase outline-none transition-colors focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/20"
                    name="invite_code"
                    autoComplete="off"
                    value={inviteCode}
                    onChange={(event) => setInviteCode(event.target.value.toUpperCase())}
                    placeholder="BINN-XXXXXXXXXX"
                    required
                    spellCheck={false}
                    maxLength={32}
                  />
                </span>
              </FormField>
              <Button type="submit" disabled={isSubmitting} className="w-full">
                {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="size-4" />}
                注册并进入
              </Button>
              <BackToEmailButton onClick={restartEmailLookup} />
            </form>
          ) : null}
        </SurfaceCard>
      </div>
    </main>
  )
}

function BackToEmailButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-bold text-slate-500 transition hover:bg-slate-50 hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-primary"
    >
      <ArrowLeft className="size-4" />
      更换邮箱
    </button>
  )
}

async function responseMessage(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json() as { detail?: string }
    return payload.detail || fallback
  } catch {
    return fallback
  }
}
