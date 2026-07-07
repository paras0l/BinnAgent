import { useId, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  ChevronDown,
  Clock3,
  Database,
  MessageCircle,
  Pause,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Save,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  Upload,
  UserRoundCheck,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { IconButton } from '@/components/ui/IconButton'
import { useFocusTrap } from '@/hooks/useFocusTrap'
import { useToast } from '@/hooks/useToast'

type SourceStatus = 'active' | 'paused' | 'revoked'
type ParticipantRole = 'learner' | 'partner' | 'unknown'

interface GroupSourceConfig {
  id: string
  displayName: string
  externalGroupKey: string
  status: SourceStatus
  rawRetentionDays: number
  lastSeenAt: string
  pendingSignals: number
  autoGenerateRecommendations: boolean
  autoWriteCandidates: boolean
  autoApplyHighConfidenceTaggedSignals: boolean
  confidenceThreshold: number
}

interface ParticipantMapping {
  id: string
  sourceId: string
  displayName: string
  externalMemberKey: string
  learnerName: string | null
  role: ParticipantRole
  analysisEnabled: boolean
  lastMessageAt: string
}

type SourceDraft = Pick<GroupSourceConfig, 'displayName' | 'externalGroupKey' | 'status' | 'rawRetentionDays'>

type DangerAction =
  | { type: 'remove-source'; sourceId: string }
  | { type: 'delete-cache'; sourceId: string }
  | null

const RETENTION_OPTIONS = [1, 3, 7, 14, 30]
const CONFIDENCE_OPTIONS = [0.7, 0.8, 0.9]
const CURRENT_LEARNER_LABEL = '当前 learner'

const INITIAL_SOURCES: GroupSourceConfig[] = [
  {
    id: 'source-study-partner',
    displayName: '七年级英语学习搭子群',
    externalGroupKey: 'wechat-grade7-study-partner',
    status: 'active',
    rawRetentionDays: 7,
    lastSeenAt: '今天 20:42',
    pendingSignals: 4,
    autoGenerateRecommendations: true,
    autoWriteCandidates: true,
    autoApplyHighConfidenceTaggedSignals: false,
    confidenceThreshold: 0.8,
  },
  {
    id: 'source-writing',
    displayName: '写作互助群',
    externalGroupKey: 'wechat-writing-workshop',
    status: 'paused',
    rawRetentionDays: 14,
    lastSeenAt: '昨天 22:10',
    pendingSignals: 1,
    autoGenerateRecommendations: true,
    autoWriteCandidates: false,
    autoApplyHighConfidenceTaggedSignals: false,
    confidenceThreshold: 0.9,
  },
]

const INITIAL_PARTICIPANTS: ParticipantMapping[] = [
  {
    id: 'participant-xiaolin',
    sourceId: 'source-study-partner',
    displayName: '小林',
    externalMemberKey: 'wechat-member-xiaolin',
    learnerName: CURRENT_LEARNER_LABEL,
    role: 'learner',
    analysisEnabled: true,
    lastMessageAt: '今天 20:31',
  },
  {
    id: 'participant-may',
    sourceId: 'source-study-partner',
    displayName: 'May',
    externalMemberKey: 'wechat-member-may',
    learnerName: null,
    role: 'partner',
    analysisEnabled: false,
    lastMessageAt: '今天 20:28',
  },
  {
    id: 'participant-writing-host',
    sourceId: 'source-writing',
    displayName: '作文打卡主持人',
    externalMemberKey: 'wechat-member-writing-host',
    learnerName: null,
    role: 'unknown',
    analysisEnabled: false,
    lastMessageAt: '昨天 21:55',
  },
]

interface GroupLearningSettingsDialogProps {
  open: boolean
  onClose: () => void
}

export function GroupLearningSettingsDialog({
  open,
  onClose,
}: GroupLearningSettingsDialogProps) {
  const titleId = useId()
  const { showToast } = useToast()
  const [isEnabled, setIsEnabled] = useState(true)
  const [sources, setSources] = useState<GroupSourceConfig[]>(() => INITIAL_SOURCES)
  const [participants, setParticipants] = useState<ParticipantMapping[]>(() => INITIAL_PARTICIPANTS)
  const [selectedSourceId, setSelectedSourceId] = useState(INITIAL_SOURCES[0]?.id ?? '')
  const [editingSourceId, setEditingSourceId] = useState<string | null>(null)
  const [sourceDraft, setSourceDraft] = useState<SourceDraft>(() => createEmptySourceDraft())
  const [nextSourceIndex, setNextSourceIndex] = useState(1)
  const [memberQuery, setMemberQuery] = useState('')
  const [dangerAction, setDangerAction] = useState<DangerAction>(null)
  const [lastImportSummary, setLastImportSummary] = useState('尚未导入本地 JSON。')
  const [lastSavedArea, setLastSavedArea] = useState<string | null>(null)
  const { containerRef, handleKeyDown } = useFocusTrap<HTMLElement>({
    isActive: open && !dangerAction,
    onEscape: onClose,
  })

  const selectedSource = sources.find((source) => source.id === selectedSourceId) ?? sources[0] ?? null
  const selectedParticipants = useMemo(() => {
    const query = memberQuery.trim().toLowerCase()
    return participants.filter((participant) => {
      const matchesSource = selectedSource ? participant.sourceId === selectedSource.id : false
      if (!matchesSource) return false
      if (!query) return true
      return `${participant.displayName} ${participant.externalMemberKey}`.toLowerCase().includes(query)
    })
  }, [memberQuery, participants, selectedSource])

  const activeSourceCount = sources.filter((source) => source.status === 'active').length
  const mappedParticipantCount = participants.filter((participant) => participant.role === 'learner' && participant.analysisEnabled).length

  if (!open) return null

  const startAddSource = () => {
    setEditingSourceId('new')
    setSourceDraft(createEmptySourceDraft())
  }

  const startEditSource = (source: GroupSourceConfig) => {
    setEditingSourceId(source.id)
    setSourceDraft({
      displayName: source.displayName,
      externalGroupKey: source.externalGroupKey,
      status: source.status,
      rawRetentionDays: source.rawRetentionDays,
    })
  }

  const saveSourceDraft = () => {
    const displayName = sourceDraft.displayName.trim()
    const externalGroupKey = sourceDraft.externalGroupKey.trim()
    if (!displayName || !externalGroupKey) {
      showToast('群名称和群标识不能为空。', { variant: 'warning' })
      return
    }
    if (!RETENTION_OPTIONS.includes(sourceDraft.rawRetentionDays)) {
      showToast('原始消息保留天数只能选择 1、3、7、14 或 30 天。', { variant: 'warning' })
      return
    }
    const duplicated = sources.some((source) => {
      return source.externalGroupKey === externalGroupKey && source.id !== editingSourceId
    })
    if (duplicated) {
      showToast('这个群标识已经在白名单里。', { variant: 'warning' })
      return
    }

    if (editingSourceId === 'new') {
      const nextSource: GroupSourceConfig = {
        id: `source-custom-${nextSourceIndex}`,
        displayName,
        externalGroupKey,
        status: sourceDraft.status,
        rawRetentionDays: sourceDraft.rawRetentionDays,
        lastSeenAt: '尚未同步',
        pendingSignals: 0,
        autoGenerateRecommendations: true,
        autoWriteCandidates: true,
        autoApplyHighConfidenceTaggedSignals: false,
        confidenceThreshold: 0.8,
      }
      setSources((items) => [...items, nextSource])
      setNextSourceIndex((value) => value + 1)
      setSelectedSourceId(nextSource.id)
      markSaved('白名单群组已添加')
    } else {
      setSources((items) => items.map((source) => (
        source.id === editingSourceId
          ? { ...source, displayName, externalGroupKey, status: sourceDraft.status, rawRetentionDays: sourceDraft.rawRetentionDays }
          : source
      )))
      markSaved('白名单群组已保存')
    }

    setEditingSourceId(null)
  }

  const updateSource = (sourceId: string, patch: Partial<GroupSourceConfig>, message?: string) => {
    setSources((items) => items.map((source) => source.id === sourceId ? { ...source, ...patch } : source))
    if (message) markSaved(message)
  }

  const updateParticipant = (participantId: string, patch: Partial<ParticipantMapping>) => {
    setParticipants((items) => items.map((participant) => (
      participant.id === participantId ? { ...participant, ...patch } : participant
    )))
  }

  const saveParticipants = () => {
    markSaved('成员映射已保存')
  }

  const confirmDangerAction = () => {
    if (!dangerAction) return
    if (dangerAction.type === 'remove-source') {
      setSources((items) => {
        const next = items.filter((source) => source.id !== dangerAction.sourceId)
        if (!next.some((source) => source.id === selectedSourceId)) {
          setSelectedSourceId(next[0]?.id ?? '')
        }
        return next
      })
      setParticipants((items) => items.filter((participant) => participant.sourceId !== dangerAction.sourceId))
      markSaved('已移除白名单群组')
    } else {
      updateSource(dangerAction.sourceId, { lastSeenAt: '原始缓存已删除' }, '已删除该群原始消息缓存')
    }
    setDangerAction(null)
  }

  const handleImportJson = (file: File | undefined) => {
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result ?? '{}')) as unknown
        const messageCount = countImportedMessages(parsed)
        const ignoredCount = Math.max(0, Math.round(messageCount * 0.35))
        const generatedCount = Math.max(0, Math.round((messageCount - ignoredCount) * 0.55))
        setLastImportSummary(`导入成功 ${messageCount} 条 · 重复跳过 0 条 · 生成候选线索 ${generatedCount} 条 · 成员规则忽略 ${ignoredCount} 条`)
        markSaved('本地 JSON 已导入')
      } catch {
        showToast('JSON 格式无法解析，请检查导出的消息文件。', { variant: 'error' })
      }
    }
    reader.readAsText(file)
  }

  const markSaved = (message: string) => {
    setLastSavedArea(message)
    showToast(message, { variant: 'success' })
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center px-3 py-4 sm:items-center">
      <button
        type="button"
        aria-label="关闭群聊学习线索设置"
        className="absolute inset-0 bg-slate-950/35 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        onClick={onClose}
      />
      <section
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        className="relative max-h-[calc(100dvh-2rem)] w-full max-w-5xl overflow-y-auto overscroll-contain rounded-xl border border-slate-200 bg-white shadow-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-slate-100 bg-white px-5 py-4">
          <div className="flex min-w-0 items-start gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-primary">
              <MessageCircle className="size-5" />
            </span>
            <div className="min-w-0">
              <h2 id={titleId} className="text-lg font-black text-slate-950">群聊学习线索设置</h2>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                添加白名单群组、映射成员、配置缓存保留和写入策略。
              </p>
            </div>
          </div>
          <IconButton label="关闭群聊学习线索设置" onClick={onClose}>
            <X className="size-4" />
          </IconButton>
        </div>

        <div className="grid gap-5 px-5 py-5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="space-y-5">
            <SettingsSection
              description="关闭后停止读取新消息；已有线索仍可处理。"
              icon={<SlidersHorizontal className="size-4" />}
              title="读取开关"
            >
              <ToggleRow
                checked={isEnabled}
                description="关闭后不读取任何白名单群的新消息。"
                label="启用群聊学习线索捕捉"
                name="group_learning_enabled"
                onChange={(checked) => {
                  setIsEnabled(checked)
                  markSaved(checked ? '已启用群聊学习线索捕捉' : '已暂停全部群聊读取')
                }}
              />
              <div className="grid gap-2 sm:grid-cols-3">
                <MetricTile label="白名单群组" value={`${sources.length} 个`} />
                <MetricTile label="活跃来源" value={`${activeSourceCount} 个`} />
                <MetricTile label="分析成员" value={`${mappedParticipantCount} 位`} />
              </div>
            </SettingsSection>

            <SettingsSection
              action={<Button variant="secondary" onClick={startAddSource}><Plus className="size-4" />添加群组</Button>}
              description="只有加入白名单的微信群会被读取。"
              icon={<MessageCircle className="size-4" />}
              title="群组白名单"
            >
              {editingSourceId ? (
                <SourceEditor
                  draft={sourceDraft}
                  isNew={editingSourceId === 'new'}
                  onCancel={() => setEditingSourceId(null)}
                  onChange={setSourceDraft}
                  onSave={saveSourceDraft}
                />
              ) : null}

              {sources.length ? (
                <div className="space-y-3">
                  {sources.map((source) => (
                    <SourceRow
                      key={source.id}
                      source={source}
                      selected={selectedSource?.id === source.id}
                      onDelete={() => setDangerAction({ type: 'remove-source', sourceId: source.id })}
                      onDeleteCache={() => setDangerAction({ type: 'delete-cache', sourceId: source.id })}
                      onEdit={() => startEditSource(source)}
                      onSelect={() => setSelectedSourceId(source.id)}
                      onToggleStatus={() => updateSource(
                        source.id,
                        { status: source.status === 'active' ? 'paused' : 'active' },
                        source.status === 'active' ? '已暂停该群读取' : '已恢复该群读取',
                      )}
                    />
                  ))}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center">
                  <MessageCircle className="mx-auto size-6 text-slate-400" />
                  <p className="mt-2 text-sm font-black text-slate-950">还没有白名单群组</p>
                  <p className="mt-1 text-sm text-slate-500">添加指定微信群后，BinnAgent 才会读取该群文本消息。</p>
                  <Button className="mt-4" onClick={startAddSource}><Plus className="size-4" />添加群组</Button>
                </div>
              )}
            </SettingsSection>

            <SettingsSection
              description="只有映射为 learner 且开启分析的成员会写入学习资产。"
              icon={<UserRoundCheck className="size-4" />}
              title="成员映射"
            >
              {selectedSource ? (
                <>
                  <div className="grid gap-3 md:grid-cols-[220px_minmax(0,1fr)]">
                    <label className="relative grid gap-1">
                      <span className="text-xs font-bold text-slate-500">当前群组</span>
                      <select
                        value={selectedSource.id}
                        onChange={(event) => setSelectedSourceId(event.currentTarget.value)}
                        className="appearance-none rounded-lg border border-slate-200 bg-white py-2 pl-3 pr-10 text-sm font-bold text-slate-800 outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                      >
                        {sources.map((source) => <option key={source.id} value={source.id}>{source.displayName}</option>)}
                      </select>
                      <ChevronDown className="pointer-events-none absolute bottom-2.5 right-3.5 size-4 text-slate-400" />
                    </label>
                    <label className="relative grid gap-1">
                      <span className="text-xs font-bold text-slate-500">搜索成员</span>
                      <Search className="pointer-events-none absolute bottom-2.5 left-3 size-4 text-slate-400" />
                      <input
                        value={memberQuery}
                        onChange={(event) => setMemberQuery(event.currentTarget.value)}
                        className="rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                        placeholder="搜索显示名或 external_member_key"
                      />
                    </label>
                  </div>
                  <div className="space-y-3">
                    {selectedParticipants.map((participant) => (
                      <ParticipantRow
                        key={participant.id}
                        participant={participant}
                        onChange={(patch) => updateParticipant(participant.id, patch)}
                      />
                    ))}
                    {selectedParticipants.length === 0 ? (
                      <p className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">
                        当前筛选下没有成员。导入消息后，未映射成员会先出现在这里。
                      </p>
                    ) : null}
                  </div>
                  <div className="flex justify-end">
                    <Button onClick={saveParticipants}><Save className="size-4" />保存映射</Button>
                  </div>
                </>
              ) : (
                <p className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500">
                  先添加白名单群组，再配置成员映射。
                </p>
              )}
            </SettingsSection>
          </div>

          <aside className="space-y-5">
            <SettingsSection
              description="控制 raw message 的保留窗口和清理动作。"
              icon={<Database className="size-4" />}
              title="保留与清理"
            >
              {selectedSource ? (
                <>
                  <label className="relative grid gap-1">
                    <span className="text-xs font-bold text-slate-500">原始消息保留天数</span>
                    <select
                      value={selectedSource.rawRetentionDays}
                      onChange={(event) => updateSource(
                        selectedSource.id,
                        { rawRetentionDays: Number(event.currentTarget.value) },
                        '原始消息保留天数已保存',
                      )}
                      className="appearance-none rounded-lg border border-slate-200 bg-white py-2 pl-3 pr-10 text-sm font-bold text-slate-800 outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                    >
                      {RETENTION_OPTIONS.map((days) => <option key={days} value={days}>{days} 天</option>)}
                    </select>
                    <ChevronDown className="pointer-events-none absolute bottom-2.5 right-3.5 size-4 text-slate-400" />
                  </label>
                  <div className="grid gap-2">
                    <Button
                      variant="secondary"
                      className="justify-between"
                      onClick={() => markSaved('已清理过期原始消息缓存')}
                    >
                      清理过期缓存<RefreshCw className="size-4" />
                    </Button>
                    <Button
                      variant="danger"
                      className="justify-between"
                      onClick={() => setDangerAction({ type: 'delete-cache', sourceId: selectedSource.id })}
                    >
                      删除全部原始消息<Trash2 className="size-4" />
                    </Button>
                  </div>
                </>
              ) : null}
            </SettingsSection>

            <SettingsSection
              description="控制线索接受后如何进入学习资产。"
              icon={<ShieldCheck className="size-4" />}
              title="写入策略"
            >
              {selectedSource ? (
                <>
                  <ToggleRow
                    checked={selectedSource.autoGenerateRecommendations}
                    description="开启后，候选线索会生成推荐理由和学习目标。"
                    label="自动生成学习推荐"
                    name="auto_generate_recommendations"
                    onChange={(checked) => updateSource(selectedSource.id, { autoGenerateRecommendations: checked }, '写入策略已保存')}
                  />
                  <ToggleRow
                    checked={selectedSource.autoWriteCandidates}
                    description="开启后，接受线索会写入词汇、好句、语法等候选资产。"
                    label="接受后自动写入候选资产"
                    name="auto_write_candidates"
                    onChange={(checked) => updateSource(selectedSource.id, { autoWriteCandidates: checked }, '写入策略已保存')}
                  />
                  <ToggleRow
                    checked={selectedSource.autoApplyHighConfidenceTaggedSignals}
                    description="仅对 #单词、#语法、#收藏 等主动标签线索生效。"
                    label="高可信标签线索自动进入候选"
                    name="auto_apply_high_confidence_tagged_signals"
                    onChange={(checked) => updateSource(selectedSource.id, { autoApplyHighConfidenceTaggedSignals: checked }, '写入策略已保存')}
                  />
                  <label className="relative grid gap-1">
                    <span className="text-xs font-bold text-slate-500">可信度阈值</span>
                    <select
                      value={selectedSource.confidenceThreshold}
                      onChange={(event) => updateSource(
                        selectedSource.id,
                        { confidenceThreshold: Number(event.currentTarget.value) },
                        '可信度阈值已保存',
                      )}
                      className="appearance-none rounded-lg border border-slate-200 bg-white py-2 pl-3 pr-10 text-sm font-bold text-slate-800 outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                    >
                      {CONFIDENCE_OPTIONS.map((value) => <option key={value} value={value}>{Math.round(value * 100)}%</option>)}
                    </select>
                    <ChevronDown className="pointer-events-none absolute bottom-2.5 right-3.5 size-4 text-slate-400" />
                  </label>
                </>
              ) : null}
            </SettingsSection>

            <SettingsSection
              description="同步状态只是辅助信息，配置仍以上方控件为准。"
              icon={<Clock3 className="size-4" />}
              title="同步与导入"
            >
              <div className="space-y-2 text-sm text-slate-600">
                <StatusLine label="最后同步" value={selectedSource?.lastSeenAt ?? '尚未同步'} />
                <StatusLine label="待确认线索" value={`${selectedSource?.pendingSignals ?? 0} 条`} />
                <StatusLine label="最近导入" value={lastImportSummary} />
              </div>
              <div className="grid gap-2">
                <Button
                  variant="secondary"
                  className="justify-between"
                  onClick={() => {
                    if (selectedSource) updateSource(selectedSource.id, { lastSeenAt: '刚刚' }, '已手动同步一次')
                  }}
                >
                  手动同步一次<RefreshCw className="size-4" />
                </Button>
                <label className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 shadow-sm transition hover:border-primary/30 hover:text-primary">
                  <Upload className="size-4" />
                  导入本地 JSON
                  <input
                    type="file"
                    accept="application/json,.json"
                    className="sr-only"
                    onChange={(event) => {
                      handleImportJson(event.currentTarget.files?.[0])
                      event.currentTarget.value = ''
                    }}
                  />
                </label>
              </div>
            </SettingsSection>
          </aside>
        </div>

        <div className="flex flex-col gap-2 border-t border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs font-bold text-slate-500">
            {lastSavedArea ? `最近保存：${lastSavedArea}` : '修改设置后会显示保存反馈。'}
          </p>
          <Button onClick={onClose}>完成</Button>
        </div>
      </section>

      <ConfirmDialog
        open={Boolean(dangerAction)}
        title={dangerAction?.type === 'remove-source' ? '移除这个白名单群组？' : '删除全部原始消息缓存？'}
        description={dangerAction?.type === 'remove-source'
          ? '移除后不再读取这个群的新消息；你可以选择后续接入 API 时同时删除该群 raw message 缓存。'
          : '删除后无法从原始群消息重新生成线索；已接受的学习资产不会删除。'}
        confirmLabel={dangerAction?.type === 'remove-source' ? '移除' : '删除缓存'}
        danger
        onCancel={() => setDangerAction(null)}
        onConfirm={confirmDangerAction}
      />
    </div>
  )
}

