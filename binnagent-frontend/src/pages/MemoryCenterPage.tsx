import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  ArchiveX,
  CheckCircle2,
  Download,
  Pencil,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Trash2,
} from 'lucide-react'
import type { Learner, MemoryCardItem, MemoryCenter } from '@/types'
import { useToast } from '@/hooks/useToast'

interface MemoryCenterPageProps {
  learner: Learner
}

export function MemoryCenterPage({ learner }: MemoryCenterPageProps) {
  const { showToast } = useToast()
  const [memory, setMemory] = useState<MemoryCenter | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [activeSkill, setActiveSkill] = useState<string>('all')
  const [editingCard, setEditingCard] = useState<MemoryCardItem | null>(null)
  const [editText, setEditText] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)

  const loadMemory = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`/api/learners/${learner.id}/memory/center`)
      if (!response.ok) throw new Error('Failed to load memory')
      const data: MemoryCenter = await response.json()
      setMemory(data)
    } catch (err) {
      console.error('Memory center error:', err)
      showToast('学习记忆暂时无法加载，请稍后重试。', { variant: 'error' })
    } finally {
      setIsLoading(false)
    }
  }, [learner.id, showToast])

  useEffect(() => {
    const timer = window.setTimeout(() => void loadMemory(), 0)
    return () => window.clearTimeout(timer)
  }, [loadMemory])

  const skills = useMemo(() => {
    const values = new Set((memory?.cards ?? []).map((card) => card.skill))
    return ['all', ...Array.from(values)]
  }, [memory])

  const cards = useMemo(() => {
    const allCards = memory?.cards ?? []
    if (activeSkill === 'all') return allCards
    return allCards.filter((card) => card.skill === activeSkill)
  }, [activeSkill, memory])

  const handleCurate = async () => {
    setBusyId('curate')
    try {
      const response = await fetch(`/api/learners/${learner.id}/memory/curate`, { method: 'POST' })
      if (!response.ok) throw new Error('Curate failed')
      await loadMemory()
      showToast('已整理学习记忆。', { variant: 'success' })
    } catch (err) {
      console.error('Curate memory error:', err)
      showToast('整理记忆失败，请稍后重试。', { variant: 'error' })
    } finally {
      setBusyId(null)
    }
  }

  const handleExport = async () => {
    setBusyId('export')
    try {
      const response = await fetch(`/api/learners/${learner.id}/memory/export`)
      if (!response.ok) throw new Error('Export failed')
      const blob = new Blob([JSON.stringify(await response.json(), null, 2)], {
        type: 'application/json',
      })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `binnagent-memory-${learner.id}.json`
      anchor.click()
      URL.revokeObjectURL(url)
      showToast('已导出学习记忆。', { variant: 'success' })
    } catch (err) {
      console.error('Export memory error:', err)
      showToast('导出失败，请稍后重试。', { variant: 'error' })
    } finally {
      setBusyId(null)
    }
  }

  const updateSetting = async (key: keyof MemoryCenter['settings'], value: boolean) => {
    setBusyId(`setting-${key}`)
    try {
      const response = await fetch(`/api/learners/${learner.id}/memory/settings`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: value }),
      })
      if (!response.ok) throw new Error('Update settings failed')
      await loadMemory()
      showToast('已更新记忆设置。', { variant: 'success' })
    } catch (err) {
      console.error('Memory settings error:', err)
      showToast('更新设置失败，请稍后重试。', { variant: 'error' })
    } finally {
      setBusyId(null)
    }
  }

  const handleResetPlan = async () => {
    const shouldReset = window.confirm('确定重置当前学习计划吗？未完成任务会被标记为已重置。')
    if (!shouldReset) return
    setBusyId('reset-plan')
    try {
      const response = await fetch(`/api/learners/${learner.id}/memory/reset-plan`, { method: 'POST' })
      if (!response.ok) throw new Error('Reset plan failed')
      await loadMemory()
      showToast('已重置学习计划。', { variant: 'success' })
    } catch (err) {
      console.error('Reset plan error:', err)
      showToast('重置计划失败，请稍后重试。', { variant: 'error' })
    } finally {
      setBusyId(null)
    }
  }

  const controlCard = async (
    card: MemoryCardItem,
    operation: 'edit' | 'delete' | 'disable' | 'mark_improved',
    content?: string
  ) => {
    const target = splitCardId(card.id)
    if (!target) return
    setBusyId(card.id)
    try {
      const response = await fetch(
        `/api/learners/${learner.id}/memory/items/${target.type}/${target.id}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ operation, content }),
        }
      )
      if (!response.ok) throw new Error('Memory control failed')
      setEditingCard(null)
      setEditText('')
      await loadMemory()
      showToast('已更新这条记忆。', { variant: 'success' })
    } catch (err) {
      console.error('Memory control error:', err)
      showToast('操作失败，请稍后重试。', { variant: 'error' })
    } finally {
      setBusyId(null)
    }
  }

  if (isLoading && !memory) {
    return (
      <div className="flex min-h-[calc(100vh-4rem)] items-center justify-center bg-[#f7f8fa] text-sm text-slate-500">
        <RefreshCw className="mr-2 size-4 animate-spin" />
        正在读取学习记忆...
      </div>
    )
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-[#f7f8fa] px-4 py-7 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1180px] space-y-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">
              <ShieldCheck className="size-3.5" />
              用户可控
            </div>
            <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-950">我的学习记忆</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
              查看 BinnAgent 记住了什么、证据来自哪里，以及这些记忆如何影响下一步推荐。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={handleCurate} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 shadow-sm transition hover:border-emerald-300 hover:text-emerald-700 disabled:opacity-60" disabled={busyId === 'curate'}>
              <Sparkles className="size-4" />
              整理记忆
            </button>
            <button type="button" onClick={handleExport} className="inline-flex items-center gap-2 rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-slate-800 disabled:opacity-60" disabled={busyId === 'export'}>
              <Download className="size-4" />
              导出
            </button>
            <button type="button" onClick={handleResetPlan} className="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-white px-4 py-2.5 text-sm font-bold text-rose-600 shadow-sm transition hover:bg-rose-50 disabled:opacity-60" disabled={busyId === 'reset-plan'}>
              <RotateCcw className="size-4" />
              重置计划
            </button>
          </div>
        </div>

        <section className="grid gap-3 md:grid-cols-4">
          <Metric label="记忆事件" value={memory?.metrics.memory_write_count ?? 0} />
          <Metric label="用户操作" value={memory?.metrics.memory_operation_count ?? 0} />
          <Metric label="删除记录" value={memory?.metrics.memory_user_deleted_count ?? 0} />
          <Metric label="检索命中率" value={memory?.metrics.memory_hit_rate ?? 0} suffix="%" />
        </section>

        <section className="grid gap-3 md:grid-cols-3">
          <SettingSwitch
            label="情绪 / 节奏记忆"
            description="关闭时，不长期保存学习时间、疲劳和节奏类推断。"
            checked={memory?.settings.emotion_rhythm_enabled ?? false}
            disabled={busyId === 'setting-emotion_rhythm_enabled'}
            onChange={(checked) => void updateSetting('emotion_rhythm_enabled', checked)}
          />
          <SettingSwitch
            label="推断偏好记忆"
            description="允许保存可删除的反馈风格、例句偏好等学习偏好。"
            checked={memory?.settings.inferred_preferences_enabled ?? true}
            disabled={busyId === 'setting-inferred_preferences_enabled'}
            onChange={(checked) => void updateSetting('inferred_preferences_enabled', checked)}
          />
          <SettingSwitch
            label="低置信记忆入上下文"
            description="关闭时，低置信推断只展示为候选，不进入推荐上下文。"
            checked={memory?.settings.low_confidence_memory_enabled ?? false}
            disabled={busyId === 'setting-low_confidence_memory_enabled'}
            onChange={(checked) => void updateSetting('low_confidence_memory_enabled', checked)}
          />
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-start gap-3">
            <Sparkles className="mt-0.5 size-5 text-emerald-600" />
            <div>
              <h2 className="text-base font-black text-slate-950">今天为什么推荐这些任务</h2>
              <p className="mt-1 text-sm leading-6 text-slate-600">
                {memory?.recommendation_reason ?? '正在建立可解释推荐。'}
              </p>
            </div>
          </div>
        </section>

        <div className="flex gap-2 overflow-x-auto pb-1">
          {skills.map((skill) => (
            <button
              key={skill}
              type="button"
              onClick={() => setActiveSkill(skill)}
              className={`rounded-full px-3 py-1.5 text-xs font-bold transition ${
                activeSkill === skill
                  ? 'bg-slate-950 text-white'
                  : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300'
              }`}
            >
              {skill === 'all' ? '全部' : skill}
            </button>
          ))}
        </div>

        <section className="grid gap-4 lg:grid-cols-2">
          {cards.map((card) => (
            <MemoryCard
              key={card.id}
              card={card}
              busy={busyId === card.id}
              onEdit={() => {
                setEditingCard(card)
                setEditText(card.content)
              }}
              onDelete={() => void controlCard(card, 'delete')}
              onDisable={() => void controlCard(card, 'disable')}
              onImproved={() => void controlCard(card, 'mark_improved')}
            />
          ))}
        </section>

        {cards.length === 0 && (
          <div className="rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
            当前筛选下还没有可展示的学习记忆。
          </div>
        )}
      </div>

      {editingCard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4">
          <div className="w-full max-w-xl rounded-lg bg-white p-5 shadow-xl">
            <h2 className="text-lg font-black text-slate-950">编辑记忆</h2>
            <textarea
              value={editText}
              onChange={(event) => setEditText(event.target.value)}
              className="mt-4 min-h-32 w-full rounded-lg border border-slate-200 p-3 text-sm outline-none focus:border-emerald-400"
            />
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={() => setEditingCard(null)} className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-bold text-slate-600">
                取消
              </button>
              <button type="button" onClick={() => void controlCard(editingCard, 'edit', editText)} className="rounded-lg bg-slate-950 px-4 py-2 text-sm font-bold text-white">
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function MemoryCard({
  card,
  busy,
  onEdit,
  onDelete,
  onDisable,
  onImproved,
}: {
  card: MemoryCardItem
  busy: boolean
  onEdit: () => void
  onDelete: () => void
  onDisable: () => void
  onImproved: () => void
}) {
  return (
    <article className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs font-bold uppercase tracking-wide text-slate-400">{card.skill}</div>
          <h3 className="mt-1 text-base font-black text-slate-950">{card.title}</h3>
        </div>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600">
          {Math.round(card.confidence * 100)}%
        </span>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-700">{card.content}</p>
      <div className="mt-4 rounded-lg bg-slate-50 p-3">
        <div className="text-xs font-bold text-slate-500">来源证据</div>
        <div className="mt-1 space-y-1 text-xs text-slate-600">
          {card.evidence.length > 0 ? card.evidence.map((item) => <div key={item}>{item}</div>) : <div>暂无证据链接</div>}
        </div>
      </div>
      <p className="mt-3 text-xs font-semibold text-emerald-700">{card.impact}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <IconAction label="我已改善" icon={<CheckCircle2 className="size-4" />} onClick={onImproved} disabled={busy} />
        {card.editable && <IconAction label="编辑" icon={<Pencil className="size-4" />} onClick={onEdit} disabled={busy} />}
        <IconAction label="不再使用" icon={<ArchiveX className="size-4" />} onClick={onDisable} disabled={busy} />
        <IconAction label="删除" icon={<Trash2 className="size-4" />} onClick={onDelete} disabled={busy} danger />
      </div>
    </article>
  )
}

function IconAction({
  label,
  icon,
  onClick,
  disabled,
  danger = false,
}: {
  label: string
  icon: ReactNode
  onClick: () => void
  disabled?: boolean
  danger?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-bold transition disabled:opacity-50 ${
        danger
          ? 'border-rose-200 text-rose-600 hover:bg-rose-50'
          : 'border-slate-200 text-slate-600 hover:bg-slate-50'
      }`}
    >
      {icon}
      {label}
    </button>
  )
}

function Metric({ label, value, suffix = '' }: { label: string; value: number; suffix?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-bold text-slate-400">{label}</div>
      <div className="mt-2 text-2xl font-black text-slate-950">{value}{suffix}</div>
    </div>
  )
}

function SettingSwitch({
  label,
  description,
  checked,
  disabled,
  onChange,
}: {
  label: string
  description: string
  checked: boolean
  disabled?: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <span>
        <span className="block text-sm font-black text-slate-950">{label}</span>
        <span className="mt-1 block text-xs leading-5 text-slate-500">{description}</span>
      </span>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1 size-4 accent-emerald-600"
      />
    </label>
  )
}

function splitCardId(value: string): { type: string; id: string } | null {
  const index = value.indexOf(':')
  if (index <= 0) return null
  return { type: value.slice(0, index), id: value.slice(index + 1) }
}
