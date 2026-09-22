import type { Organization } from './auth'
import type { TimingMode } from './orgSettings'

export type LevelQuestionType = 'SINGLE_CHOICE' | 'MULTIPLE_ANSWER'

export type LevelAssessmentStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'PASSED' | 'FAILED'

// Never carries is_correct — that's answer-key data, only ever revealed
// per-answer after submission (see LevelAssessmentAnswer below), same
// separation as backend LevelChoiceSerializer / assessments.Choice.
export interface LevelChoice {
  id: number
  choice_text: string
  order: number
}

export interface LevelQuestion {
  id: number
  question_text: string
  question_type: LevelQuestionType | ''
  marks: number
  choices: LevelChoice[]
  // true when this question has since been deleted from the Question Bank
  // (levelassessments.serializers.LevelAssessmentAttemptSerializer.get_questions)
  // — every other field on the placeholder is blank/zeroed, never real data.
  removed: boolean
}

// pass_threshold/questions_per_attempt/timing_mode/seconds_per_question/
// total_exam_minutes are computed server-side from
// org_settings.OrganizationSettings (one row per organization, shared by all
// four levels) — read-only here; edited from the Organization Settings
// screen (pages/admin/OrganizationSettingsPage.tsx). seconds_per_question
// only applies when timing_mode is 'PER_QUESTION'; total_exam_minutes only
// when it's 'FIXED_TOTAL' — see LevelAssessmentPage.tsx.
export interface AssessmentLevelSummary {
  id: number
  organization: Organization
  name: string
  name_display: string
  pass_threshold: number
  questions_per_attempt: number
  timing_mode: TimingMode
  seconds_per_question: number
  total_exam_minutes: number
}

export interface LevelAssessmentAnswer {
  id: number
  question: number
  selected_choices: number[]
  is_correct: boolean
  // True when no choice was submitted (for example, because time expired).
  // It still earns zero marks, but is displayed separately from Incorrect.
  is_unanswered: boolean
  // Revealed only once this answer has been submitted and graded.
  correct_choice_ids: number[]
  explanation: string
  feedback_correct: string
  feedback_incorrect: string
}

export interface LevelAssessmentAttempt {
  id: number
  user: number
  assessment_level: number
  assessment_level_name: string
  pass_threshold: number
  started_at: string
  submitted_at: string | null
  score_percent: string
  passed: boolean
  // Resume support (see backend LevelAssessmentAttempt's own field
  // docstrings) — which question the learner is on, their own selections so
  // far (never answer-key data, safe pre-submission), and how many seconds
  // remain in the CURRENT timer segment, computed fresh server-side on every
  // fetch from the stored segment-start timestamp. The frontend seeds its
  // own client-side countdown from remaining_seconds in every case — a
  // fresh start, a live re-fetch, or a resume after time away — rather than
  // assuming the full per-question/total-exam allocation.
  current_question_index: number
  answers_so_far: Record<string, number[]>
  remaining_seconds: number
  questions: LevelQuestion[]
  answers: LevelAssessmentAnswer[]
}

export interface MyAssessmentLevelStatus {
  assigned: boolean
  assessment_level?: AssessmentLevelSummary
  status?: LevelAssessmentStatus
  open_attempt_id?: number | null
  // None = unlimited (org's max_level_assessment_attempts unset); otherwise
  // how many more attempts this learner may still start, floored at 0.
  attempts_remaining?: number | null
}

// Result of POST /assessment-levels/<id>/import-questions/ — one entry per
// spreadsheet row that was committed or rejected. `row` is null when the
// failure is a whole-sheet problem (a header row missing a required column).
export interface LevelQuestionImportCreated {
  sheet: string
  row: number
  question_set: string
}

export interface LevelQuestionImportFailure {
  sheet: string
  row: number | null
  reason: string
}

export interface LevelQuestionImportResult {
  created: LevelQuestionImportCreated[]
  failed: LevelQuestionImportFailure[]
}

// Dry-run preview of a replace-import's destructive impact — see
// lib/levelAssessmentsApi.ts previewReplaceLevelQuestions.
export interface LevelQuestionReplaceImpact {
  question_set_labels: string[]
  existing_question_count: number
  affected_answer_count: number
}

// --- Question Bank admin (levelassessments.views.LevelQuestionAdminViewSet) ---

// Row shape for the Question Bank list — correct_answers here is the
// correct choice TEXT(s), for quick scanning; contrast with
// LevelQuestionDetail.correct_answers below, which is option letters (A-E),
// what the edit form actually needs.
export interface LevelQuestionListItem {
  id: number
  question_set_label: string
  assessment_level_name: string
  organization_name: string
  question_text: string
  question_type: LevelQuestionType
  correct_answers: string[]
  marks: number
}

// Options keyed by letter (A-E) — a blank string for any letter this
// question doesn't use, so the edit form always has exactly 5 fields to
// render regardless of how many options were actually filled in.
export type LevelQuestionOptions = Record<'A' | 'B' | 'C' | 'D' | 'E', string>

export interface LevelQuestionDetail {
  id: number
  question_set: number
  question_set_label: string
  assessment_level_name: string
  question_text: string
  question_type: LevelQuestionType
  options: LevelQuestionOptions
  // Option letters (A-E), not text — which checkboxes/radios the edit form
  // should show as checked.
  correct_answers: string[]
  marks: number
  explanation: string
  feedback_correct: string
  feedback_incorrect: string
}

// Write side of a Question Bank edit — validated server-side by the exact
// same rules as the Excel bulk import (see backend imports.py).
export interface LevelQuestionEditInput {
  question_text: string
  question_type: LevelQuestionType
  options: LevelQuestionOptions
  correct_answers: string[]
  marks: number
  explanation: string
  feedback_correct: string
  feedback_incorrect: string
}

// How many past attempts drew this question — fetched before a delete so
// the admin can be warned first (see components/admin/DeleteQuestionModal).
export interface LevelQuestionUsage {
  attempt_count: number
}

// --- Admin content-review preview (AssessmentLevelViewSet.preview) ---

// Simulates one real attempt's random draw for content review — same
// question shape the Question Bank "View/Edit" panel already uses
// (LevelQuestionDetail, answer key included), but never backed by a
// LevelAssessmentAttempt: no id, no timer, freely navigable both ways.
export interface LevelAssessmentPreview {
  assessment_level: AssessmentLevelSummary
  questions: LevelQuestionDetail[]
}