function SettingsSection({
  action,
  children,
  description,
  icon,
  title,
}: {
  action?: ReactNode
  children: ReactNode
  description: string
  icon: ReactNode
  title: string
}) {
  return (
    <section className="rounded-lg border border-slate-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-primary">
            {icon}
            <h3 className="text-sm font-black text-slate-950">{title}</h3>
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">{description}</p>
        </div>
        {action}
      </div>
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  )
}

function SourceEditor({
  draft,
  isNew,
  onCancel,
  onChange,
  onSave,
}: {
  draft: SourceDraft
  isNew: boolean
  onCancel: () => void
  onChange: (draft: SourceDraft) => void
  onSave: () => void
}) {
  return (
    <div className="rounded-lg border border-indigo-100 bg-indigo-50/60 p-3">
      <p className="text-sm font-black text-slate-950">{isNew ? '添加白名单群组' : '编辑白名单群组'}</p>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <TextInput
          label="群名称"
          value={draft.displayName}
          onChange={(displayName) => onChange({ ...draft, displayName })}
          placeholder="例如：七年级英语学习搭子群"
        />
        <TextInput
          label="external_group_key"
          value={draft.externalGroupKey}
          onChange={(externalGroupKey) => onChange({ ...draft, externalGroupKey })}
          placeholder="例如：wechat-grade7-study"
        />
        <SelectField
          label="状态"
          value={draft.status}
          onChange={(status) => onChange({ ...draft, status: status as SourceStatus })}
          options={[
            { label: 'active', value: 'active' },
            { label: 'paused', value: 'paused' },
            { label: 'revoked', value: 'revoked' },
          ]}
        />
        <SelectField
          label="原始消息保留"
          value={String(draft.rawRetentionDays)}
          onChange={(rawRetentionDays) => onChange({ ...draft, rawRetentionDays: Number(rawRetentionDays) })}
          options={RETENTION_OPTIONS.map((days) => ({ label: `${days} 天`, value: String(days) }))}
        />
      </div>
      <div className="mt-3 flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel}>取消</Button>
        <Button onClick={onSave}><Save className="size-4" />保存</Button>
      </div>
    </div>
  )
}

