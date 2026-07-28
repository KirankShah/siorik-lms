import { apiFetch } from './apiClient'
import type { Badge, LeaderboardEntry, UserBadge } from '../types/gamification'

// Already scoped to the caller's own organization server-side.
export function fetchLeaderboard(): Promise<LeaderboardEntry[]> {
  return apiFetch<LeaderboardEntry[]>('/leaderboard/')
}

export function fetchBadges(): Promise<Badge[]> {
  return apiFetch<Badge[]>('/badges/')
}

// Already scoped to the caller's own badges server-side.
export function fetchMyBadges(): Promise<UserBadge[]> {
  return apiFetch<UserBadge[]>('/user-badges/')
}
