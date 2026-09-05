// A leaderboard row — always scoped server-side to the caller's own
// organization (see backend gamification.views.LeaderboardEntryViewSet),
// so this list is already safe to render as-is, no further filtering needed.
export interface LeaderboardEntry {
  user_id: number
  first_name: string
  last_name: string
  total_points: number
  courses_completed_count: number
  average_quiz_score: string
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
}
