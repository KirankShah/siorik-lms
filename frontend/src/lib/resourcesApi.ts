import { apiFetch, apiFetchBlob } from './apiClient'
import type { Resource, ResourceUploadInput } from '../types/resources'

export function fetchResources(): Promise<Resource[]> {
  return apiFetch<Resource[]>('/resources/')
}

export function fetchResource(id: number): Promise<Resource> {
  return apiFetch<Resource>(`/resources/${id}/`)
}

export function uploadResource(input: ResourceUploadInput): Promise<Resource> {
  const formData = new FormData()
  formData.append('title', input.title)
  formData.append('description', input.description)
  formData.append('file', input.file)
  return apiFetch<Resource>('/resources/', { method: 'POST', body: formData })
}

export function deleteResource(id: number): Promise<void> {
  return apiFetch<void>(`/resources/${id}/`, { method: 'DELETE' })
}

// The only way to reach a resource's PDF bytes — there is no public/direct
// file URL (see types/resources.ts). Authenticated fetch, org-scoped
// server-side on every call.
export function fetchResourcePdfBlob(id: number): Promise<Blob> {
  return apiFetchBlob(`/resources/${id}/stream/`)
}
