// A leaderboard row — always scoped server-side to the caller's own
// organization (see backend gamification.views.LeaderboardEntryViewSet),
// so this list is already safe to render as-is, no further filtering needed.
export interface LeaderboardEntry {
  user_id: number
  first_name: string
  last_name: string
  assessment_level: string | null
  assessment_level_display: string
  total_points: number
  courses_completed_count: number
  average_quiz_score: string
  current_course_quiz_average: string | null
  quizzes_completed: number
  quizzes_required: number
  latest_level_assessment_score: string | null
  knowledge_score: string | null
  is_ranked: boolean
  last_assessed_at: string | null
  certificates_earned_count: number
  level_assessments_passed_count: number
  updated_at: string
}

export interface Badge {
  id: number
  key: string
  name: string
  description: string
  icon: string
  unlock_condition: string
}

export interface UserBadge {
  id: number
  badge: Badge
  earned_at: string
  celebration_seen_at: string | null
}
