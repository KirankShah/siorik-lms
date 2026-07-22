import { apiFetch } from './apiClient'
import type { Assignment, AssignmentSubmission, SubmissionType } from '../types/assignment'

// A Page of type ASSIGNMENT has at most one Assignment (page is OneToOne on
// the backend) — null means none has been created yet.
export async function fetchAssignmentForPage(pageId: number): Promise<Assignment | null> {
  const assignments = await apiFetch<Assignment[]>(`/assignments/?page=${pageId}`)
  return assignments[0] ?? null
}

export interface AssignmentInput {
  page: number
  instructions_json: unknown[]
  submission_type: SubmissionType
  max_marks: number
  due_offset_days: number | null
}

export function createAssignment(input: AssignmentInput): Promise<Assignment> {
  return apiFetch<Assignment>('/assignments/', { method: 'POST', body: input })
}

export function updateAssignment(id: number, input: Partial<AssignmentInput>): Promise<Assignment> {
  return apiFetch<Assignment>(`/assignments/${id}/`, { method: 'PATCH', body: input })
}

// --- Learner: submissions ---

export function fetchMySubmissions(assignmentId: number): Promise<AssignmentSubmission[]> {
  return apiFetch<AssignmentSubmission[]>(`/assignment-submissions/?assignment=${assignmentId}`)
}

export interface AssignmentSubmissionInput {
  assignment: number
  text_response?: string
  file?: File | null
}

export function createAssignmentSubmission(input: AssignmentSubmissionInput): Promise<AssignmentSubmission> {
  const body = input.file instanceof File ? buildSubmissionFormData(input) : { assignment: input.assignment, text_response: input.text_response }
  return apiFetch<AssignmentSubmission>('/assignment-submissions/', { method: 'POST', body })
}

function buildSubmissionFormData(input: AssignmentSubmissionInput): FormData {
  const formData = new FormData()
  formData.append('assignment', String(input.assignment))
  if (input.text_response) formData.append('text_response', input.text_response)
  if (input.file instanceof File) formData.append('file', input.file)
  return formData
}

// --- Admin: grading ---

export function fetchUngradedAssignmentSubmissions(): Promise<AssignmentSubmission[]> {
  return apiFetch<AssignmentSubmission[]>('/assignment-submissions/?ungraded=true')
}

export function gradeAssignmentSubmission(
  id: number,
  input: { marks_awarded: number; grader_feedback: string },
): Promise<AssignmentSubmission> {
  return apiFetch<AssignmentSubmission>(`/assignment-submissions/${id}/`, { method: 'PATCH', body: input })
}
