import { apiFetch } from './apiClient'
import type { SlideTemplate } from '../types/slides'

// The curated preset catalog is small and effectively static within a
// session (admin/migration-managed), so it's memoized here rather than
// re-fetched by every slide that renders one.
let cachedTemplates: Promise<SlideTemplate[]> | null = null

export function fetchSlideTemplates(): Promise<SlideTemplate[]> {
  if (!cachedTemplates) {
    cachedTemplates = apiFetch<SlideTemplate[]>('/slide-templates/').catch((err) => {
      cachedTemplates = null
      throw err
    })
  }
  return cachedTemplates
}
