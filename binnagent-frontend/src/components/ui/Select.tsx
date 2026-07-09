import {
  Children,
  isValidElement,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type FocusEvent,
  type KeyboardEvent,
  type ReactNode,
  type SelectHTMLAttributes,
} from 'react'
import { Check, ChevronDown } from 'lucide-react'

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  children: ReactNode
  wrapperClassName?: string
  iconClassName?: string
}

interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

const SELECT_TRIGGER_CLASS =
  'min-h-10 w-full cursor-pointer rounded-xl border border-slate-200 bg-gradient-to-b from-white to-slate-50 py-2 pl-3.5 pr-11 text-left text-sm font-semibold text-slate-800 shadow-[0_1px_2px_rgba(15,23,42,0.06),inset_0_1px_0_rgba(255,255,255,0.88)] outline-none transition-[border-color,box-shadow,background-color] hover:border-slate-300 hover:from-white hover:to-white focus-visible:border-primary focus-visible:ring-4 focus-visible:ring-primary/15 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:from-slate-100 disabled:to-slate-100 disabled:text-slate-400 disabled:shadow-none'

function nodeText(node: ReactNode): string {
  if (node === null || node === undefined || typeof node === 'boolean') return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(nodeText).join('')
  if (isValidElement<{ children?: ReactNode }>(node)) return nodeText(node.props.children)
  return ''
}

function optionsFromChildren(children: ReactNode): SelectOption[] {
  return Children.toArray(children).flatMap((child) => {
    if (!isValidElement<{ children?: ReactNode; disabled?: boolean; value?: number | string }>(child)) return []
    const label = nodeText(child.props.children).trim()
    const value = child.props.value ?? label
    return [{
      disabled: child.props.disabled,
      label,
      value: String(value),
    }]
  })
}

function nextEnabledIndex(options: SelectOption[], startIndex: number, direction: 1 | -1) {
  if (options.length === 0) return -1
  for (let step = 0; step < options.length; step += 1) {
    const index = (startIndex + step * direction + options.length) % options.length
    if (!options[index]?.disabled) return index
  }
  return -1
}

