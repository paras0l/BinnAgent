import type { ReactNode } from 'react'
import { Button } from './Button'

interface ConfirmDialogProps {
  open: boolean
  title: string
  description: string
  confirmLabel: string
  cancelLabel?: string
  isBusy?: boolean
  danger?: boolean
  children?: ReactNode
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel = '取消',
  isBusy = false,
  danger = false,
  children,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4">
      <div className="w-full max-w-md rounded-[13px] border border-slate-200 bg-white p-5 shadow-xl">
        <h2 className="text-lg font-black text-slate-950">{title}</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">{description}</p>
        {children && <div className="mt-4">{children}</div>}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={onCancel} disabled={isBusy}>{cancelLabel}</Button>
          <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm} disabled={isBusy}>{confirmLabel}</Button>
        </div>
      </div>
    </div>
  )
}
