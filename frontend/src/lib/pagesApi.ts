import { apiFetch } from './apiClient'
import type { PageDetail, PageType } from '../types/courses'

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
