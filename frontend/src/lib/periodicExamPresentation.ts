import { ApiError } from './apiClient'
import type {
  PeriodicExamAvailability,
  PeriodicExamLearnerSummary,
  PeriodicExamReasonCode,
} from '../types/periodicExams'

const REASON_MESSAGES: Record<PeriodicExamReasonCode, string> = {
  ALREADY_PASSED: 'You have passed this cycle. No further attempt is needed.',
  REVOKED: 'Your eligibility for this cycle is no longer active.',
  ATTEMPT_IN_PROGRESS: 'You already have an attempt in progress.',
  ATTEMPT_LIMIT_REACHED: 'You have used all attempts available for this cycle.',
  INSUFFICIENT_POOL: 'A full exam cannot be formed for your assigned level yet.',
  CYCLE_POOL_EXHAUSTED: 'There are not enough new questions for another attempt this cycle.',
  CYCLE_CLOSED: 'No Periodic Exam cycle is open right now.',
}

// Codes the learner endpoints return as errors rather than summary reasons.
const ERROR_MESSAGES: Record<string, string> = {
  ...REASON_MESSAGES,
  NOT_ELIGIBLE: 'You are not included in the current Periodic Exam cycle. Please contact your administrator.',
  FEATURE_DISABLED: 'Periodic Exam is not available for your organization right now.',
  SUBSCRIPTION_EXPIRED: "Your organization's subscription has expired.",
}

const GENERIC_ERROR = 'Periodic Exam details could not be loaded. Please try again.'

/** A learner-facing message for a failed Periodic Exam request, using the server's reason code. */
export function periodicExamErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.body && typeof error.body === 'object') {
    const { code, detail } = error.body as { code?: unknown; detail?: unknown }
    if (typeof code === 'string' && ERROR_MESSAGES[code]) return ERROR_MESSAGES[code]
    if (typeof detail === 'string' && detail) return detail
  }
  return GENERIC_ERROR
}

/** Shown instead of the exam when the feature is enabled but no cycle is open. */
export function periodicExamNotOpenMessage(availability: PeriodicExamAvailability | null): string {
  const upcoming = availability?.upcoming_cycle
  if (upcoming) {
    return `Your first Periodic Exam (${upcoming.display_label}) opens on ${formatPeriodicExamDate(upcoming.starts_at)}.`
  }
  return REASON_MESSAGES.CYCLE_CLOSED
}

export function periodicExamReasonMessage(code: PeriodicExamReasonCode | null): string | null {
  return code ? REASON_MESSAGES[code] : null
}

export function periodicExamStatus(summary: PeriodicExamLearnerSummary): string {
  return {
    PENDING: 'Pending',
    IN_PROGRESS: 'In progress',
    RETAKE: 'Retake required',
    PASSED: 'Passed',
    FAILED: 'Failed',
  }[summary.status]
}

export function formatPeriodicExamDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeZone: 'Asia/Kathmandu' }).format(new Date(value))
}
