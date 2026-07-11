import { createContext } from 'react'
import type { PetMotionState } from './petMotionMachine'

export type ToastVariant = 'info' | 'success' | 'warning' | 'error'

export interface ToastOptions {
  title?: string
  variant?: ToastVariant
  duration?: number
  motion?: PetMotionState
  priority?: number
}

export interface PetSpiritPreferences {
  alwaysVisible: boolean
  autonomousMotion: boolean
  idleMotionInterval: number
  introductionsEnabled: boolean
  reducedMotion: boolean
}

export interface ToastContextType {
  showToast: (message: string, options?: ToastOptions) => string
  hideToast: (id: string) => void
  introduceFeature: (featureKey: string, title: string, message: string) => void
  beginPetActivity: (message: string, title?: string) => string
  completePetActivity: (activityId: string, message?: string, variant?: ToastVariant) => void
  signalMemoryChange: (message?: string | null) => void
  petPreferences: PetSpiritPreferences
  resetIntroductions: () => void
  updatePetPreferences: (patch: Partial<PetSpiritPreferences>) => void
}

export const ToastContext = createContext<ToastContextType | undefined>(undefined)
