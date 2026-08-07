import type { Organization } from './auth'
import type { SlideProgress, SlideSummary } from './slides'

export type LessonType = 'VIDEO' | 'SLIDES' | 'DOCUMENT' | 'TEXT'

export interface Lesson {
  id: number
  title: string
  lesson_type: LessonType
  content_file: string | null
  content_url: string
  order: number
  estimated_minutes: number
  // True only for a demo user (accounts.User.is_demo) opening a lesson their
  // course's DemoLessonAccess grants don't cover — always false otherwise.
  // slides is [] whenever this is true; see backend LessonSerializer.
  is_locked: boolean
  slides: SlideSummary[]
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
  // Null means the pre-templates default look — see backend Course.template.
  template: number | null
  completion_deadline_days: number | null
  created_at: string
  updated_at: string
  // True only for a demo user (accounts.User.is_demo) viewing a course
  // outside their Organization's normal assignment — see backend
  // courses.permissions.catalog_courses_for_user. Always false otherwise.
  // A locked course is a teaser card only: its detail/content stays 404
  // server-side even if the id/slug is known.
  is_locked: boolean
}

export interface CourseAccessGrant {
  id: number
  organization: Organization
  granted_at: string
}

export interface CourseDetail extends CourseListItem {
  created_by: number | null
  certificate_pass_threshold: number
  certificate_expiry_months: number | null
  is_demo_available: boolean
  modules: Module[]
  access_grants: CourseAccessGrant[]
}

export interface DemoLessonAccessGrant {
  id: number
  course: number
  lesson: number
  created_at: string
}

export type EnrollmentStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED'

export interface Enrollment {
  id: number
  user: number
  course: number
  enrolled_at: string
  completed_at: string | null
  status: EnrollmentStatus
  progress_percent: number
  completed_lesson_ids: number[]
  slide_progress: SlideProgress[]
  // Null once status isn't COMPLETED yet, or once the learner is eligible
  // for a certificate. Otherwise why they aren't (yet) — currently always
  // the course-wide quiz average falling short of the course's pass
  // threshold. See backend certificates.services.certificate_ineligibility_reason.
  certificate_ineligible_reason: string | null
}
