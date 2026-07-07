import { useCallback, useEffect, useRef, type KeyboardEvent } from 'react'

interface UseFocusTrapOptions {
  isActive: boolean
  onEscape?: () => void
  restoreFocus?: boolean
  isEscapeEnabled?: boolean
}

export function useFocusTrap<T extends HTMLElement>({
  isActive,
  onEscape,
  restoreFocus = true,
  isEscapeEnabled = true,
}: UseFocusTrapOptions) {
  const containerRef = useRef<T | null>(null)

  useEffect(() => {
    if (!isActive) return
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const timer = window.setTimeout(() => {
      const focusTarget = getFocusableElements(containerRef.current)[0] ?? containerRef.current
      focusTarget?.focus()
    }, 0)

    return () => {
      window.clearTimeout(timer)
      if (restoreFocus) previousFocus?.focus()
    }
  }, [isActive, restoreFocus])

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<T>) => {
      if (!isActive) return
      if (event.key === 'Escape') {
        event.stopPropagation()
        if (isEscapeEnabled) onEscape?.()
        return
      }
      if (event.key !== 'Tab') return

      const focusableElements = getFocusableElements(containerRef.current)
      if (focusableElements.length === 0) {
        event.preventDefault()
        containerRef.current?.focus()
        return
      }

      const firstElement = focusableElements[0]
      const lastElement = focusableElements[focusableElements.length - 1]
      if (event.shiftKey && document.activeElement === firstElement) {
        event.preventDefault()
        lastElement.focus()
      } else if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault()
        firstElement.focus()
      }
    },
    [isActive, isEscapeEnabled, onEscape]
  )

  return { containerRef, handleKeyDown }
}

function getFocusableElements(root: HTMLElement | null) {
  if (!root) return []
  return Array.from(
    root.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )
  ).filter((element) => !element.hasAttribute('disabled') && element.getAttribute('aria-hidden') !== 'true')
}
