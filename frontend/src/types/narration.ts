import type { NarrationLanguage } from './auth'

export interface SlideNarration {
  id: number
  slide: number
  language: NarrationLanguage
  script_text: string
  audio_file: string | null
  voice_name: string
  generated_by: number | null
  generated_by_name: string | null
  generated_at: string
}
