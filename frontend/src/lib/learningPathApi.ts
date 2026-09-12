import { apiFetch } from './apiClient'
import type { LearningPath } from '../types/learningPath'

// Already scoped to the caller's own tier/eligibility server-side — see
// backend courses.learning_path.build_learning_path.
export function fetchMyLearningPath(): Promise<LearningPath> {
  return apiFetch<LearningPath>('/learning-path/')
}
