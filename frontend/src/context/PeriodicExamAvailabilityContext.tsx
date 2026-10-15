import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { useAuth } from './AuthContext'
import { fetchPeriodicExamAvailability } from '../lib/periodicExamsApi'
import { fetchPlatformPeriodicExamOrganizations } from '../lib/periodicExamsApi'
import type { PeriodicExamAvailability } from '../types/periodicExams'
import { PeriodicExamAvailabilityContext } from './usePeriodicExamAvailability'

export function PeriodicExamAvailabilityProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const userId = user?.id
  const userRole = user?.role
  const [availability, setAvailability] = useState<PeriodicExamAvailability | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refreshAvailability = useCallback(async () => {
    if (!userId) {
      setAvailability({ enabled: false })
      setIsLoading(false)
      return
    }
    setIsLoading(true)
    try {
      if (userRole === 'PLATFORM_ADMIN') {
        const organizations = await fetchPlatformPeriodicExamOrganizations()
        setAvailability({ enabled: organizations.some((item) => item.periodic_exam_enabled) })
      } else {
        setAvailability(await fetchPeriodicExamAvailability())
      }
    } catch {
      // Availability is fail-closed: navigation and direct routes stay hidden
      // if this small feature-specific request cannot be completed.
      setAvailability({ enabled: false })
    } finally {
      setIsLoading(false)
    }
  }, [userId, userRole])

  useEffect(() => {
    void refreshAvailability()
  }, [refreshAvailability])

  return (
    <PeriodicExamAvailabilityContext.Provider value={{ availability, isLoading, refreshAvailability }}>
      {children}
    </PeriodicExamAvailabilityContext.Provider>
  )
}
