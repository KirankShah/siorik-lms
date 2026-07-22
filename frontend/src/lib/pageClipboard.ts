import type { PageType } from '../types/courses'

// Whole-page copy/paste (distinct from BlockNote's own block-level copy/paste
// within a page). Backed by sessionStorage rather than component state so a
// copied page survives navigating to a different lesson/course tab before
// pasting, but doesn't linger across browser sessions.
const STORAGE_KEY = 'lms-page-clipboard'

export interface ClipboardPage {
  title: string
  page_type: PageType
  content_json: unknown[]
  estimated_minutes: number
}

export function copyPageToClipboard(page: ClipboardPage): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(page))
}

export function readPageClipboard(): ClipboardPage | null {
  const raw = sessionStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as ClipboardPage
  } catch {
    return null
  }
}

export function hasPageClipboard(): boolean {
  return sessionStorage.getItem(STORAGE_KEY) !== null
}
