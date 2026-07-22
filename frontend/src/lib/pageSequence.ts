import type { CourseDetail, Lesson, Module, PageSummary } from '../types/courses'

export interface FlatPageEntry {
  page: PageSummary
  lesson: Lesson
  module: Module
}

// Module/Lesson/Page are all returned in `order` from the backend, so a
// straightforward nested walk reproduces the authored sequence: Page 1 ->
// Page 2 -> ... within a lesson, then into the next lesson, then module.
export function flattenCoursePages(course: CourseDetail): FlatPageEntry[] {
  const entries: FlatPageEntry[] = []
  for (const courseModule of course.modules) {
    for (const lesson of courseModule.lessons) {
      for (const page of lesson.pages) {
        entries.push({ page, lesson, module: courseModule })
      }
    }
  }
  return entries
}

// A page is unlocked once every page before it in the authored sequence is
// complete — this is what stops a student from jumping ahead via the sidebar
// to dodge a later page's dwell-time gate. frontierPageId is the furthest
// unlocked page, i.e. where a returning student should resume.
export function computeUnlockedPageIds(
  entries: FlatPageEntry[],
  completedPageIds: Set<number>,
): { unlocked: Set<number>; frontierPageId: number | null } {
  const unlocked = new Set<number>()
  let frontierPageId: number | null = null
  let reachable = true

  for (const entry of entries) {
    if (!reachable) break
    unlocked.add(entry.page.id)
    frontierPageId = entry.page.id
    if (!completedPageIds.has(entry.page.id)) {
      reachable = false
    }
  }

  return { unlocked, frontierPageId }
}

