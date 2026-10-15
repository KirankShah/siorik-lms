import type { PeriodicExamLearnerSummary, PeriodicExamReasonCode } from '../types/periodicExams'

const REASON_MESSAGES: Record<PeriodicExamReasonCode, string> = {
  ALREADY_PASSED: 'You have passed this cycle. No further attempt is needed.',
  REVOKED: 'Your eligibility for this cycle is no longer active.',
  ATTEMPT_IN_PROGRESS: 'You already have an attempt in progress.',
  ATTEMPT_LIMIT_REACHED: 'You have used all attempts available for this cycle.',
  INSUFFICIENT_POOL: 'A full exam cannot be formed for your assigned level yet.',
  CYCLE_CLOSED: 'This Periodic Exam cycle has closed.',
}

export function periodicExamReasonMessage(code: PeriodicExamReasonCode | null): string | null {
  return code ? REASON_MESSAGES[code] : null
}

export function periodicExamStatus(summary: PeriodicExamLearnerSummary): string {
  if (summary.passed) return 'Passed'
  if (summary.open_attempt_id) return 'In progress'
  if (summary.completed) return 'Failed — retake available'
  return 'Not started'
}

export function formatPeriodicExamDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeZone: 'Asia/Kathmandu' }).format(new Date(value))
}
