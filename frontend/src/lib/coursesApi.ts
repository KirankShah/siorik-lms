import { apiFetch } from './apiClient'
import type { CourseDetail, CourseListItem, Enrollment } from '../types/courses'

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
