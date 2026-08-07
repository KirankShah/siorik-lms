import { apiFetch, apiFetchBlob } from './apiClient'
import type { AnalyticsOrganizationGroup, BulkEnrollResult, ReportRow } from '../types/admin'
import type {
  CourseAccessGrant,
  CourseDetail,
  CourseListItem,
  DemoLessonAccessGrant,
  Enrollment,
  LessonType,
} from '../types/courses'

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

// time_spent_seconds is a delta added to the slide's running total, not an
// absolute value — see courses.views.EnrollmentViewSet.slide_progress.
export function saveSlideProgress(
  enrollmentId: number,
  input: { slide: number; time_spent_seconds?: number; completed?: boolean },
): Promise<Enrollment> {
  return apiFetch<Enrollment>(`/enrollments/${enrollmentId}/slide-progress/`, {
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
  template?: number | null
  certificate_pass_threshold?: number
  certificate_expiry_months?: number | null
  completion_deadline_days?: number | null
  is_demo_available?: boolean
}

export function createCourse(input: CourseInput): Promise<CourseDetail> {
  const body = input.cover_image instanceof File ? buildFormData(input) : input
  return apiFetch<CourseDetail>('/courses/', { method: 'POST', body })
}

export function updateCourse(slug: string, input: Partial<CourseInput>): Promise<CourseDetail> {
  const body = input.cover_image instanceof File ? buildFormData(input) : input
  return apiFetch<CourseDetail>(`/courses/${slug}/`, { method: 'PATCH', body })
}

export function deleteCourse(slug: string): Promise<void> {
  return apiFetch<void>(`/courses/${slug}/`, { method: 'DELETE' })
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

// --- Admin: demo lesson access ---

export function fetchDemoLessonAccess(courseSlug: string): Promise<DemoLessonAccessGrant[]> {
  return apiFetch<DemoLessonAccessGrant[]>(`/courses/${courseSlug}/demo-lesson-access/`)
}

export function grantDemoLessonAccess(courseSlug: string, lessonId: number): Promise<DemoLessonAccessGrant> {
  return apiFetch<DemoLessonAccessGrant>(`/courses/${courseSlug}/demo-lesson-access/`, {
    method: 'POST',
    body: { lesson: lessonId },
  })
}

export function revokeDemoLessonAccess(courseSlug: string, lessonId: number): Promise<void> {
  return apiFetch<void>(`/courses/${courseSlug}/demo-lesson-access/revoke/`, {
    method: 'DELETE',
    body: { lesson: lessonId },
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

export interface ModuleOrder {
  id: number
  order: number
}

export function reorderModules(courseId: number, moduleIds: number[]): Promise<ModuleOrder[]> {
  return apiFetch<ModuleOrder[]>('/modules/reorder/', {
    method: 'POST',
    body: { course: courseId, module_ids: moduleIds },
  })
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

export interface LessonOrder {
  id: number
  order: number
  module: number
}

export function reorderLessons(moduleId: number, lessonIds: number[]): Promise<LessonOrder[]> {
  return apiFetch<LessonOrder[]>('/lessons/reorder/', {
    method: 'POST',
    body: { module: moduleId, lesson_ids: lessonIds },
  })
}

// lessonIds is the target module's full desired lesson order, including movedLessonId —
// the source module's remaining lessons are compacted server-side automatically.
export function moveLesson(movedLessonId: number, targetModuleId: number, lessonIds: number[]): Promise<LessonOrder[]> {
  return apiFetch<LessonOrder[]>('/lessons/move/', {
    method: 'POST',
    body: { lesson: movedLessonId, target_module: targetModuleId, lesson_ids: lessonIds },
  })
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

export interface InviteResult {
  email: string
  created: boolean
}

export function inviteLearnerByEmail(courseSlug: string, email: string): Promise<InviteResult> {
  return apiFetch<InviteResult>(`/courses/${courseSlug}/invite/`, {
    method: 'POST',
    body: { email },
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

// --- Admin: analytics dashboard ---

export interface AnalyticsFilters {
  organization?: number
  course?: number
}

function analyticsQueryString(filters: AnalyticsFilters): string {
  const params = new URLSearchParams()
  if (filters.organization) params.set('organization', String(filters.organization))
  if (filters.course) params.set('course', String(filters.course))
  return params.toString()
}

export function fetchAdminAnalytics(filters: AnalyticsFilters): Promise<AnalyticsOrganizationGroup[]> {
  const query = analyticsQueryString(filters)
  return apiFetch<AnalyticsOrganizationGroup[]>(`/reports/analytics/${query ? `?${query}` : ''}`)
}

export async function downloadAdminAnalyticsXlsx(filters: AnalyticsFilters): Promise<void> {
  const query = analyticsQueryString(filters)
  const blob = await apiFetchBlob(`/reports/analytics/?${query ? `${query}&` : ''}export=xlsx`)
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = 'admin_analytics.xlsx'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}
