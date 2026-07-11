import { useContext } from 'react'
import { ToastContext, type PetSpiritPreferences, type ToastOptions, type ToastVariant } from '../components/ui/ToastContext'

export interface UseToastReturn {
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

export function useToast(): UseToastReturn {
  const context = useContext(ToastContext)

  if (!context) {
    throw new Error('useToast must be used within a ToastProvider')
  }

  return context
}