function SourceRow({
  onDelete,
  onDeleteCache,
  onEdit,
  onSelect,
  onToggleStatus,
  selected,
  source,
}: {
  onDelete: () => void
  onDeleteCache: () => void
  onEdit: () => void
  onSelect: () => void
  onToggleStatus: () => void
  selected: boolean
  source: GroupSourceConfig
}) {
  return (
    <article className={`rounded-lg border p-3 ${selected ? 'border-indigo-300 bg-indigo-50/50' : 'border-slate-100 bg-slate-50'}`}>
      <button type="button" className="w-full text-left" onClick={onSelect}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-black text-slate-950">{source.displayName}</p>
            <p className="mt-1 break-all text-xs font-bold text-slate-500">{source.externalGroupKey}</p>
          </div>
          <StatusPill status={source.status} />
        </div>
        <div className="mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-3">
          <span>最后同步：<b className="text-slate-700">{source.lastSeenAt}</b></span>
          <span>待确认：<b className="text-slate-700">{source.pendingSignals}</b></span>
          <span>缓存：<b className="text-slate-700">{source.rawRetentionDays} 天</b></span>
        </div>
      </button>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="secondary" onClick={onToggleStatus}>
          {source.status === 'active' ? <Pause className="size-4" /> : <Play className="size-4" />}
          {source.status === 'active' ? '暂停' : '恢复'}
        </Button>
        <Button variant="secondary" onClick={onEdit}><Pencil className="size-4" />编辑</Button>
        <Button variant="secondary" onClick={onDeleteCache}><Database className="size-4" />删缓存</Button>
        <Button variant="danger" onClick={onDelete}><Trash2 className="size-4" />移除</Button>
      </div>
    </article>
  )
}

