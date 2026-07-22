import { apiFetch, apiFetchBlob } from './apiClient'
import type { BulkEnrollResult, ReportRow } from '../types/admin'
import type { CourseAccessGrant, CourseDetail, CourseListItem, Enrollment, LessonType } from '../types/courses'

export function fetchCourses(): Promise<CourseListItem[]> {
  return apiFetch<CourseListItem[]>('/courses/')
}

export function fetchCourseDetail(slug: string): Promise<CourseDetail> {
  return apiFetch<CourseDetail>(`/courses/${slug}/`)
}

export function fetchEnrollments(courseId?: number): Promise<Enrollment[]> {
  const query = courseId ? `?course=${courseId}` : ''
  return apiFetch<Enrollment[]>(`/enrollments/${query}`)
}

export function enrollInCourse(courseId: number): Promise<Enrollment> {
  return apiFetch<Enrollment>('/enrollments/', { method: 'POST', body: { course: courseId } })
}

export function completeLesson(enrollmentId: number, lessonId: number): Promise<Enrollment> {
  return apiFetch<Enrollment>(`/enrollments/${enrollmentId}/complete-lesson/`, {
    method: 'POST',
    body: { lesson: lessonId },
  })
}

// time_spent_seconds is a delta added to the page's running total, not an
// absolute value — see courses.views.EnrollmentViewSet.page_progress.
export function savePageProgress(
  enrollmentId: number,
  input: { page: number; time_spent_seconds?: number; completed?: boolean },
): Promise<Enrollment> {
  return apiFetch<Enrollment>(`/enrollments/${enrollmentId}/page-progress/`, {
    method: 'POST',
    body: input,
  })
}

function buildFormData<T extends object>(payload: T): FormData {
  const formData = new FormData()
  for (const [key, value] of Object.entries(payload as Record<string, unknown>)) {
    if (value === undefined || value === null) continue
    formData.append(key, value instanceof File ? value : String(value))
  }
  return formData
}

// --- Admin: course builder ---

export interface CourseInput {
  title: string
  slug: string
  description: string
  // Only meaningful for PLATFORM_ADMIN — the backend forces this to the
  // caller's own org for ORG_ADMIN/INSTRUCTOR regardless of what's sent.
  organization: number | null
  is_published: boolean
  cover_image?: File | null
}

export function createCourse(input: CourseInput): Promise<CourseDetail> {
  const body = input.cover_image instanceof File ? buildFormData(input) : input
  return apiFetch<CourseDetail>('/courses/', { method: 'POST', body })
}

export function updateCourse(slug: string, input: Partial<CourseInput>): Promise<CourseDetail> {
  const body = input.cover_image instanceof File ? buildFormData(input) : input
  return apiFetch<CourseDetail>(`/courses/${slug}/`, { method: 'PATCH', body })
}

// --- Admin: PLATFORM_ADMIN course access grants ---

export function grantCourseAccess(courseSlug: string, organizationId: number): Promise<CourseAccessGrant> {
  return apiFetch<CourseAccessGrant>(`/courses/${courseSlug}/access-grants/`, {
    method: 'POST',
    body: { organization: organizationId },
  })
}

export function revokeCourseAccess(courseSlug: string, organizationId: number): Promise<void> {
  return apiFetch<void>(`/courses/${courseSlug}/access-grants/revoke/`, {
    method: 'DELETE',
    body: { organization: organizationId },
  })
}

export interface ModuleInput {
  course: number
  title: string
  order: number
}

export function createModule(input: ModuleInput): Promise<{ id: number }> {
  return apiFetch('/modules/', { method: 'POST', body: input })
}

export function updateModule(id: number, input: Partial<ModuleInput>): Promise<{ id: number }> {
  return apiFetch(`/modules/${id}/`, { method: 'PATCH', body: input })
}

export function deleteModule(id: number): Promise<void> {
  return apiFetch<void>(`/modules/${id}/`, { method: 'DELETE' })
}

export interface LessonInput {
  module: number
  title: string
  lesson_type: LessonType
  content_url?: string
  order: number
  estimated_minutes: number
  content_file?: File | null
}

export function createLesson(input: LessonInput): Promise<{ id: number }> {
  const body = input.content_file instanceof File ? buildFormData(input) : input
  return apiFetch('/lessons/', { method: 'POST', body })
}

export function updateLesson(id: number, input: Partial<LessonInput>): Promise<{ id: number }> {
  const body = input.content_file instanceof File ? buildFormData(input) : input
  return apiFetch(`/lessons/${id}/`, { method: 'PATCH', body })
}

export function deleteLesson(id: number): Promise<void> {
  return apiFetch<void>(`/lessons/${id}/`, { method: 'DELETE' })
}

// --- Admin: bulk enroll ---

export function bulkEnroll(courseSlug: string, file: File): Promise<BulkEnrollResult> {
  const formData = new FormData()
  formData.append('file', file)
  return apiFetch<BulkEnrollResult>(`/courses/${courseSlug}/bulk-enroll/`, {
    method: 'POST',
    body: formData,
  })
}

// --- Admin: reporting ---

export interface ReportFilters {
  course?: number
  status?: string
  date_from?: string
  date_to?: string
}

function reportQueryString(filters: ReportFilters): string {
  const params = new URLSearchParams()
  if (filters.course) params.set('course', String(filters.course))
  if (filters.status) params.set('status', filters.status)
  if (filters.date_from) params.set('date_from', filters.date_from)
  if (filters.date_to) params.set('date_to', filters.date_to)
  return params.toString()
}

export function fetchEnrollmentReport(filters: ReportFilters): Promise<ReportRow[]> {
  const query = reportQueryString(filters)
  return apiFetch<ReportRow[]>(`/reports/enrollments/${query ? `?${query}` : ''}`)
}

export async function downloadEnrollmentReportCsv(filters: ReportFilters): Promise<void> {
  const query = reportQueryString(filters)
  const blob = await apiFetchBlob(`/reports/enrollments/?${query ? `${query}&` : ''}export=csv`)
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = 'enrollment_report.csv'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}
