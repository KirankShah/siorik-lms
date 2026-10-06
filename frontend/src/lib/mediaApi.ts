import { apiFetch } from './apiClient'

export interface UploadedMedia {
  url: string
  name: string
  size: number
  content_type: string
}

interface VideoUploadSession {
  upload_id: string
  chunk_size: number
  chunk_count: number
}

interface CompletedVideoUpload {
  video_upload_token: string
  name: string
  size: number
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

// Large videos are split into small requests so a slow connection or hosting
// request timeout cannot discard the whole file near the end. Two chunks are
// uploaded concurrently for useful throughput without exhausting the shared
// application's worker pool.
export async function uploadVideoFile(file: File, onProgress?: (percent: number) => void): Promise<string> {
  const session = await apiFetch<VideoUploadSession>('/media/video-upload/start/', {
    method: 'POST',
    body: { filename: file.name, size: file.size, content_type: file.type },
  })

  let nextIndex = 0
  let uploadedBytes = 0
  onProgress?.(0)

  async function worker() {
    while (true) {
      const index = nextIndex++
      if (index >= session.chunk_count) return
      const start = index * session.chunk_size
      const chunk = file.slice(start, Math.min(start + session.chunk_size, file.size))
      const formData = new FormData()
      formData.append('upload_id', session.upload_id)
      formData.append('index', String(index))
      formData.append('file', chunk, `${file.name}.part${index}`)
      await apiFetch('/media/video-upload/chunk/', { method: 'POST', body: formData })
      uploadedBytes += chunk.size
      onProgress?.(Math.min(99, Math.round((uploadedBytes / file.size) * 100)))
    }
  }

  await Promise.all(Array.from({ length: Math.min(2, session.chunk_count) }, () => worker()))
  const completed = await apiFetch<CompletedVideoUpload>('/media/video-upload/complete/', {
    method: 'POST',
    body: { upload_id: session.upload_id },
  })
  onProgress?.(100)
  return completed.video_upload_token
}
