import { RotateCcw, Settings, X } from 'lucide-react'
import { useId, useState } from 'react'
import type { LearningPreferences } from '@/hooks/useLearningPreferences'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { IconButton } from '@/components/ui/IconButton'
import { useFocusTrap } from '@/hooks/useFocusTrap'

interface LearningSettingsDialogProps {
  open: boolean
  preferences: LearningPreferences
  onClose: () => void
  onReset: () => void
  onUpdate: (patch: Partial<LearningPreferences>) => void
}

export function LearningSettingsDialog({
  open,
  preferences,
  onClose,
  onReset,
  onUpdate,
}: LearningSettingsDialogProps) {
  const titleId = useId()
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false)
  const { containerRef, handleKeyDown } = useFocusTrap<HTMLElement>({
    isActive: open && !isResetConfirmOpen,
    onEscape: onClose,
  })

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center px-3 py-4 sm:items-center">
      <button
        type="button"
        aria-label="关闭学习设置"
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
        className="relative max-h-[calc(100dvh-2rem)] w-full max-w-2xl overflow-y-auto overscroll-contain rounded-xl border border-slate-200 bg-white shadow-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-slate-100 bg-white px-5 py-4">
          <div className="flex min-w-0 items-start gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
              <Settings className="size-5" />
            </span>
            <div className="min-w-0">
              <h2 id={titleId} className="text-lg font-black text-slate-950">学习设置</h2>
              <p className="mt-1 text-sm leading-6 text-slate-500">
                设置会即时保存在当前学习者本机，下次进入词汇任务时自动生效。
              </p>
            </div>
          </div>
          <IconButton label="关闭学习设置" onClick={onClose}>
            <X className="size-4" />
          </IconButton>
        </div>

        <div className="space-y-5 px-5 py-5">
          <SettingsGroup title="默认词汇练习">
            <SegmentedChoice
              label="默认模式"
              options={[
                { label: '认识新词', value: 'new' },
                { label: '今日复习', value: 'review' },
                { label: '听音拼写', value: 'spelling' },
              ]}
              value={preferences.defaultPracticeMode}
              onChange={(defaultPracticeMode) => onUpdate({ defaultPracticeMode })}
            />
            <SegmentedChoice
              label="默认数量"
              options={[
                { label: '5', value: '5' },
                { label: '10', value: '10' },
                { label: '15', value: '15' },
                { label: '20', value: '20' },
              ]}
              value={String(preferences.defaultLimit)}
              onChange={(value) => onUpdate({ defaultLimit: Number(value) })}
            />
            <SegmentedChoice
              label="发音偏好"
              options={[
                { label: '英音', value: 'uk' },
                { label: '美音', value: 'us' },
                { label: '跟随词典', value: 'auto' },
              ]}
              value={preferences.pronunciationAccent}
              onChange={(pronunciationAccent) => onUpdate({ pronunciationAccent })}
            />
          </SettingsGroup>

          <SettingsGroup title="进入任务">
            <ToggleRow
              checked={preferences.showSetupBeforePractice}
              description="关闭后，点击练习入口会按默认设置直接开始。"
              label="进入练习前显示设置页"
              name="show_setup_before_practice"
              onChange={(showSetupBeforePractice) => onUpdate({ showSetupBeforePractice })}
            />
            <ToggleRow
              checked={preferences.scopeUnitVocabularyByDefault}
              description="从教材单元进入词汇任务时，默认只练当前单元词汇。"
              label="教材单元词汇限定当前单元"
              name="scope_unit_vocabulary_by_default"
              onChange={(scopeUnitVocabularyByDefault) => onUpdate({ scopeUnitVocabularyByDefault })}
            />
          </SettingsGroup>

          <SettingsGroup title="练习行为">
            <ToggleRow
              checked={preferences.autoPlayPronunciation}
              description="听写和复习进入新题时自动播放一次发音。"
              label="自动播放发音"
              name="auto_play_pronunciation"
              onChange={(autoPlayPronunciation) => onUpdate({ autoPlayPronunciation })}
            />
            <ToggleRow
              checked={preferences.autoCheckSpelling}
              description="拼写填满目标长度后自动检查。"
              label="拼写填满后自动检查"
              name="auto_check_spelling"
              onChange={(autoCheckSpelling) => onUpdate({ autoCheckSpelling })}
            />
            <ToggleRow
              checked={preferences.autoAdvanceAfterPractice}
              description="拼写答对后短暂停留，再进入下一题。"
              label="答对后自动进入下一题"
              name="auto_advance_after_practice"
              onChange={(autoAdvanceAfterPractice) => onUpdate({ autoAdvanceAfterPractice })}
            />
          </SettingsGroup>
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-slate-100 px-5 py-4 sm:flex-row sm:justify-between">
          <Button variant="secondary" onClick={() => setIsResetConfirmOpen(true)}>
            <RotateCcw className="size-4" />
            恢复默认
          </Button>
          <Button onClick={onClose}>完成</Button>
        </div>
      </section>
      <ConfirmDialog
        open={isResetConfirmOpen}
        title="恢复默认学习设置？"
        description="恢复后会立即覆盖当前学习者本机保存的练习默认模式、数量和自动播放等偏好。"
        confirmLabel="恢复默认"
        cancelLabel="继续编辑"
        danger
        onCancel={() => setIsResetConfirmOpen(false)}
        onConfirm={() => {
          onReset()
          setIsResetConfirmOpen(false)
        }}
      />
    </div>
  )
}

function SettingsGroup({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <section className="rounded-lg border border-slate-200 p-4">
      <h3 className="text-sm font-black text-slate-950">{title}</h3>
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  )
}

function SegmentedChoice<TValue extends string>({
  label,
  onChange,
  options,
  value,
}: {
  label: string
  options: Array<{ label: string; value: TValue }>
  value: TValue
  onChange: (value: TValue) => void
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-[128px_minmax(0,1fr)] sm:items-center">
      <p className="text-sm font-bold text-slate-700">{label}</p>
      <div className="grid gap-2 sm:grid-cols-3" role="group" aria-label={label}>
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={value === option.value}
            onClick={() => onChange(option.value)}
            className={`rounded-lg border px-3 py-2 text-sm font-bold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
              value === option.value
                ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                : 'border-slate-200 bg-white text-slate-600 hover:border-indigo-200 hover:text-indigo-700'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
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
