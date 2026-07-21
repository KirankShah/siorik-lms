import type { QuizSummary } from './quiz'

export type LessonType = 'VIDEO' | 'SLIDES' | 'DOCUMENT' | 'TEXT'

export interface Lesson {
  id: number
  title: string
  lesson_type: LessonType
  content_file: string | null
  content_url: string
  order: number
  estimated_minutes: number
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

export interface CourseDetail extends CourseListItem {
  created_by: number | null
  updated_at: string
  modules: Module[]
  quizzes: QuizSummary[]
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
}
