import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, RefreshCw, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { ErrorState } from '@/components/ui/ErrorState'
import { LoadingState } from '@/components/ui/LoadingState'
import { StatusBanner } from '@/components/ui/StatusBanner'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import { debugFetch } from '@/shared/api/debugClient'

type Profile = 'strict' | 'interactive' | 'trusted_integration'
interface Policy { profile: Profile; allowed_domains: string[]; allow_network: boolean; allow_same_origin: boolean; allow_storage: boolean; allow_navigation: boolean; allow_popups: boolean }

const profileCopy: Record<Profile, { title: string; description: string }> = {
  strict: { title: '默认安全', description: '本地交互、脚本桥接与数据图片；不允许外联请求。' },
  interactive: { title: '互动增强', description: '提高组件资源与运行时间上限；仍不允许外联请求。' },
  trusted_integration: { title: '受信集成', description: '仅允许向下方 HTTPS 域名白名单发起 fetch 请求。' },
}

export function SandboxPermissionsPage() {
  const [policy, setPolicy] = useState<Policy | null>(null)
  const [profile, setProfile] = useState<Profile>('strict')
  const [domains, setDomains] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const response = await debugFetch('/api/debug/sandbox-policy')
      if (!response.ok) throw new Error('Sandbox policy unavailable')
      const next = (await response.json() as { policy: Policy }).policy
      setPolicy(next); setProfile(next.profile); setDomains(next.allowed_domains.join('\n'))
    } catch { setError('沙箱权限策略暂时无法加载。') } finally { setLoading(false) }
  }, [])
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [load])

  const save = async () => {
    setSaving(true); setSaved(false); setError(null)
    const allowed_domains = domains.split(/[\n,]/).map((value) => value.trim()).filter(Boolean)
    try {
      const response = await debugFetch('/api/debug/sandbox-policy', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ profile, allowed_domains }) })
      if (!response.ok) throw new Error('Sandbox policy update failed')
      const next = (await response.json() as { policy: Policy }).policy
      setPolicy(next); setProfile(next.profile); setDomains(next.allowed_domains.join('\n')); setSaved(true)
    } catch { setError('保存失败。域名必须是纯 HTTPS 主机名，例如 api.example.com。') } finally { setSaving(false) }
  }

  if (loading && !policy) return <LoadingState title="正在读取沙箱权限" description="正在加载运行中的隔离策略…" />
  if (!policy) return <ErrorState title="沙箱权限不可用" description={error ?? '无法读取策略。'} action={<Button onClick={() => void load()}>重试</Button>} />
  return <div className="space-y-4">
    <StatusBanner tone={policy.allow_network ? 'warning' : 'success'} title={policy.allow_network ? '受信网络访问已开启' : '沙箱保持本地隔离'} action={<Button variant="secondary" onClick={() => void load()} disabled={saving}><RefreshCw className="size-4" />刷新</Button>}>
      策略会作用于 Expression Lab 与 AI 对话中的互动组件；变更会持久化，并在新生成或重新打开的组件上生效。
    </StatusBanner>
    {error ? <StatusBanner tone="warning">{error}</StatusBanner> : null}
    {saved ? <StatusBanner tone="success" title="已保存"><CheckCircle2 className="size-4" />运行策略已更新。</StatusBanner> : null}
    <SurfaceCard>
      <div className="flex gap-3"><ShieldCheck className="mt-1 size-5 text-cyan-600" /><div><h2 className="font-black text-slate-950">权限档位</h2><p className="text-sm text-slate-600">选择最小可用权限；白名单只在“受信集成”档位启用。</p></div></div>
      <div className="mt-4 grid gap-3 lg:grid-cols-3">{(Object.keys(profileCopy) as Profile[]).map((id) => <button key={id} type="button" onClick={() => setProfile(id)} className={`rounded-xl border p-4 text-left ${profile === id ? 'border-cyan-400 bg-cyan-50' : 'border-slate-200 hover:border-cyan-200'}`}><p className="font-black text-slate-950">{profileCopy[id].title}</p><p className="mt-1 text-sm leading-6 text-slate-600">{profileCopy[id].description}</p></button>)}</div>
      <label className="mt-5 block"><span className="text-sm font-black text-slate-950">允许外联的域名</span><span className="ml-2 text-xs text-slate-500">每行一个，不含协议、路径或通配符</span><textarea value={domains} onChange={(event) => setDomains(event.target.value)} disabled={profile !== 'trusted_integration'} rows={5} placeholder={'api.example.com\ncdn.example.com'} className="mt-2 w-full rounded-lg border border-slate-200 p-3 font-mono text-sm disabled:bg-slate-100" /></label>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3"><p className="flex items-start gap-2 text-xs leading-5 text-slate-500"><AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" />同源、存储、顶层跳转与弹窗始终禁止；这些边界不可由 AI 组件放开。</p><Button onClick={() => void save()} disabled={saving}>{saving ? '正在保存' : '保存沙箱策略'}</Button></div>
    </SurfaceCard>
  </div>
}
