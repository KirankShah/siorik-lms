import { apiFetch } from './apiClient'
import type { NarrationLanguage } from '../types/auth'
import type { SlideNarration } from '../types/narration'

// A slide can have zero, one, or both languages generated independently.
export function fetchNarrationsForSlide(slideId: number): Promise<SlideNarration[]> {
  return apiFetch<SlideNarration[]>(`/slide-narrations/?slide=${slideId}`)
}

// PLATFORM_ADMIN-only server-side (see narration.views.SlideNarrationViewSet.
// get_permissions) — creates the narration on first call, overwrites
// script_text/audio_file/voice_name on a later call for the same language.
export function generateSlideNarration(slideId: number, language: NarrationLanguage): Promise<SlideNarration> {
  return apiFetch<SlideNarration>('/slide-narrations/generate/', {
    method: 'POST',
    body: { slide: slideId, language },
  })
}
