import { FileDown, FileText, Image, Images, Link, Quote, Type, Video } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { ElementType } from '../types/slides'

export const ELEMENT_TYPE_LABEL: Record<ElementType, string> = {
  TEXT: 'Text',
  IMAGE: 'Image',
  VIDEO_AUDIO: 'Video or audio',
  BREAKOUT_IMAGE: 'Breakout image',
  QUOTE: 'Quote',
  FILE_DOWNLOAD: 'File download',
  EMBED: 'Embed',
  PRESENTATION_PDF: 'Presentation or PDF',
}

export const ELEMENT_TYPE_ICON: Record<ElementType, LucideIcon> = {
  TEXT: Type,
  IMAGE: Image,
  VIDEO_AUDIO: Video,
  BREAKOUT_IMAGE: Images,
  QUOTE: Quote,
  FILE_DOWNLOAD: FileDown,
  EMBED: Link,
  PRESENTATION_PDF: FileText,
}

export const ELEMENT_TYPES: ElementType[] = [
  'TEXT',
  'IMAGE',
  'VIDEO_AUDIO',
  'BREAKOUT_IMAGE',
  'QUOTE',
  'FILE_DOWNLOAD',
  'EMBED',
  'PRESENTATION_PDF',
]
