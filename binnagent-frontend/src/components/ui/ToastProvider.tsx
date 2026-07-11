import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { PetSpirit } from './PetSpirit'
import { expressionForMotion, motionForVariant, type PetExpression, type PetMotionState } from './petMotionMachine'
import {
  ToastContext,
  type PetSpiritPreferences,
  type ToastOptions,
  type ToastVariant,
} from './ToastContext'
import { createClientId } from '@/utils/id'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { enqueuePetMessage } from './petMessageQueue'
import { companionizePetMessage } from './petCompanionCopy'
import { petMessageDuration } from './petMessageDuration'

export interface PetMessage {
  id: string
  message: string
  title?: string
  variant: ToastVariant
  duration: number
  expression: PetExpression
  motion: PetMotionState
  priority: number
}

const DEFAULT_PREFERENCES: PetSpiritPreferences = {
  alwaysVisible: true,
  autonomousMotion: true,
  idleMotionInterval: 6,
  introductionsEnabled: true,
  reducedMotion: false,
}
const PREFERENCES_KEY = 'binn-pet-spirit-preferences-v1'
const INTRODUCTIONS_KEY = 'binn-pet-spirit-introductions-v1'
const MAX_MESSAGES = 5

function readPreferences() {
  try {
    return { ...DEFAULT_PREFERENCES, ...JSON.parse(localStorage.getItem(PREFERENCES_KEY) ?? '{}') } as PetSpiritPreferences
  } catch {
    return DEFAULT_PREFERENCES
  }
}

function readIntroductions() {
  try {
    return new Set<string>(JSON.parse(localStorage.getItem(INTRODUCTIONS_KEY) ?? '[]'))
  } catch {
    return new Set<string>()
  }
}

function expressionForVariant(variant: ToastVariant): PetExpression {
  return expressionForMotion(motionForVariant(variant))
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<PetMessage[]>([])
  const [petPreferences, setPetPreferences] = useState<PetSpiritPreferences>(readPreferences)
  const [memoryPulse, setMemoryPulse] = useState(0)
  const systemReducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')
  const activeMessage = messages[0]

  const hideToast = useCallback((id: string) => {
    setMessages((current) => current.filter((message) => message.id !== id))
  }, [])

  const showToast = useCallback((message: string, options: ToastOptions = {}) => {
    const id = createClientId('pet-message')
    const variant = options.variant ?? 'info'
    const companionMessage = companionizePetMessage(message)
    const priority = options.priority ?? 0
    const nextMessage: PetMessage = {
      id,
      message: companionMessage,
      title: options.title,
      variant,
      duration: options.duration ?? petMessageDuration({
        message: companionMessage,
        title: options.title,
        variant,
        priority,
      }),
      expression: expressionForVariant(variant),
      motion: options.motion ?? motionForVariant(variant),
      priority,
    }
    setMessages((current) => enqueuePetMessage(current, nextMessage, MAX_MESSAGES))
    return id
  }, [])

  const beginPetActivity = useCallback((message: string, title = '我们一起处理') => (
    showToast(message, { title, variant: 'info', duration: 60_000, motion: 'working', priority: 5 })
  ), [showToast])

  const completePetActivity = useCallback((activityId: string, message?: string, variant: ToastVariant = 'success') => {
    hideToast(activityId)
    if (message) showToast(message, { variant })
  }, [hideToast, showToast])

  const signalMemoryChange = useCallback((message: string | null = '我把这次线索记下来了，下次我们可以从这里接着走。') => {
    setMemoryPulse((current) => current + 1)
    if (message) showToast(message, { title: '我们的学习记忆', variant: 'info', motion: 'working', priority: 4 })
  }, [showToast])

  const introduceFeature = useCallback((featureKey: string, title: string, message: string) => {
    if (!petPreferences.introductionsEnabled) return
    const seen = readIntroductions()
    if (seen.has(featureKey)) return
    seen.add(featureKey)
    try {
      localStorage.setItem(INTRODUCTIONS_KEY, JSON.stringify([...seen]))
    } catch {
      // Keep introductions usable when browser storage is unavailable.
    }
    showToast(message, { title, variant: 'info', priority: 2 })
  }, [petPreferences.introductionsEnabled, showToast])

  const updatePetPreferences = useCallback((patch: Partial<PetSpiritPreferences>) => {
    setPetPreferences((current) => {
      const next = { ...current, ...patch }
      try {
        localStorage.setItem(PREFERENCES_KEY, JSON.stringify(next))
      } catch {
        // Keep the current session usable when browser storage is unavailable.
      }
      return next
    })
  }, [])

  const resetIntroductions = useCallback(() => {
    try {
      localStorage.removeItem(INTRODUCTIONS_KEY)
    } catch {
      // No-op: resetting is best effort in private browsing modes.
    }
    showToast('好的，下次进入功能页时我会重新介绍。', { variant: 'success' })
  }, [showToast])

  useEffect(() => {
    if (!activeMessage) return undefined
    const timer = window.setTimeout(() => hideToast(activeMessage.id), activeMessage.duration)
    return () => window.clearTimeout(timer)
  }, [activeMessage, hideToast])

  const value = useMemo(() => ({
    showToast,
    hideToast,
    introduceFeature,
    beginPetActivity,
    completePetActivity,
    signalMemoryChange,
    petPreferences,
    resetIntroductions,
    updatePetPreferences,
  }), [beginPetActivity, completePetActivity, hideToast, introduceFeature, petPreferences, resetIntroductions, showToast, signalMemoryChange, updatePetPreferences])

  return (
    <ToastContext.Provider value={value}>
      {children}
      {createPortal(
        <PetSpirit
          message={activeMessage}
          queuedCount={Math.max(0, messages.length - 1)}
          alwaysVisible={petPreferences.alwaysVisible}
          autonomousMotion={petPreferences.autonomousMotion}
          idleMotionInterval={petPreferences.idleMotionInterval}
          reducedMotion={petPreferences.reducedMotion || systemReducedMotion}
          memoryPulse={memoryPulse}
          onDismiss={hideToast}
        />,
        document.body,
      )}
    </ToastContext.Provider>
  )
}
