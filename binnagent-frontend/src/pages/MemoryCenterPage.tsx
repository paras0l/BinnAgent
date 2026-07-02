import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  ArchiveX,
  CheckCircle2,
  Download,
  Pencil,
  RotateCcw,
  Sparkles,
  Trash2,
} from 'lucide-react'
import { FeatureHero } from '@/components/layout/FeatureHero'
import { PageShell } from '@/components/layout/PageShell'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { LoadingState } from '@/components/ui/LoadingState'
import { SurfaceCard } from '@/components/ui/SurfaceCard'
import { EvidencePanel } from '@/components/learning/EvidencePanel'
import { ReasonCard } from '@/components/learning/ReasonCard'
import type { Learner, MemoryCardItem, MemoryCenter } from '@/types'
import { useToast } from '@/hooks/useToast'
import { debugFetch } from '@/shared/api/debugClient'

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
  const [isResetDialogOpen, setIsResetDialogOpen] = useState(false)

  const loadMemory = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await debugFetch(`/api/learners/${learner.id}/memory/center`)
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
      const response = await debugFetch(`/api/learners/${learner.id}/memory/curate`, { method: 'POST' })
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
      const response = await debugFetch(`/api/learners/${learner.id}/memory/export`)
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
      const response = await debugFetch(`/api/learners/${learner.id}/memory/settings`, {
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
    setBusyId('reset-plan')
    try {
      const response = await debugFetch(`/api/learners/${learner.id}/memory/reset-plan`, { method: 'POST' })
      if (!response.ok) throw new Error('Reset plan failed')
      await loadMemory()
      showToast('已重置学习计划。', { variant: 'success' })
    } catch (err) {
      console.error('Reset plan error:', err)
      showToast('重置计划失败，请稍后重试。', { variant: 'error' })
    } finally {
      setBusyId(null)
      setIsResetDialogOpen(false)
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
      const response = await debugFetch(
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
    return <LoadingState title="正在读取学习记忆" description="正在加载长期记忆、推荐原因、证据和控制设置..." />
  }

  return (
    <PageShell>
        <FeatureHero
          eyebrow="Memory Control"
          title="我的学习记忆"
          description="查看 BinnAgent 记住了什么、证据来自哪里，以及这些记忆如何影响下一步推荐。"
          stats={[
            { label: '记忆事件', value: memory?.metrics.memory_write_count ?? 0 },
            { label: '用户操作', value: memory?.metrics.memory_operation_count ?? 0 },
            { label: '删除记录', value: memory?.metrics.memory_user_deleted_count ?? 0, tone: 'warning' },
            { label: '检索命中率', value: `${memory?.metrics.memory_hit_rate ?? 0}%`, tone: 'primary' },
          ]}
          actions={
            <>
            <Button variant="secondary" onClick={handleCurate} disabled={busyId === 'curate'}>
              <Sparkles className="size-4" />
              整理记忆
            </Button>
            <Button onClick={handleExport} disabled={busyId === 'export'}>
              <Download className="size-4" />
              导出
            </Button>
            <Button variant="danger" onClick={() => setIsResetDialogOpen(true)} disabled={busyId === 'reset-plan'}>
              <RotateCcw className="size-4" />
              重置计划
            </Button>
            </>
          }
        />

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

        <ReasonCard
          title="今天为什么推荐这些任务"
          reason={memory?.recommendation_reason ?? '正在建立可解释推荐。'}
          evidence={(memory?.cards ?? []).slice(0, 3).map((card) => card.title)}
          outcome="你可以编辑、删除、不再使用或标记已改善，后续推荐会排除被禁用的记忆。"
        />

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
      <ConfirmDialog
        open={isResetDialogOpen}
        title="重置当前学习计划？"
        description="未完成任务会被标记为已重置，后续推荐会重新根据你的记忆和练习记录安排。"
        confirmLabel="重置计划"
        danger
        isBusy={busyId === 'reset-plan'}
        onCancel={() => setIsResetDialogOpen(false)}
        onConfirm={() => void handleResetPlan()}
      />

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
    </PageShell>
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
    <SurfaceCard>
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
      <div className="mt-4">
        <EvidencePanel items={card.evidence} />
      </div>
      <p className="mt-3 text-xs font-semibold text-emerald-700">{card.impact}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        <IconAction label="我已改善" icon={<CheckCircle2 className="size-4" />} onClick={onImproved} disabled={busy} />
        {card.editable && <IconAction label="编辑" icon={<Pencil className="size-4" />} onClick={onEdit} disabled={busy} />}
        <IconAction label="不再使用" icon={<ArchiveX className="size-4" />} onClick={onDisable} disabled={busy} />
        <IconAction label="删除" icon={<Trash2 className="size-4" />} onClick={onDelete} disabled={busy} danger />
      </div>
    </SurfaceCard>
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
