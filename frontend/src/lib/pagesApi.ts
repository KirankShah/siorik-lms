import { apiFetch } from './apiClient'
import type { PageDetail, PageSummary, PageType } from '../types/courses'

export function fetchPage(id: number): Promise<PageDetail> {
  return apiFetch<PageDetail>(`/pages/${id}/`)
}

export interface PageInput {
  lesson: number
  title: string
  order: number
  page_type: PageType
  content_json?: unknown[]
  estimated_minutes?: number
}

export function createPage(input: PageInput): Promise<PageDetail> {
  return apiFetch<PageDetail>('/pages/', { method: 'POST', body: input })
}

// Generic partial update — used for renames and any other metadata edit.
// Content autosave uses savePageContent below instead, to keep that PATCH
// scoped to content_json only.
export function updatePage(id: number, input: Partial<PageInput>): Promise<PageDetail> {
  return apiFetch<PageDetail>(`/pages/${id}/`, { method: 'PATCH', body: input })
}

export function deletePage(id: number): Promise<void> {
  return apiFetch<void>(`/pages/${id}/`, { method: 'DELETE' })
}

// Used by the PageEditor's autosave — a focused PATCH that only ever touches
// content_json, so concurrent edits to title/order elsewhere aren't clobbered.
export function savePageContent(id: number, contentJson: unknown[]): Promise<PageDetail> {
  return apiFetch<PageDetail>(`/pages/${id}/`, {
    method: 'PATCH',
    body: { content_json: contentJson },
  })
}

// Persists a full drag-and-drop reorder of one lesson's pages in a single
// atomic call — see courses.views.PageViewSet.reorder for why this isn't
// just N individual PATCHes (the (lesson, order) unique constraint would
// collide mid-sequence for most permutations).
export function reorderPages(lessonId: number, pageIds: number[]): Promise<PageSummary[]> {
  return apiFetch<PageSummary[]>('/pages/reorder/', {
    method: 'POST',
    body: { lesson: lessonId, page_ids: pageIds },
  })
}
