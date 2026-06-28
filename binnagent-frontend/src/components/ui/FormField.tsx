import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from 'react'

interface BaseProps {
  label: string
  description?: string
  children?: ReactNode
}

interface InputFieldProps extends BaseProps, InputHTMLAttributes<HTMLInputElement> {
  as?: 'input'
}

interface TextareaFieldProps extends BaseProps, TextareaHTMLAttributes<HTMLTextAreaElement> {
  as: 'textarea'
}

type FormFieldProps = InputFieldProps | TextareaFieldProps

export function FormField({ label, description, children, as = 'input', className = '', ...props }: FormFieldProps) {
  const controlClass = `w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-primary ${className}`

  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-950">{label}</span>
      {description && <span className="mt-1 block text-xs leading-5 text-slate-500">{description}</span>}
      <span className="mt-1.5 block">
        {children ?? (
          as === 'textarea'
            ? <textarea className={`${controlClass} min-h-24 leading-6`} {...(props as TextareaHTMLAttributes<HTMLTextAreaElement>)} />
            : <input className={controlClass} {...(props as InputHTMLAttributes<HTMLInputElement>)} />
        )}
      </span>
    </label>
  )
}
