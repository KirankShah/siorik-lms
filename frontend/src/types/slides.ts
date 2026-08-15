import type { Character, Scene } from './dialogue'

export type SlideType = 'CONTENT' | 'QUIZ' | 'ASSIGNMENT' | 'SCENARIO'

export type Layout = 'STACKED' | 'IMAGE_LEFT' | 'IMAGE_RIGHT'

// IMAGE_LEFT/IMAGE_RIGHT only — caps how wide the docked image column can
// grow (35% / 45% / 55% of canvas width; see SlideElementsView's
// canvasMode). The image still auto-sizes to its own aspect ratio up to
// that cap.
export type ImageColumnWidth = 'COMPACT' | 'STANDARD' | 'WIDE'

export type ElementType =
  | 'TEXT'
  | 'IMAGE'
  | 'VIDEO_AUDIO'
  | 'BREAKOUT_IMAGE'
  | 'QUOTE'
  | 'FILE_DOWNLOAD'
  | 'EMBED'
  | 'PRESENTATION_PDF'
  | 'DIALOGUE'

export type ElementAlign = 'LEFT' | 'CENTER' | 'RIGHT'

export type DialogueSpeaker = 'LEFT' | 'RIGHT'

export interface DialogueLine {
  speaker: DialogueSpeaker
  text: string
}

// A curated background/text/accent theme for CONTENT slides — see
// backend SlideTemplate. Seeded via migration, not user-creatable.
export interface SlideTemplate {
  id: number
  name: string
  background_css: string
  text_color: string
  accent_color: string
  order: number
}

// Nested under a Lesson (see courses.ts) without its elements — matches
// backend SlideSummarySerializer.
export interface SlideSummary {
  id: number
  title: string
  order: number
  slide_type: SlideType
  layout: Layout
  image_column_width: ImageColumnWidth
  // Null (the common case) means this slide follows the course's current
  // template — see Course.template in courses.ts.
  template_override: number | null
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
  dialogue_scene: number | null
  dialogue_character_left: number | null
  dialogue_character_right: number | null
  dialogue_lines: DialogueLine[]
  // Nested read-only detail for the ids above — only present on DIALOGUE
  // elements, see backend ElementSerializer.to_representation.
  dialogue_scene_detail?: Scene | null
  dialogue_character_left_detail?: Character | null
  dialogue_character_right_detail?: Character | null
}

export interface SlideProgress {
  id: number
  slide: number
  started_at: string | null
  completed_at: string | null
  time_spent_seconds: number
}