function ParticipantRow({
  onChange,
  participant,
}: {
  onChange: (patch: Partial<ParticipantMapping>) => void
  participant: ParticipantMapping
}) {
  return (
    <article className="rounded-lg border border-slate-100 bg-slate-50 p-3">
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_150px_160px_120px] lg:items-end">
        <div className="min-w-0">
          <p className="font-black text-slate-950">{participant.displayName}</p>
          <p className="mt-1 break-all text-xs font-bold text-slate-500">{participant.externalMemberKey}</p>
          <p className="mt-1 text-xs text-slate-500">最近消息：{participant.lastMessageAt}</p>
        </div>
        <SelectField
          label="映射 learner"
          value={participant.learnerName ?? ''}
          onChange={(value) => onChange({ learnerName: value || null, role: value ? 'learner' : 'unknown', analysisEnabled: Boolean(value) })}
          options={[
            { label: '未映射', value: '' },
            { label: CURRENT_LEARNER_LABEL, value: CURRENT_LEARNER_LABEL },
          ]}
        />
        <SelectField
          label="角色"
          value={participant.role}
          onChange={(role) => onChange({ role: role as ParticipantRole, analysisEnabled: role === 'learner' ? participant.analysisEnabled : false })}
          options={[
            { label: 'learner', value: 'learner' },
            { label: 'partner', value: 'partner' },
            { label: 'unknown', value: 'unknown' },
          ]}
        />
        <label className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2">
          <span className="text-xs font-bold text-slate-600">分析</span>
          <input
            type="checkbox"
            checked={participant.analysisEnabled}
            disabled={participant.role !== 'learner'}
            onChange={(event) => onChange({ analysisEnabled: event.currentTarget.checked })}
            className="size-5 accent-indigo-600 disabled:opacity-40"
          />
        </label>
      </div>
      {participant.role !== 'learner' ? (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-white px-3 py-2 text-xs leading-5 text-slate-500">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-500" />
          partner / unknown 成员默认只作上下文，不会写入当前 learner 的学习画像。
        </div>
      ) : null}
    </article>
  )
}