export function Select({
  children,
  className = '',
  defaultValue,
  disabled = false,
  iconClassName = '',
  id,
  name,
  onBlur,
  onChange,
  onFocus,
  onKeyDown,
  value,
  wrapperClassName = '',
  ...props
}: SelectProps) {
  const generatedId = useId()
  const triggerId = id ?? generatedId
  const listboxId = `${triggerId}-listbox`
  const options = useMemo(() => optionsFromChildren(children), [children])
  const initialValue = String(defaultValue ?? options.find((option) => !option.disabled)?.value ?? '')
  const [internalValue, setInternalValue] = useState(initialValue)
  const [isOpen, setIsOpen] = useState(false)
  const controlledValue = value === undefined ? undefined : String(value)
  const selectedValue = controlledValue ?? internalValue
  const selectedIndex = options.findIndex((option) => option.value === selectedValue)
  const selectedOption = options[selectedIndex] ?? options.find((option) => !option.disabled)
  const [activeIndex, setActiveIndex] = useState(() => Math.max(selectedIndex, 0))
  const wrapperRef = useRef<HTMLSpanElement>(null)
  const ariaLabel = props['aria-label']
  const ariaLabelledby = props['aria-labelledby']

  useEffect(() => {
    if (!isOpen) return

    const handlePointerDown = (event: PointerEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) setIsOpen(false)
    }

    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [isOpen])

  const emitChange = (nextValue: string) => {
    if (controlledValue === undefined) setInternalValue(nextValue)
    onChange?.({
      currentTarget: { name, value: nextValue },
      target: { name, value: nextValue },
    } as ChangeEvent<HTMLSelectElement>)
  }

  const chooseOption = (option: SelectOption) => {
    if (option.disabled) return
    emitChange(option.value)
    setIsOpen(false)
  }

  const selectedEnabledIndex = () => (
    selectedIndex >= 0 && !options[selectedIndex]?.disabled
      ? selectedIndex
      : nextEnabledIndex(options, 0, 1)
  )

  const openListbox = () => {
    setActiveIndex(selectedEnabledIndex())
    setIsOpen(true)
  }

  const toggleListbox = () => {
    if (isOpen) {
      setIsOpen(false)
      return
    }
    openListbox()
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    onKeyDown?.(event as unknown as KeyboardEvent<HTMLSelectElement>)
    if (event.defaultPrevented) return
    if (disabled) return
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const direction = event.key === 'ArrowDown' ? 1 : -1
      if (!isOpen) {
        openListbox()
        return
      }
      setActiveIndex((current) => nextEnabledIndex(options, current + direction, direction))
      return
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      if (!isOpen) {
        openListbox()
        return
      }
      const activeOption = options[activeIndex]
      if (activeOption) chooseOption(activeOption)
      return
    }
    if (event.key === 'Escape') {
      setIsOpen(false)
    }
  }

  return (
    <span ref={wrapperRef} className={`group relative block ${wrapperClassName}`}>
      {name ? <input type="hidden" name={name} value={selectedOption?.value ?? ''} /> : null}
      <button
        id={triggerId}
        type="button"
        aria-controls={listboxId}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-label={ariaLabel}
        aria-labelledby={ariaLabelledby}
        className={`${SELECT_TRIGGER_CLASS} ${className}`}
        disabled={disabled}
        onBlur={(event) => onBlur?.(event as unknown as FocusEvent<HTMLSelectElement>)}
        onClick={toggleListbox}
        onFocus={(event) => onFocus?.(event as unknown as FocusEvent<HTMLSelectElement>)}
        onKeyDown={handleKeyDown}
      >
        <span className="block truncate">{selectedOption?.label ?? ''}</span>
      </button>
      <span className="pointer-events-none absolute right-2 top-1/2 flex size-6 -translate-y-1/2 items-center justify-center rounded-lg border border-slate-200/80 bg-white/85 text-slate-500 shadow-[0_1px_1px_rgba(15,23,42,0.04)] transition-colors group-hover:border-slate-300 group-hover:bg-slate-50 group-focus-within:border-primary/25 group-focus-within:bg-primary/10 group-focus-within:text-primary group-has-disabled:border-slate-200 group-has-disabled:bg-slate-100 group-has-disabled:text-slate-400">
        <ChevronDown
          aria-hidden="true"
          className={`size-3.5 transition-transform ${isOpen ? 'rotate-180' : ''} ${iconClassName}`}
        />
      </span>
      {isOpen ? (
        <div
          id={listboxId}
          role="listbox"
          aria-labelledby={triggerId}
          className="select-popover-enter absolute left-0 right-0 top-full z-50 mt-1.5 max-h-64 overflow-y-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_18px_42px_rgba(15,23,42,0.16),0_4px_12px_rgba(15,23,42,0.08)] ring-1 ring-slate-950/5"
        >
          {options.map((option, index) => {
            const isSelected = option.value === selectedOption?.value
            const isActive = index === activeIndex
            return (
              <button
                key={`${option.value}-${option.label}`}
                type="button"
                role="option"
                aria-disabled={option.disabled || undefined}
                aria-selected={isSelected}
                className={`flex min-h-9 w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition-colors ${
                  option.disabled
                    ? 'cursor-not-allowed text-slate-300'
                    : isSelected
                      ? 'bg-primary/10 font-bold text-primary'
                      : isActive
                        ? 'bg-slate-100 font-semibold text-slate-950'
                        : 'font-medium text-slate-700 hover:bg-slate-50 hover:text-slate-950'
                }`}
                disabled={option.disabled}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => chooseOption(option)}
              >
                <span className="min-w-0 truncate">{option.label}</span>
                {isSelected ? <Check className="size-4 shrink-0" /> : <span className="size-4 shrink-0" />}
              </button>
            )
          })}
        </div>
      ) : null}
    </span>
  )
}
