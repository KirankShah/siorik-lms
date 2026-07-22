import type { Organization } from './auth'

export type LessonType = 'VIDEO' | 'SLIDES' | 'DOCUMENT' | 'TEXT'

export type PageType = 'CONTENT' | 'QUIZ' | 'ASSIGNMENT'

// Nested under a Lesson without content_json — see PageDetail for the full page.
export interface PageSummary {
  id: number
  title: string
  order: number
  page_type: PageType
  estimated_minutes: number
}

export interface PageDetail {
  id: number
  lesson: number
  title: string
  order: number
  page_type: PageType
  // BlockNote document — an array of blocks, kept as unknown[] here so this
  // module doesn't need to depend on @blocknote/core's types.
  content_json: unknown[]
  estimated_minutes: number
  created_at: string
  updated_at: string
}

export interface Lesson {
  id: number
  title: string
  lesson_type: LessonType
  content_file: string | null
  content_url: string
  order: number
  estimated_minutes: number
  pages: PageSummary[]
}

export interface Module {
  id: number
  title: string
  order: number
  lessons: Lesson[]
}

export type ContentOwner = 'PLATFORM' | 'ORGANIZATION'

export interface CourseListItem {
  id: number
  title: string
  slug: string
  description: string
  organization: number | null
  content_owner: ContentOwner
  cover_image: string | null
  is_published: boolean
  created_at: string
}

export interface CourseAccessGrant {
  id: number
  organization: Organization
  granted_at: string
}

export interface CourseDetail extends CourseListItem {
  created_by: number | null
  updated_at: string
  modules: Module[]
  access_grants: CourseAccessGrant[]
}

export type EnrollmentStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED'

export interface PageProgress {
  id: number
  page: number
  started_at: string | null
  completed_at: string | null
  time_spent_seconds: number
}

export interface Enrollment {
  id: number
  user: number
  course: number
  enrolled_at: string
  completed_at: string | null
  status: EnrollmentStatus
  progress_percent: number
  completed_lesson_ids: number[]
  page_progress: PageProgress[]
}