function TextInput({
  label,
  onChange,
  placeholder,
  value,
}: {
  label: string
  onChange: (value: string) => void
  placeholder: string
  value: string
}) {
  return (
    <label className="grid gap-1">
      <span className="text-xs font-bold text-slate-500">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.currentTarget.value)}
        className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
        placeholder={placeholder}
      />
    </label>
  )
}

function SelectField({
  label,
  onChange,
  options,
  value,
}: {
  label: string
  onChange: (value: string) => void
  options: Array<{ label: string; value: string }>
  value: string
}) {
  return (
    <label className="relative grid gap-1">
      <span className="text-xs font-bold text-slate-500">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.currentTarget.value)}
        className="appearance-none rounded-lg border border-slate-200 bg-white py-2 pl-3 pr-10 text-sm font-bold text-slate-800 outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
      >
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
      <ChevronDown className="pointer-events-none absolute bottom-2.5 right-3.5 size-4 text-slate-400" />
    </label>
  )
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
      <p className="text-xs font-bold text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-black text-slate-950">{value}</p>
    </div>
  )
}

function StatusLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 p-3">
      <p className="text-xs font-bold text-slate-500">{label}</p>
      <p className="mt-1 break-words text-sm font-black text-slate-900">{value}</p>
    </div>
  )
}

