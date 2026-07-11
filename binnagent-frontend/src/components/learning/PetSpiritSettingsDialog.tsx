import { RotateCcw, Sparkles, X } from 'lucide-react'
import { useId } from 'react'
import { Button } from '@/components/ui/Button'
import { IconButton } from '@/components/ui/IconButton'
import type { PetSpiritPreferences } from '@/components/ui/ToastContext'
import { useFocusTrap } from '@/hooks/useFocusTrap'

export function PetSpiritSettingsDialog({
  open,
  preferences,
  onClose,
  onResetIntroductions,
  onUpdate,
}: {
  open: boolean
  preferences: PetSpiritPreferences
  onClose: () => void
  onResetIntroductions: () => void
  onUpdate: (patch: Partial<PetSpiritPreferences>) => void
}) {
  const titleId = useId()
  const { containerRef, handleKeyDown } = useFocusTrap<HTMLElement>({ isActive: open, onEscape: onClose })
  if (!open) return null

  return (
    <div className="fixed inset-0 z-[110] flex items-end justify-center px-3 py-4 sm:items-center">
      <button type="button" aria-label="关闭宠物精灵设置" className="absolute inset-0 bg-slate-950/35" onClick={onClose} />
      <section
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        className="relative w-full max-w-xl overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
          <div className="flex items-start gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-sky-50 text-sky-600"><Sparkles className="size-5" /></span>
            <div>
              <h2 id={titleId} className="text-lg font-black text-slate-950">宠物精灵设置</h2>
              <p className="mt-1 text-sm leading-6 text-slate-500">小冰会负责通知、功能引导和学习反馈。设置仅保存在当前浏览器。</p>
            </div>
          </div>
          <IconButton label="关闭宠物精灵设置" onClick={onClose}><X className="size-4" /></IconButton>
        </header>
        <div className="space-y-3 p-5">
          <ToggleRow
            checked={preferences.alwaysVisible}
            label="让小冰一直陪伴"
            description="关闭后，小冰平时会休息，但有重要消息时仍会出现。"
            onChange={(alwaysVisible) => onUpdate({ alwaysVisible })}
          />
          <ToggleRow
            checked={preferences.autonomousMotion}
            label="允许自主小动作"
            description="空闲时会张望、工作、伸懒腰或打哈欠；关闭后仍保留通知和点击反馈。"
            onChange={(autonomousMotion) => onUpdate({ autonomousMotion })}
          />
          <RangeRow
            disabled={!preferences.autonomousMotion}
            label="静置动作频率"
            description="调节小冰观察、伸懒腰和打哈欠的间隔。"
            min={3}
            max={20}
            value={preferences.idleMotionInterval}
            onChange={(idleMotionInterval) => onUpdate({ idleMotionInterval })}
          />
          <ToggleRow
            checked={preferences.introductionsEnabled}
            label="首次进入功能时介绍"
            description="每个新界面只介绍一次，不会反复打扰。"
            onChange={(introductionsEnabled) => onUpdate({ introductionsEnabled })}
          />
          <ToggleRow
            checked={preferences.reducedMotion}
            label="减少动态效果"
            description="保留表情反馈，同时减少漂浮和弹跳动画。"
            onChange={(reducedMotion) => onUpdate({ reducedMotion })}
          />
          <button type="button" className="flex w-full items-center gap-3 rounded-lg border border-slate-200 px-4 py-3 text-left transition hover:border-indigo-200 hover:bg-indigo-50/40" onClick={onResetIntroductions}>
            <RotateCcw className="size-4 text-indigo-600" />
            <span><span className="block text-sm font-bold text-slate-800">重新播放功能介绍</span><span className="mt-0.5 block text-xs text-slate-500">清除已介绍记录，下次进入页面时重新说明。</span></span>
          </button>
        </div>
        <footer className="flex justify-end border-t border-slate-100 px-5 py-4"><Button onClick={onClose}>完成</Button></footer>
      </section>
    </div>
  )
}

function ToggleRow({ checked, description, label, onChange }: { checked: boolean; description: string; label: string; onChange: (checked: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 rounded-lg border border-slate-200 px-4 py-3">
      <span><span className="block text-sm font-bold text-slate-800">{label}</span><span className="mt-0.5 block text-xs leading-5 text-slate-500">{description}</span></span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="size-4 accent-indigo-600" />
    </label>
  )
}

function RangeRow({ description, disabled, label, max, min, onChange, value }: {
  description: string
  disabled?: boolean
  label: string
  max: number
  min: number
  onChange: (value: number) => void
  value: number
}) {
  return (
    <label className={`block rounded-lg border border-slate-200 px-4 py-3 ${disabled ? 'opacity-50' : ''}`}>
      <span className="flex items-center justify-between gap-3">
        <span>
          <span className="block text-sm font-bold text-slate-800">{label}</span>
          <span className="mt-0.5 block text-xs leading-5 text-slate-500">{description}</span>
        </span>
        <output className="shrink-0 rounded-full bg-sky-50 px-2.5 py-1 text-xs font-black text-sky-700">约 {value} 秒</output>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={1}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-3 h-2 w-full cursor-pointer accent-sky-600 disabled:cursor-not-allowed"
        aria-label={label}
      />
      <span className="mt-1 flex justify-between text-[11px] font-semibold text-slate-400"><span>更活跃</span><span>更安静</span></span>
    </label>
  )
}
