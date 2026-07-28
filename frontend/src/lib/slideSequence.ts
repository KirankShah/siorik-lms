import type { CourseDetail, Lesson, Module } from '../types/courses'
import type { SlideSummary } from '../types/slides'

export interface FlatSlideEntry {
  slide: SlideSummary
  lesson: Lesson
  module: Module
}

// Module.order -> Lesson.order -> Slide.order, fully flattened into one
// continuous sequence spanning the whole course — this is the order "Next"
// walks through, matching the instructor's authored order.
export function flattenCourseSlides(course: CourseDetail): FlatSlideEntry[] {
  const entries: FlatSlideEntry[] = []
  for (const courseModule of [...course.modules].sort((a, b) => a.order - b.order)) {
    for (const lesson of [...courseModule.lessons].sort((a, b) => a.order - b.order)) {
      for (const slide of [...lesson.slides].sort((a, b) => a.order - b.order)) {
        entries.push({ slide, lesson, module: courseModule })
      }
    }
  }
  return entries
}

// Every completed slide, plus the first not-yet-completed one (the current
// "frontier") — used to let a learner freely revisit anything they've
// already reached, without being able to skip ahead past it.
export function computeReachedSlideIds(entries: FlatSlideEntry[], completedSlideIds: Set<number>): Set<number> {
  const reached = new Set<number>()
  for (const entry of entries) {
    reached.add(entry.slide.id)
    if (!completedSlideIds.has(entry.slide.id)) break
  }
  return reached
}
