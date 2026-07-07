import { AlertCircle, FileText, LoaderCircle, UploadCloud, X } from 'lucide-react'
import { useId, useRef, useState } from 'react'
import { useFocusTrap } from '@/hooks/useFocusTrap'

interface UploadTextbookDialogProps {
  open: boolean
  onClose: () => void
  onUpload: (file: File) => Promise<void>
}

export function UploadTextbookDialog({ open, onClose, onUpload }: UploadTextbookDialogProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const titleId = useId()
  const [file, setFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { containerRef, handleKeyDown } = useFocusTrap<HTMLElement>({
    isActive: open,
    onEscape: onClose,
    isEscapeEnabled: !isUploading,
  })

  if (!open) return null

  const handleSubmit = async () => {
    if (!file) {
      setError('请选择英语 PDF 教材。')
      return
    }
    setIsUploading(true)
    setError(null)
    try {
      await onUpload(file)
      setFile(null)
      onClose()
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : '上传失败，请稍后重试。')
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="关闭上传教材弹窗"
        className="absolute inset-0 bg-slate-950/35 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        disabled={isUploading}
        onClick={onClose}
      />
      <section
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={handleKeyDown}
        className="relative max-h-[calc(100dvh-2rem)] w-full max-w-lg overflow-y-auto overscroll-contain rounded-2xl bg-white p-6 shadow-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id={titleId} className="text-xl font-extrabold text-slate-950">上传英语教材</h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">支持七到九年级英语 PDF，未知教材会先生成通用目录和校对队列。</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isUploading}
            className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="关闭"
          >
            <X className="size-5" />
          </button>
        </div>

        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="mt-6 flex min-h-40 w-full flex-col items-center justify-center rounded-xl border border-dashed border-indigo-300 bg-indigo-50/40 px-6 text-center transition-colors hover:bg-indigo-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          {file ? <FileText className="size-8 text-indigo-600" /> : <UploadCloud className="size-8 text-indigo-600" />}
          <span className="mt-3 text-sm font-extrabold text-slate-800">{file?.name ?? '选择 PDF 文件'}</span>
          <span className="mt-1 text-xs text-slate-500">最大 50 MB</span>
        </button>
        <input
          ref={inputRef}
          type="file"
          name="textbook_pdf"
          accept="application/pdf,.pdf"
          className="sr-only"
          onChange={(event) => {
            const nextFile = event.target.files?.[0] ?? null
            setFile(nextFile)
            setError(null)
          }}
        />
        {error ? <UploadFailureDetails message={error} /> : null}

        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose} disabled={isUploading} className="rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50">取消</button>
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={isUploading}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-extrabold text-white transition-colors hover:bg-indigo-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isUploading ? <LoaderCircle className="size-4 animate-spin" /> : <UploadCloud className="size-4" />}
            {isUploading ? '正在上传…' : '上传并处理'}
          </button>
        </div>
      </section>
    </div>
  )
}

export function UploadFailureDetails({ message }: { message: string }) {
  const lines = message.split('\n').filter((line) => line.trim().length > 0)
  return (
    <div className="mt-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700" role="alert">
      <div className="flex items-start gap-2">
        <AlertCircle className="mt-0.5 size-4 shrink-0" />
        <div className="min-w-0 space-y-1">
          {lines.map((line, index) => (
            <p key={`${line}-${index}`} className={line.startsWith('- ') ? 'pl-3' : 'font-semibold'}>
              {line}
            </p>
          ))}
        </div>
      </div>
    </div>
  )
}
