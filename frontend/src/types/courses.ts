import type { Organization } from './auth'
import type { LearningPathCourseState } from './learningPath'
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

// Mirrors backend accounts.User.AssessmentLevel's codes.
export type AssessmentLevelCode = 'assistant_supervisor' | 'officer' | 'management' | 'senior_management'

export interface CourseListItem {
  id: number
  title: string
  slug: string
  description: string
  organization: number | null
  // Populated whenever `organization` is set, regardless of content_owner —
  // lets the admin course list show which org a course belongs to without a
  // follow-up request.
  organization_name: string | null
  content_owner: ContentOwner
  cover_image: string | null
  is_published: boolean
  // Null means the pre-templates default look — see backend Course.template.
  template: number | null
  completion_deadline_days: number | null
  // This course's position in the learner-facing "My Learning Path" (see
  // LearningPathSection.tsx) — null means it isn't part of the path.
  path_order: number | null
  // Null means this course sits in the path's Foundation tier (open to
  // everyone); otherwise the single AssessmentLevel tier a learner needs
  // (accounts.User.assessment_level) to have it appear in their path.
  minimum_assessment_level: AssessmentLevelCode | null
  // Set only when this course was produced by cloning another course (a
  // platform course forked for an org, or an org course pulled up into the
  // platform library) — see courses.services.clone_course.
  cloned_from_title: string | null
  created_at: string
  updated_at: string
  // True only for a demo user (accounts.User.is_demo) viewing a course
  // outside their Organization's normal assignment — see backend
  // courses.permissions.catalog_courses_for_user. Always false otherwise.
  // A locked course is a teaser card only: its detail/content stays 404
  // server-side even if the id/slug is known.
  is_locked: boolean
  // Non-null only when this listing is the caller's own Learning Path
  // catalog (a non-demo learner with an assigned path) — the exact same
  // state the Learning Path dashboard widget computes for this course, so
  // the catalog can render identical completed/current/locked treatment.
  // Null for every other listing (admin/instructor, demo, or a learner with
  // no path assigned yet, which falls back to the full catalog).
  path_state: LearningPathCourseState | null
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
  // Set only when this course was produced by cloning another course (a
  // platform course forked for an org, or an org course pulled up into the
  // platform library) — see courses.services.clone_course.
  cloned_from_title: string | null
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
