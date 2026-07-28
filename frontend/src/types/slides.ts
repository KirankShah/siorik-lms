export type SlideType = 'CONTENT' | 'QUIZ' | 'ASSIGNMENT' | 'SCENARIO'

export type ElementType =
  | 'TEXT'
  | 'IMAGE'
  | 'VIDEO_AUDIO'
  | 'BREAKOUT_IMAGE'
  | 'QUOTE'
  | 'FILE_DOWNLOAD'
  | 'EMBED'
  | 'PRESENTATION_PDF'

export type ElementAlign = 'LEFT' | 'CENTER' | 'RIGHT'

// Nested under a Lesson (see courses.ts) without its elements — matches
// backend SlideSummarySerializer.
export interface SlideSummary {
  id: number
  title: string
  order: number
  slide_type: SlideType
  estimated_minutes: number
}

export interface Slide extends SlideSummary {
  lesson: number
  created_at: string
  updated_at: string
}

// Named SlideElement (not Element) to avoid colliding with the DOM's global
// Element type in files that need both.
export interface SlideElement {
  id: number
  slide: number
  order: number
  element_type: ElementType
  rich_text: string
  file: string | null
  video_url: string
  video_file: string | null
  embed_url: string
  caption: string
  align: ElementAlign
}

export interface SlideProgress {
  id: number
  slide: number
  started_at: string | null
  completed_at: string | null
  time_spent_seconds: number
}
