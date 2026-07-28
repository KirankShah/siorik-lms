import { apiFetch } from './apiClient'
import type { ElementAlign, ElementType, Slide, SlideElement, SlideSummary, SlideType } from '../types/slides'

export interface SlideInput {
  lesson: number
  title?: string
  order: number
  slide_type: SlideType
  estimated_minutes?: number
}

export function createSlide(input: SlideInput): Promise<Slide> {
  return apiFetch<Slide>('/slides/', { method: 'POST', body: input })
}

export function updateSlide(id: number, input: Partial<SlideInput>): Promise<Slide> {
  return apiFetch<Slide>(`/slides/${id}/`, { method: 'PATCH', body: input })
}

export function deleteSlide(id: number): Promise<void> {
  return apiFetch<void>(`/slides/${id}/`, { method: 'DELETE' })
}

export function reorderSlides(lessonId: number, slideIds: number[]): Promise<SlideSummary[]> {
  return apiFetch<SlideSummary[]>('/slides/reorder/', {
    method: 'POST',
    body: { lesson: lessonId, slide_ids: slideIds },
  })
}

export function duplicateSlide(id: number): Promise<Slide> {
  return apiFetch<Slide>(`/slides/${id}/duplicate/`, { method: 'POST' })
}

export function fetchElements(slideId: number): Promise<SlideElement[]> {
  return apiFetch<SlideElement[]>(`/elements/?slide=${slideId}`)
}

export interface ElementInput {
  slide: number
  order: number
  element_type: ElementType
  rich_text?: string
  video_url?: string
  embed_url?: string
  caption?: string
  align?: ElementAlign
  file?: File | null
  video_file?: File | null
}

function buildElementFormData(input: Partial<ElementInput>): FormData {
  const formData = new FormData()
  for (const [key, value] of Object.entries(input)) {
    if (value === undefined || value === null) continue
    formData.append(key, value instanceof File ? value : String(value))
  }
  return formData
}

function hasFile(input: Partial<ElementInput>): boolean {
  return input.file instanceof File || input.video_file instanceof File
}

export function createElement(input: ElementInput): Promise<SlideElement> {
  const body = hasFile(input) ? buildElementFormData(input) : input
  return apiFetch<SlideElement>('/elements/', { method: 'POST', body })
}

export function updateElement(id: number, input: Partial<ElementInput>): Promise<SlideElement> {
  const body = hasFile(input) ? buildElementFormData(input) : input
  return apiFetch<SlideElement>(`/elements/${id}/`, { method: 'PATCH', body })
}

export function deleteElement(id: number): Promise<void> {
  return apiFetch<void>(`/elements/${id}/`, { method: 'DELETE' })
}

export function reorderElements(slideId: number, elementIds: number[]): Promise<SlideElement[]> {
  return apiFetch<SlideElement[]>('/elements/reorder/', {
    method: 'POST',
    body: { slide: slideId, element_ids: elementIds },
  })
}
