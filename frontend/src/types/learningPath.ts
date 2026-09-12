export type LearningPathCourseState = 'completed' | 'current' | 'locked'

export interface LearningPathCourse {
  id: number
  slug: string
  title: string
  path_order: number
  state: LearningPathCourseState
}

export interface LearningPathTier {
  // 'FOUNDATION', or one of accounts.User.AssessmentLevel's codes
  // ('officer', 'management', ...) for a role tier.
  tier_key: string
  tier_label: string
  // True once every course in this tier is completed — the frontend shifts
  // the tier's nodes to the gold "completed milestone" tint once this flips,
  // distinct from the ordinary teal used for a single completed course.
  is_complete: boolean
  courses: LearningPathCourse[]
}

export interface LearningPath {
  // Percentage of the learner's own branch_department colleagues (same
  // organization) who've completed fewer of these path courses than the
  // learner has. Null whenever there's nothing meaningful to compare against
  // (no branch set, no colleagues sharing it) — see backend
  // courses.learning_path.branch_completion_percentile. Render the line only
  // when this isn't null; never show a placeholder value.
  branch_percentile: number | null
  tiers: LearningPathTier[]
}
