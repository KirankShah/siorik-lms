import { apiFetch } from './apiClient'

export interface UploadedMedia {
  url: string
  name: string
  size: number
  content_type: string
}

// Backs every custom BlockNote media block (image gallery, video, audio,
// file attachment) — all uploads go through this one endpoint, which saves
// via the same storage backend (STORAGES['default']) as every other
// FileField/ImageField in the app. See courses.views.MediaUploadView.
export function uploadMedia(file: File): Promise<UploadedMedia> {
  const formData = new FormData()
  formData.append('file', file)
  return apiFetch<UploadedMedia>('/media/upload/', { method: 'POST', body: formData })
}