function StatusPill({ status }: { status: SourceStatus }) {
  const className = {
    active: 'bg-emerald-50 text-emerald-700',
    paused: 'bg-amber-50 text-amber-700',
    revoked: 'bg-slate-100 text-slate-500',
  }[status]
  return <span className={`rounded-full px-2.5 py-1 text-xs font-black ${className}`}>{status}</span>
}

function ToggleRow({
  checked,
  description,
  label,
  name,
  onChange,
}: {
  checked: boolean
  description: string
  label: string
  name: string
  onChange: (checked: boolean) => void
}) {
  const descriptionId = useId()

  return (
    <label className="grid cursor-pointer gap-3 rounded-lg border border-slate-100 bg-slate-50 p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
      <span className="min-w-0">
        <span className="block text-sm font-bold text-slate-900">{label}</span>
        <span id={descriptionId} className="mt-1 block text-xs leading-5 text-slate-500">{description}</span>
      </span>
      <span className="inline-flex items-center justify-between gap-3 sm:justify-end">
        <span className="text-xs font-bold text-slate-500">{checked ? '开启' : '关闭'}</span>
        <input
          type="checkbox"
          name={name}
          checked={checked}
          aria-describedby={descriptionId}
          onChange={(event) => onChange(event.currentTarget.checked)}
          className="size-5 accent-indigo-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        />
      </span>
    </label>
  )
}

function createEmptySourceDraft(): SourceDraft {
  return {
    displayName: '',
    externalGroupKey: '',
    status: 'active',
    rawRetentionDays: 7,
  }
}

function countImportedMessages(value: unknown): number {
  if (Array.isArray(value)) return value.length
  if (value && typeof value === 'object' && 'messages' in value) {
    const messages = (value as { messages?: unknown }).messages
    return Array.isArray(messages) ? messages.length : 0
  }
  return 0
}
