import { createContext, useContext } from 'react'
import type { PeriodicExamAvailability } from '../types/periodicExams'

export interface PeriodicExamAvailabilityContextValue {
  availability: PeriodicExamAvailability | null
  isLoading: boolean
  refreshAvailability: () => Promise<void>
}

export const PeriodicExamAvailabilityContext = createContext<PeriodicExamAvailabilityContextValue | null>(null)

export function usePeriodicExamAvailability(): PeriodicExamAvailabilityContextValue {
  const context = useContext(PeriodicExamAvailabilityContext)
  if (!context) throw new Error('usePeriodicExamAvailability must be used within PeriodicExamAvailabilityProvider')
  return context
}
