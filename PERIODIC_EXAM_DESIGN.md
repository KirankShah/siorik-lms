# Periodic Exam — feature design

Status: approved; Phase 1 reconciled on `feature/periodic-exam-v2`
Prepared: 2026-10-15
Target: Siorik LMS, initially Lumbini Bikas Bank Limited, generic per organisation

## 0. Scope, repository state, and design decisions

This document describes a new, organisation-scoped **Periodic Exam** feature. It is deliberately separate from the existing Level Assessment. Phase 1 implements only settings/cycle infrastructure, APIs, the calendar adapter, the platform toggle, and the org-admin settings UI.

The canonical production base is `origin/main` at `54b9224a98e38c37533df86cba86ac9811078890`.
Phase 1 v2 is based on `integration/main-2026-10`, which adds only the recorded
baseline and the separately reviewed certificate/categorize regression tests.
The real base already contains `levelassessments`, `org_settings`, subscription
middleware, Resources, narration, certificates, and Knowledge Score. Phase 1
uses those interfaces directly while keeping Periodic Exam data in its own app;
the obsolete `fresh-start` and archive/deployment lines are not merged.

Recommended high-level choices:

1. Add a new Django app, `periodic_exams`, with its own settings, cycles, eligible-participant snapshots, attempt lifecycle, paper snapshots, usage history, reports, and reminder command.
2. Reuse the existing organisation/learner levels and the existing `levelassessments.LevelQuestion`/`LevelChoice` bank as **read-only source content**. Snapshot source content into each cycle so edits or deletes cannot change an open or historical exam.
3. Do not call Level Assessment finalisation. Periodic Exam grading must have no certificate, badge, leaderboard, Knowledge Score, level assignment, or learning-path effects.
4. Store all authoritative instants in UTC, calculate the business calendar in `Asia/Kathmandu`, and freeze both Gregorian boundaries and Bikram Sambat labels/components on each cycle.
5. Generate cycles on demand after a cycle has started. Only the reminder command needs a scheduler.

## 1. Existing code reuse and isolation

### 1.1 Safe reuse

| Existing area | Reuse | Boundary |
|---|---|---|
| `accounts.Organization` and `accounts.User` | Organisation ownership, learner role, `is_active`, `assessment_level`, name/email, and `branch_department` | Periodic Exam owns its eligibility snapshots and history. It does not change role or level semantics. |
| `levelassessments.AssessmentLevel`, `LevelQuestion`, `LevelChoice` | Source question bank by organisation and learner level; choice-based content shape; existing normalized-question-text rule | Read-only input. No Periodic Exam attempts or answers are written to Level Assessment tables. |
| `levelassessments.services.normalize_question_text` | Treat visibly equivalent question wording as one draw key | Pure helper only; no call to Level Assessment draw/start/finalise services. |
| Level Assessment sequential flow | The concepts of persisted current index, server-derived remaining time, save-on-change, resume catch-up, auto-lock, and server-side expiry | Implemented independently in `periodic_exams.services`, against frozen cycle/attempt data and a hard cycle deadline. |
| Level Assessment choice grading | Exact selected-choice-set equality for `SINGLE_CHOICE` and `MULTIPLE_ANSWER` | A small Periodic Exam pure grader should apply the same rule to snapshot option keys. It must not call `finalize_level_assessment_attempt`. |
| `core.permissions` | `IsPlatformAdminRole`, `IsOrgAdminRole`, authenticated-role conventions | Add Periodic Exam-specific enabled/ownership checks; do not rely on hidden frontend routes. |
| `core.subscription_middleware.SubscriptionAccessMiddleware` | Existing API-wide subscription expiry and org-admin grace/soft-lock | New `/api/periodic-exams/` routes are not allowlisted, so locked tenant users remain blocked automatically. Add explicit service checks as defence in depth for commands and direct service calls. |
| Staff Training Report helpers in `courses.views` | Flat shared dataset for JSON/CSV/XLSX, `csv.writer`, `openpyxl.Workbook`, header formatting, freeze pane, and spreadsheet-formula neutralisation | Move only generic export helpers to a neutral utility if worthwhile, with existing report regression tests. Otherwise reproduce the small safe helpers locally to avoid changing the current report. |
| `apiFetchBlob` and current report download pattern | Browser download of CSV/XLSX | New API wrapper and report page; existing report contract remains unchanged. |
| Sidebar, `App.tsx`, dashboard card patterns | Role-gated routes, cards, loading/error states | Visibility additionally depends on server-returned Periodic Exam availability. |
| Email construction/delivery conventions | Branding, text+HTML email, logging, frontend login URL | New recipient query, delivery ledger, service, and management command. It must not reuse existing reminder eligibility or exemption behavior. |

### 1.2 Code that must not be repurposed or behaviourally changed

- Do not add Periodic Exam fields to `org_settings.OrganizationSettings`. Its pass mark, timing, attempt limits, certificates, and Level Assessment coupling must remain exactly as they are.
- Do not change `LevelAssessmentAttempt`, `LevelAssessmentAnswer`, their URLs/serializers/services, current no-repeat algorithm, current UI, or question-bank authoring behaviour for Level Assessment.
- Do not call `levelassessments.services.finalize_level_assessment_attempt`: it updates gamification, awards badges, and checks learning-path certificate issuance.
- Do not call quiz submission/finalisation. `assessments.QuizViewSet.submit` records course quiz attempts, learning activity, gamification, and certificate-related state.
- Do not update `accounts.User.assessment_level` after a Periodic Exam.
- Do not write `gamification` models or services, certificate services, course/slide progress, enrollments, leaderboard data, or Knowledge Score data.
- Do not extend `send_inactivity_reminders`, use its audience functions, use its last-sent fields, or consult `User.reminder_exempt`. Periodic Exam reminders are explicitly separate.
- Do not add Periodic Exam routes to the subscription middleware allowlist.
- Do not alter existing answer-key exposure rules. Periodic Exam serializers must independently hide snapshot answer keys before submission (and after submission unless review is explicitly approved).

These boundaries mean Periodic Exam can consume the same authored question content without changing how Level Assessment chooses, times, scores, reports, or reacts to an attempt.

## 2. Proposed data model

All models below live in a new `backend/periodic_exams/` app. Names are proposals.

### 2.1 `PeriodicExamSettings`

One-to-one with `Organization` (`related_name='periodic_exam_settings'`). This is intentionally separate from `OrganizationSettings`.

Fields:

- `organization`: one-to-one, cascade delete.
- `enabled`: boolean, default `False`; writable only by platform admin.
- `frequency`: `MONTHLY`, `QUARTERLY`, `HALF_YEARLY`, `YEARLY`.
- `questions_per_exam`: positive integer, default `30`.
- `pass_mark_percent`: integer 0–100, default `60`.
- `seconds_per_question`: positive integer, default `60`, suggested minimum 5.
- `max_attempts_per_cycle`: positive integer, default `2`.
- `reminders_enabled`: boolean, default `False`.
- `reminder_days_before_end`: JSON list of unique positive integers, default `[7, 2]`, normalized descending.
- `configuration_version`: positive integer, incremented on any operational setting change.
- `enabled_at`, `enabled_from`, `disabled_at`, `updated_at`: timestamps. First enable sets `enabled_from` to the next full natural period. Re-enable preserves a current cycle so remaining attempts can continue; without a current cycle it schedules the next full period.
- `pending_frequency`: nullable frequency and `pending_frequency_effective_at`: nullable UTC boundary. A mid-cycle frequency change keeps the old frequency until the next full period of the new frequency.
- `updated_by`: nullable `User` FK with `SET_NULL`.

The row holds the configuration to use when the next cycle is created. An existing cycle uses only its own snapshots, so edits never affect it.

Indexes/constraints:

- One-to-one unique index on `organization_id`.
- Check constraints for positive question/time/attempt values and pass mark range. Keep serializer validation too because MySQL check enforcement varies by version/configuration.

### 2.2 `PeriodicExamCycle`

An immutable cycle header.

Fields:

- `organization` FK.
- `sequence`: monotonically increasing per organisation.
- `frequency_snapshot`, `configuration_version`.
- `questions_per_exam`, `pass_mark_percent`, `seconds_per_question`, `max_attempts_per_cycle` snapshots.
- `reminders_enabled`, `reminder_days_before_end` snapshots.
- `starts_at`: UTC datetime for 00:00:00 on the first cycle day in `Asia/Kathmandu`, inclusive.
- `ends_at`: UTC datetime for 00:00:00 after the last cycle day in `Asia/Kathmandu`, exclusive.
- `start_date_ad`, `end_date_ad`: Gregorian date display/audit snapshots, with `end_date_ad` being the inclusive last day.
- `start_year_bs`, `start_month_bs`, `start_day_bs`, `end_year_bs`, `end_month_bs`, `end_day_bs`.
- `fiscal_year_start_bs`, `period_number`, `display_label` (for example `2083/84 Q1 (Shrawan–Asoj)`).
- `created_at`.

Do not persist a mutable OPEN/CLOSED flag; status is derived from the frozen boundaries. A reconciliation service closes expired open attempts when any relevant endpoint/report/reminder job is invoked.

Indexes/constraints:

- Unique `(organization, sequence)`.
- Unique `(organization, starts_at)`.
- Index `(organization, starts_at, ends_at)` for current-cycle lookup.
- Index `(organization, -starts_at)` for report selectors.
- Check `starts_at < ends_at`.

### 2.3 `PeriodicExamCycleQuestion`

Frozen source pool for one cycle and level. This prevents question edits/deletes during a cycle from changing papers or grading.

Fields:

- `cycle` FK.
- `level`: snapshot of `User.AssessmentLevel` value (the implemented name follows the existing Level Assessment field).
- `source_question`: nullable FK to `LevelQuestion`, `SET_NULL`.
- `source_question_id_snapshot`: integer for audit after deletion.
- `normalized_text` plus `normalized_text_hash`: the existing normalized learner-visible text and its SHA-256 key. Keeping both makes conflicts diagnosable without putting a MySQL `TEXT` field in a unique index.
- `question_text`, `question_type`, `marks`: snapshots.
- `choices`: JSON array of stable A–E option keys and display text; the key is derived from the Level Assessment option order.
- `correct_option_keys`: JSON array, never exposed by learner pre-submit serializers.

At cycle creation, normalized duplicates are collapsed to one pool entry, matching the existing Level Assessment notion of duplicate learner-visible wording. If duplicates disagree on options/answers, cycle creation should fail validation and identify the conflicting source IDs rather than silently choose one.

Indexes/constraints:

- Unique `(cycle, level, normalized_text_hash)`.
- Index `(cycle, level)`.

### 2.4 `PeriodicExamParticipant`

One frozen report/eligibility row per learner per cycle.

Fields:

- `cycle` FK.
- `learner`: nullable FK with `SET_NULL`, plus `learner_id_snapshot`.
- `name_snapshot`, `email_snapshot`, `level_snapshot`, `branch_department_snapshot`.
- `can_form_full_exam`: frozen capacity result for the participant's level, so Phase 3 can deny an impossible first paper without failing cycle creation.
- `eligible_at`, `revoked_at` (deactivation after cycle inclusion).
- `attempts_used`: default 0.
- `best_score_percent`: nullable decimal.
- `passed_at`, `last_attempt_at`: nullable timestamps.

Participant snapshots preserve historical reporting if a user is later edited or deleted. `level_code` fixes the exam level for the cycle.

Indexes/constraints:

- Unique `(cycle, learner_id_snapshot)` for durable identity after user deletion.
- Index `(cycle, level_snapshot)`.
- Composite index `(cycle, passed_at, revoked_at)` for reminders/reporting.

### 2.5 `PeriodicExamAttempt`

Fields:

- `participant` FK.
- `attempt_number`.
- `started_at`, `submitted_at`.
- `current_question_index`.
- `timer_segment_started_at`.
- `score_percent`, `passed`.
- `submission_reason`: `LEARNER` or `QUESTION_TIMEOUT`. Cycle end never submits an already-started attempt, and Phase 3 has no separate reconciliation submission path.

Constraints/indexes:

- Unique `(participant, attempt_number)`.
- Index `(participant, submitted_at)`.

Do not use a partial unique constraint for “one open attempt”; MySQL does not enforce PostgreSQL-style conditional unique constraints. Instead, lock the `PeriodicExamParticipant` row with `select_for_update()` inside a transaction, check for an open attempt, allocate the next attempt number, and create it. The unique attempt-number constraint is the race backstop on both databases.

### 2.6 `PeriodicExamAttemptQuestion`

The immutable paper plus mutable answer/lock state.

Fields:

- `attempt` FK.
- `cycle_question` FK with `PROTECT`.
- `order`.
- `selected_option_keys`: JSON list, default empty.
- `locked_at`.
- `is_correct`: nullable until locked/finalized.
- `marks_awarded`: frozen awarded marks after locking.

Unique `(attempt, order)` and `(attempt, cycle_question)`, plus index `(attempt, order)`.

### 2.7 `PeriodicExamQuestionUsage`

Efficient lifetime no-repeat history.

Fields:

- `learner` FK. Organisation is derived through the learner and is not duplicated.
- `level`.
- `question_key`.
- `first_cycle_sequence`, `last_cycle_sequence`, `last_used_at`, `times_used`.

Unique `(learner, level, question_key)`. Index `(learner, level, last_cycle_sequence, last_used_at)`. Update only when a paper is successfully created, in the same transaction as attempt questions.

### 2.8 `PeriodicExamReminderDelivery`

Idempotency and audit ledger for the separate reminder job.

Fields:

- `cycle`, `participant` FKs.
- `days_before_end`.
- `scheduled_local_date`, `sent_at`.
- optional `status`/`error_summary` if retry auditing is desired.

Unique `(cycle, participant, days_before_end)` prevents duplicate sends if the command is run repeatedly.

### 2.9 Migration safety on MySQL production

Initial migrations should be additive only:

1. Add the new app and its new tables/indexes/constraints.
2. Add `PeriodicExamSettings` rows for existing organisations with `enabled=False`, or create them lazily with an idempotent post-save/on-read service. No feature becomes visible.
3. Do not alter or rewrite any existing table or applied migration.
4. Do not backfill or alter learners. Eligibility uses existing indexed user fields and participant snapshots are created in a later phase.
5. Use ordinary `BigAutoField`/FK types matching the project, bounded `CharField`s, `DecimalField`, `DateTimeField`, and Django `JSONField`, all supported by the configured MySQL path. Avoid PostgreSQL-only JSON lookups, partial indexes, array fields, and deferrable constraints.
6. Test generated migrations and schema creation on the supported MySQL version as well as PostgreSQL. Confirm index byte lengths under the production charset; store `question_key` as a fixed 64-character hex string rather than indexing normalized question text.
7. Deployment must install the pinned calendar dependency before applying migrations, although the schema migration itself must not execute calendar conversion code.

Rollback is safe while disabled: reverse migrations drop only new tables. Once production attempts exist, rollback requires an explicit data-retention/export decision rather than blind table removal.

## 3. Nepali calendar and cycle generation

### 3.1 Library and adapter

Pin `nepali-datetime==1.0.8.5` behind `periodic_exams/calendar.py`. The package supplies BS dates, variable-length month handling, and AD↔BS conversion. Pinning and wrapping it prevents library calls from spreading through models/views and makes it replaceable. Its package documentation is at <https://pypi.org/project/nepali-datetime/> and source at <https://github.com/amitgaru/nepali-datetime>.

The implementation contains a pinned month-length table for BS 2083–2090 and adjacent boundary rows for fiscal periods crossing the edges. Its exact source was `nepali_datetime/data/calendar_bs.csv` shipped inside the same pinned `nepali-datetime==1.0.8.5` package used by the adapter. Tests compare every supported month to that library and the adapter fails closed when a business date converts outside 2083–2090. This is **not independent verification**; it is only a dependency-parity snapshot. Bank-approved calendar samples remain a manual pre-deploy gate, especially for projected later years.

The project remains globally `TIME_ZONE='UTC'`, `USE_TZ=True`. Periodic Exam explicitly uses `zoneinfo.ZoneInfo('Asia/Kathmandu')` for business-day calculations and converts boundary instants to UTC for storage/comparison.

### 3.2 Variable month lengths

Never hard-code 29/30/31/32-day assumptions. Build a cycle’s first BS date, build the next period’s first BS date through the adapter, convert both to AD, and define:

- `starts_at` = local midnight at first BS date, inclusive.
- `ends_at` = local midnight at next period’s first BS date, exclusive.
- inclusive display end date = `ends_at` in Kathmandu minus one calendar day.

This naturally follows each published BS month length.

### 3.3 Fiscal-year boundaries

BS month numbers are: 1 Baishakh, 2 Jestha, 3 Asar, 4 Shrawan, 5 Bhadra, 6 Asoj, 7 Kartik, 8 Mangsir, 9 Poush, 10 Magh, 11 Falgun, 12 Chaitra.

- Fiscal year `Y/Y+1` starts at **Shrawan 1 of BS year Y** and ends at the last day of **Asar of BS year Y+1**.
- Quarterly:
  - Q1: Shrawan 1 through last day of Asoj.
  - Q2: Kartik 1 through last day of Poush.
  - Q3: Magh 1 through last day of Chaitra.
  - Q4: Baishakh 1 through last day of Asar in the following BS calendar year.
- Half-yearly:
  - H1: Shrawan 1 through last day of Poush.
  - H2: Magh 1 through last day of Asar in the following BS calendar year.
- Yearly: Shrawan 1 through last day of Asar in the following BS calendar year.
- Monthly: first through last day of the current BS month; it still receives the appropriate fiscal-year label.

### 3.4 On-demand creation, no cycle cron

`ensure_current_cycle(organization, at=now)` is idempotent and transactional:

1. Convert `now` to Kathmandu time.
2. Lock the organisation’s `PeriodicExamSettings` row.
3. Return the already-frozen cycle containing `now`, if present.
4. If first enable has not reached `enabled_from`, return no cycle. Otherwise compute the applicable natural BS period, applying any due pending-frequency transition, create the cycle with a unique constraint race backstop, snapshot settings and question pools, and materialize eligible participants.
5. Reconcile any prior expired open attempts.

Phase 2 implements step 4 by reading `LevelQuestion`/`LevelChoice` only, validating normalized duplicate signatures, and bulk-creating the frozen pool and participant rows in batches of 500 inside the same transaction. Low question counts set `can_form_full_exam=False` on affected participants and never roll back the cycle.

Call it from availability/summary, learner start/resume/submit, org-admin settings/report, platform enable, and the reminder job. Do **not** create future or missed cycles. First enable records the next full boundary but does not create that cycle early. If nobody invokes the service during an entire period, a later call creates only the period containing that later call.

Before an enabled org admin changes operational settings, the settings API calls `ensure_current_cycle` so the current period is frozen with the old values. Non-frequency edits are then naturally picked up by the next created cycle. A frequency edit records `pending_frequency`; its effective boundary is the first full new-frequency period beginning on or after the current cycle ends. Until that boundary, on-demand cycles retain the old frequency. At/after that boundary the pending value is promoted atomically before creating the current cycle.

The reminder command is the only scheduled process. Running it daily is sufficient. It calls `ensure_current_cycle` before evaluating 7-day/2-day delivery dates.

## 4. Eligibility and frozen settings

- Eligible population: users in the cycle’s organisation who are currently active, are non-demo, have role `LEARNER`, have an assigned level, and have `date_joined < cycle.starts_at`.
- This rule uses existing account data only. There is no Periodic Exam learner-state model and no change to account create/reactivate/deactivate code.
- A newly created learner whose `date_joined` is during the cycle is deferred to the next cycle. Reactivation does not rewrite `date_joined`; therefore an older reactivated learner may be eligible if active when participants are materialized, which is an accepted consequence of the approved rule.
- Participant name/email/level/branch are frozen at cycle creation for a stable report.
- A level change during a cycle does not change the current participant/paper; it applies next cycle.
- Settings changes update only `PeriodicExamSettings`; current `PeriodicExamCycle` snapshots remain unchanged. The next cycle copies the latest version.
- Passing any attempt sets `participant.passed_at`. Further starts are denied even if the configured attempt cap is not reached.
- A platform disable hides the feature, denies new starts, and stops reminders while retaining cycles and attempts. An already-started attempt may finish. Re-enabling during the same frozen cycle restores access and allows remaining attempts.

## 5. Question selection and no-repeat history

### 5.1 Selection algorithm

Papers draw from `PeriodicExamCycleQuestion` for the participant’s frozen level.

Inside the participant-row lock used to start an attempt:

1. Collect `question_key`s already used by this learner in **this cycle**.
2. From the not-yet-used-in-this-cycle pool, split candidates into:
   - lifetime-unused keys: no `PeriodicExamQuestionUsage` row for learner+level+key;
   - previously used keys from older cycles.
3. Randomly sample lifetime-unused keys first.
4. If more are required, order old keys by `last_cycle_sequence ASC`, then `last_used_at ASC`; randomize within an equal age bucket. This is the “oldest-used first” fallback.
5. If those candidates cannot fill the paper, add current-cycle-used keys ordered least-recently-used first. Retakes are never blocked for capacity.
6. Randomize the final paper order, create all `PeriodicExamAttemptQuestion` rows, and upsert usage rows atomically.

This maximizes paper differences per learner and per retake; once the pool is exhausted, least-recently-used questions may repeat in the same cycle. Two learners may receive overlapping questions.

### 5.2 Capacity information and minimum

For every level assigned to an active learner at cycle creation:

`unique cycle pool size >= questions_per_exam`

is the only hard minimum for a level in use. A cycle/start cannot form a valid paper below that minimum, but platform enable is never blocked by question capacity. The settings and platform UI show per-level unique counts as neutral readiness information, not a warning or enable gate. Retakes always proceed by falling back to least-recently-used questions.

### 5.3 Performance

- Cycle question normalization/snapshot happens once per organisation/cycle, not per learner.
- Start uses indexed lookups scoped to one participant, one level, and one cycle.
- The compact usage table avoids scanning every historical attempt JSON, unlike the current Level Assessment reconstruction.
- Participant aggregates make reports/reminders set-based and avoid per-learner attempt queries.
- Use `bulk_create` for cycle questions, participants, and attempt questions, and iterator/batches for a large organisation.
- Lock only the settings row during cycle creation and one participant row during attempt creation/submission; do not lock the whole organisation or question bank.
- Optional cache: cycle pool IDs grouped by level, keyed by immutable cycle ID. Correctness must not depend on cache availability.

### 5.4 Current question-bank counts and repeat timing

The local development database was queried read-only on 2026-10-15 through the
real `main` models. “Unique” uses the existing Level Assessment normalized
visible-text rule. Phase 1 now exposes these neutral per-level unique counts to
both platform admins and the organisation admin; counts never block enabling.

| Organisation | Level | Rows | Unique |
|---|---:|---:|---:|
| Lumbini Bikas Bank Limited | Front-Line | 0 | 0 |
| Lumbini Bikas Bank Limited | Middle Management | 0 | 0 |
| Lumbini Bikas Bank Limited | Officer | 0 | 0 |
| Lumbini Bikas Bank Limited | Top Management | 0 | 0 |

At 30 questions per exam, **no current level can form even the first valid paper**, so there is no repeat-start cycle to calculate for current data. Lumbini must import at least 30 unique questions per used level for one attempt, or `30 × max_attempts_per_cycle` to guarantee all retakes in a cycle.

For a future pool of `N >= 30` unique questions and exactly one attempt per cycle, repeats first appear in cycle `floor(N / 30) + 1` (for example: 30 → cycle 2, 60 → cycle 3, 75 → cycle 3 after 15 unused questions). Multiple attempts consume additional unique questions in the same cycle first; after that pool is exhausted, the approved least-recently-used fallback permits repeats rather than blocking a retake.

## 6. Question types, grading, and the categorize bug

The two existing systems do **not** share one universal grader:

- `levelassessments.LevelQuestion` supports only `SINGLE_CHOICE` and `MULTIPLE_ANSWER`; its finalizer grades exact selected-choice-set equality.
- Course quiz `assessments.Question` supports single/multiple choice, true/false, fill blank, matching, ordering, categorize, hotspot, short answer, and essay. `QuizViewSet.submit` contains separate branches for ordering, matching, categorize, hotspot, and fill blank, with a generic exact-set branch for the simpler choice types.

Recommended Periodic Exam v1 uses the existing **Level Assessment question bank**, so it supports only single-choice and multiple-answer questions. Categorize and other interactive course-quiz types are not in that bank and will not be accepted into a cycle snapshot. Therefore the categorize grading path cannot be inherited: Periodic Exam neither calls the course quiz grader nor models category placements. On the reconciled `main` base, the course-quiz categorize grader was separately verified with two and three buckets, shuffled bucket order, one wrong item, apostrophes, and arrow characters; it correctly compares stored item-to-bucket IDs and all regression cases pass.

If interactive question types are later required, that is a separate scope: extract and test pure graders per type, then explicitly opt Periodic Exam into only verified graders. Do not copy the current inline categorize branch into Periodic Exam.

## 7. Attempt lifecycle and timer

- The server is authoritative. The browser receives `remaining_seconds`, displays a countdown, and sends saves/advances; it never decides whether time remains.
- Each question has its own `timer_segment_started_at` and cycle question duration snapshot.
- Selection changes are saved to the current attempt question. A successful answer/advance transaction locks that row; locked answers cannot change and the index can move only to exactly the next question.
- On any retrieve/save/answer/submit request, server catch-up calculates elapsed time. Expired questions are locked and scored using the last selection saved before expiry (empty if none), then the clock advances. It can cascade across several questions after a closed browser.
- No new attempt may start at or after `cycle.ends_at`. An attempt started before the boundary may continue until its own per-question timers and normal submission complete; cycle end does not truncate it.
- Final submission creates no external side effects. It totals frozen marks, compares with the cycle pass-mark snapshot, updates participant aggregates, and returns the result.
- Submission is idempotent. A repeated submit returns the existing submitted result, not a second grading event or a 500/duplicate row.
- Starting is denied when the resolved cycle has ended, the feature is disabled, a pass already exists, or the cap is used. A repeated/concurrent start returns the one existing open attempt. A pool below the paper size blocks every start with a clear capacity code; otherwise retakes always fill from unused-in-cycle then least-recently-used questions.
- `attempts_used` is updated transactionally on submission; the existence of any attempt row is the authoritative “Attempted” signal while an attempt is still open.
- Phase 3 duplicates the existing subscription-lock check in its service boundary in addition to relying on middleware, so direct service callers cannot bypass expiry policy.

## 8. API and permissions

Proposed base: `/api/periodic-exams/`.

### 8.1 Shared availability

- `GET /availability/`
  - Authenticated tenant roles.
  - Returns `{enabled, role_capabilities}` for the caller’s own organisation only.
  - Platform admin may receive `enabled: false` unless an organisation is explicitly selected on the platform settings endpoint.
  - Instructor gets no Periodic Exam capability.

### 8.2 Learner endpoints

- `GET /me/summary/` — current/upcoming cycle, participant status, attempted/completed, attempts used/remaining, best score, passed, open attempt ID.
- `POST /me/attempts/start/` — starts a current-cycle paper under participant lock.
- `GET /me/attempts/{id}/` — own attempt only; performs timer/cycle catch-up.
- `PUT /me/attempts/{id}/current-answer/` — save current selection only.
- `POST /me/attempts/{id}/advance/` — lock/score current question and advance.
- `POST /me/attempts/{id}/submit/` — idempotent final submission.
- `GET /me/attempts/{id}/result/` — own score and pass/fail only. No submitted choices, correct choices, feedback, or per-question review is returned.

Every query is derived from `request.user`; no client-supplied organisation, user, or level controls scope. Require role `LEARNER`, active user, enabled settings, matching participant, open cycle where appropriate, and non-locked subscription.

### 8.3 Org-admin endpoints

- `GET /settings/` — own organisation only.
- `PATCH /settings/` — own organisation operational fields only; never `enabled`.
- `GET /cycles/` — own organisation cycle selector.
- `GET /cycles/{id}/report/` — paginated/filterable own-organisation report.
- `GET /cycles/{id}/report.csv`
- `GET /cycles/{id}/report.xlsx`

Org admin is always scoped to their own organisation. Platform admin has read-only report access and must supply/select one organisation. Instructor and learner are denied. Validate the organisation before returning any row.

Report columns, in the required order:

1. Staff name
2. Email
3. Level
4. Branch/department
5. Cycle
6. Attempted (`attempts_used > 0`, so started at least once)
7. Completed (at least one submitted attempt)
8. Attempts used
9. Best score (blank if no submitted attempt)
10. Status: `Not attempted` when none started; `In progress` when an attempt is open and no pass exists; `Passed` when any attempt passed; otherwise `Failed`.
11. Last attempt date

JSON preview, CSV, and XLSX must be generated from one typed row builder. Escape spreadsheet formulas in all text columns. Use participant snapshots, so tenant history remains stable after staff profile edits/deletion. Add server pagination/search for UI, while exports stream or iterate the complete filtered dataset without loading unbounded rows into memory.

### 8.4 Platform-admin endpoints

- `GET /platform/organizations/` — organisation list with enabled state and minimal readiness counts.
- `PATCH /platform/organizations/{organization_id}/` — `{enabled: boolean}` only.
- `GET /readiness/?organization_id={id}` — platform-admin read-only per-level pool and eligible-learner counts. The organisation selector is mandatory.

Permission is platform admin only. Enabling returns per-level question counts as information but is never blocked by capacity. Operational exam settings remain an org-admin responsibility.

The same `GET /readiness/` path is available to an enabled organisation admin without a selector and is always scoped to their own organisation. Learners and instructors are denied. Each level includes `can_form_full_exam` and a clear informational note when its unique frozen/live pool is below `questions_per_exam`.

### 8.5 Subscription enforcement

The existing middleware blocks all new API endpoints for expired learners and soft-locks org admins after their configured grace period. Platform admins remain exempt. The reminder command is outside HTTP middleware, so it must explicitly skip organisations whose learners are subscription-locked on the Kathmandu local date. Disable state also suppresses all reminder sends.

## 9. Frontend design

### 9.1 Navigation and routing

- Add a small availability provider/hook loaded in the authenticated layout.
- When disabled, render no learner card/sidebar item and no org-admin Periodic Exam settings/report links. Direct routes still receive a server denial and render not-found/unavailable.
- Learner sidebar: `Periodic Exam` only for enabled organisations.
- Org admin sidebar: `Periodic Exam Settings` and `Periodic Exam Report` only when enabled.
- Platform admin: an enable/disable control on the organisation management page.
- Instructor: no Periodic Exam navigation.

### 9.2 Learner pages

- **Dashboard card:** cycle label and dates, status, attempts remaining, best score, pass state, and Start/Resume/View Result action.
- **Introduction page:** explains cycle dates, assigned level, number of questions, pass mark, seconds per question, attempt cap, no-backtracking rule, no-late rule, and that passing clears the cycle. It should show capacity/configuration errors without exposing question details.
- **Exam page:** one question at a time, strict countdown, save-on-change, no previous button, clear locked/auto-advance states, network retry messaging, and protection against accidental navigation. Client route state is never the authority.
- **Result page:** score, pass/fail, best attempt, attempts used/remaining, and cycle cleared state. There is no per-question answer review.

### 9.3 Admin pages

- **Periodic Exam Settings:** current-cycle read-only snapshot at top and editable “next cycle” settings below. Show “Changes apply from the next cycle” and neutral per-level question counts. Defaults: 30 questions, 60% pass mark, 60 seconds, 2 attempts, reminders off with days 7 and 2.
- **Periodic Exam Report:** cycle selector, search/filter, required columns, CSV and Excel buttons, empty/error/loading states.
- **Platform organisations:** accessible toggle with enable confirmation, readiness failure details, and no exposure of tenant report data.

### 9.4 Proposed frontend files

- New: `src/lib/periodicExamsApi.ts`, `src/types/periodicExams.ts`, `src/context/PeriodicExamAvailabilityContext.tsx` (or a focused hook), learner pages, admin settings/report pages, route guard, and tests.
- Existing: `src/App.tsx`, `components/shell/Sidebar.tsx`, `pages/DashboardPage.tsx`, `pages/admin/OrganizationsPage.tsx`, and possibly `routes/AppLayout.tsx`.
- Reuse answer-choice presentation where practical, but do not reuse `LevelAssessmentPage` state wholesale; separate API/state avoids behavioural coupling.

## 10. Reminder system

Add `python manage.py send_periodic_exam_reminders`, intended to run daily. It is separate from `send_inactivity_reminders`.

For each enabled, subscription-active organisation/current cycle whose cycle snapshot has reminders enabled:

1. Convert “today” to Kathmandu local date.
2. Match an exact configured `days_before_end` value against the inclusive cycle end date.
3. Query active, non-revoked participants with `passed_at IS NULL`.
4. Ignore `User.reminder_exempt` by explicit requirement.
5. Insert/check `PeriodicExamReminderDelivery` to make sends idempotent.
6. Send branded text+HTML email with cycle end date and LMS link; record success. Failures remain retryable and are logged without learner-sensitive content.

Use exact local dates, not “last sent + interval,” because reminders are tied to a frozen cycle end. If the command misses a configured day, the proposed default is not to send a stale reminder later; confirm this policy.

## 11. Risks and edge cases

| Case | Proposed handling |
|---|---|
| Learner changes level mid-cycle | Keep participant `level_code` and cycle pool fixed; new level applies next cycle. |
| Learner deactivated mid-cycle | Authentication immediately denies access; retain attempts/report row and send no reminders. No account lifecycle code is changed. |
| Learner reactivated mid-cycle | Eligibility is recalculated from approved existing fields. Because `date_joined` predates the cycle, an older reactivated learner can qualify if participants have not yet been materialized. |
| New learner mid-cycle | `date_joined >= cycle.starts_at`, so the learner is deferred to the next cycle. |
| Frequency changes mid-cycle | Current cycle snapshot is unchanged. Old frequency continues until the first full boundary of the new frequency, then the pending frequency is promoted. |
| Other settings change mid-cycle | Persist as next-cycle configuration; current cycle and attempts retain snapshots. |
| Feature disabled mid-cycle | Hide feature, deny new starts, stop reminders, retain data, and allow an already-started attempt to finish. Re-enable in the same cycle restores remaining attempts. |
| Browser closes/loss of network | Saved selection and server timestamp resume; catch-up locks elapsed questions and may auto-submit. |
| Browser/client clock wrong | Irrelevant to authority; client renders server `remaining_seconds`. Monitor server/NTP health. |
| Kathmandu midnight and UTC date differ | All business boundaries use `Asia/Kathmandu`; UTC only for persistence/comparison. Report/email dates use Kathmandu. |
| Attempt starts near cycle end | It may finish after cycle end; only starting a new attempt at/after the boundary is denied. |
| Double-click/double submission | Participant row lock, unique attempt number, attempt-question constraints, and idempotent submit response. |
| Concurrent start requests | `select_for_update()` participant lock; one open attempt and next number allocated transactionally. |
| Concurrent answer/timeout | Lock attempt/current question; compare server time once; exactly one transition wins. |
| Bank too small for first paper | Platform enable remains allowed and counts are informational. Attempt start cannot form a valid paper until the in-use level has at least `questions_per_exam` unique questions. |
| Bank too small for fresh retakes | Never block a retake; exhaust not-yet-used-in-cycle questions first, then fill least-recently-used. |
| Question edited/deleted mid-cycle | Cycle snapshots remain valid. Source change appears next cycle only. |
| Duplicate wording with different answer data | Cycle creation fails and identifies conflicts; do not silently snapshot an arbitrary answer key. |
| User/profile deleted | Participant snapshots preserve report identity; source user FK becomes null. |
| Subscription expires mid-cycle | Learner access/reminders stop immediately under existing lock; org admin follows current grace/soft-lock; data remains. |
| No one accesses LMS at boundary | First later request/reminder creates the current cycle on demand from exact BS boundaries. No cron required. |
| Reminder command runs more than once | Delivery unique constraint prevents duplicates. |
| Reminder command does not run on a configured day | Proposed no stale catch-up send; log/monitor the missed execution. |
| Manual grading question types | Not supported in v1; strict countdown/results require deterministic auto-graded questions. |
| Answer-key leakage | Snapshot correct keys never appear in active-attempt serializers; inspect all result serializers/tests. |

Operational risks include the single-maintainer calendar dependency, large participant/pool snapshots, email deliverability, and query growth. Mitigate with pinned dependency/adapter fixtures, batched inserts, set-based report queries, indexes above, idempotent jobs, and production-sized load testing.

## 12. Approved decisions

- Implementation branch starts cleanly from the canonical `origin/main` line via `integration/main-2026-10`; `fresh-start` is obsolete and is not merged.
- Periodic Exam reads the existing Level Assessment question bank as proposed.
- Defaults are 30 questions, 60% pass, 60 seconds per question, 2 attempts, and reminders off with days `[7, 2]`.
- Eligibility uses only current `is_active`, learner role, non-demo status, assigned level, and `date_joined < cycle.starts_at`; no learner-state model or account lifecycle changes.
- First enable starts at the next full natural cycle and missed cycles are never created.
- Frequency changes retain the old cadence until the next full period of the new cadence.
- Enable is never capacity-blocked; the first paper needs one full pool, while retakes use least-recently-used fallback.
- Disable hides the feature, blocks new starts, and stops reminders; re-enable in the same cycle restores remaining attempts.
- An attempt started before cycle end may finish. No attempt may start after cycle end.
- Learner results expose score/pass-fail only, with no answer review.
- Report statuses are Passed, Failed, Not attempted, and In progress.
- Platform admin has read-only report access through an organisation selector; org admin remains own-organisation-only.

## 13. Phased implementation plan

### Phase 0 — decisions and data readiness

No application code.

- Resolve section 12.
- Keep `main` as the canonical production base for every later phase.
- Import enough Lumbini questions for every assigned learner level. At 30 questions and `A` attempts, target at least `30 × A` unique questions per used level.
- Verify sample BS/AD fiscal boundaries with a bank-approved calendar.

Manual gate: completed by the approved decisions in section 12.

### Phase 1 — app skeleton, calendar, schema, settings/toggle

Likely files:

- `backend/requirements.txt`
- `backend/core/settings.py`, `backend/core/urls.py`
- new `backend/periodic_exams/apps.py`, `models.py`, `calendar.py`, verified BS month-length lookup, `serializers.py`, `permissions.py`, `services.py`, `views.py`, `urls.py`, `admin.py`, migrations
- `frontend/src/types/periodicExams.ts`, `lib/periodicExamsApi.ts`
- `frontend/src/pages/admin/OrganizationsPage.tsx`, `pages/admin/OrganizationSettingsPage.tsx`
- `frontend/src/components/admin/PeriodicExamSettingsCard.tsx`

Tests:

- Calendar conversion/month-length fixtures and every monthly/quarterly/half-yearly/yearly fiscal boundary.
- UTC/Kathmandu boundary behavior.
- Idempotent concurrent cycle creation.
- Settings validation/defaults/versioning and current-cycle immutability.
- Platform-only enable; org-admin operational update; learner/instructor denial; tenant isolation.
- Disabled feature returns no tenant configuration/cycle data through availability.
- Migration apply/reverse on fresh and populated PostgreSQL/MySQL schemas; migration drift check.

### Phase 2 — eligibility and frozen cycle pool

Likely files:

- `backend/periodic_exams/models.py`, `services.py`, tests/migration
- question readiness serializers/views

Tests:

- Existing active learner inclusion.
- New learner mid-cycle is deferred by `date_joined`; current active state is respected when participants are created.
- Deactivation removes access/reminder eligibility without changing account lifecycle code and preserves report history.
- Level and staff details freeze per participant.
- Cycle pool snapshots survive source edit/delete.
- Duplicate normalized wording conflict detection.

### Phase 3 — selection, attempts, grading, strict timer

Likely files:

- `backend/periodic_exams/services.py`, `serializers.py`, `views.py`, `urls.py`
- `backend/periodic_exams/tests/` and/or focused additions to `backend/test_api_flows.py`

Tests:

- Different randomized papers; organisation and level isolation.
- Lifetime unused-first and deterministic oldest-used-first fallback.
- Retakes exhaust unused-in-cycle questions first, then use least-recently-used fallback without a capacity block.
- Attempt cap; one pass clears cycle; best attempt aggregation.
- Exact-set grading for single and multiple answer only.
- No certificate/gamification/leaderboard/Knowledge Score/level/path changes.
- Per-question expiry, no backtracking, save/resume, multi-question catch-up, last-question auto-submit, and permission for an already-started attempt to finish after cycle end.
- Server clock authority, stale request, concurrent advance, double start, idempotent double submit.
- Answer-key confidentiality before submission and under cross-user/cross-org ID guessing.
- Subscription expiry/soft-lock.

### Phase 4 — learner UI

Likely files:

- `frontend/src/App.tsx`
- `frontend/src/routes/AppLayout.tsx` and new Periodic Exam guard
- `frontend/src/components/shell/Sidebar.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- new introduction, exam, and result pages/components
- API/types/context files from Phase 1

Tests:

- Feature off means no sidebar/card and direct route unavailable.
- Correct role visibility.
- Intro data/defaults and start/resume actions.
- Countdown from server value, save-on-change, auto-lock, no previous navigation, reload resume, expired response, last-question submit.
- Result/best attempt/pass-cleared behavior.
- Network error/retry does not unlock or double-submit.
- Existing Level Assessment page/dashboard/sidebar tests unchanged.
- Browser compatibility build target.

### Phase 5 — org settings and report/export UI/API

Likely files:

- `backend/periodic_exams/reports.py`, `views.py`, `serializers.py`, tests
- optional neutral `backend/core/export_utils.py` only if safely extracted with existing regressions
- new frontend admin settings/report pages
- `frontend/src/App.tsx`, `components/shell/Sidebar.tsx`, Periodic Exam API/types

Tests:

- Own-organisation-only report, all required columns, snapshot values.
- Attempted vs Completed semantics, best score, pass/fail/not-attempted/in-progress decision, last attempt date.
- Empty cycle, deleted/deactivated learner, level change, multiple attempts/pass.
- JSON/CSV/XLSX exact data parity, headers, filenames, Excel types, formula injection, Unicode/Nepali labels, large export iteration.
- Settings edits marked next-cycle and current snapshot unchanged.
- Platform/instructor/learner report denial and subscription lock.
- Frontend cycle selector, filters, empty/error/loading states, downloads.

### Phase 6 — separate reminders

Likely files:

- `backend/periodic_exams/reminders.py`
- `backend/periodic_exams/management/commands/send_periodic_exam_reminders.py`
- email templates if the project adopts templates
- tests

Tests:

- Exact Kathmandu 7-day/2-day due dates across AD/BS month boundaries.
- Only enabled cycle snapshot settings; only active, non-revoked, not-passed participants.
- A prior failed/completed attempt is reminded; one pass is not.
- `reminder_exempt` is deliberately ignored.
- Disabled and subscription-expired organisations skipped.
- Duplicate command runs do not duplicate mail; failure retry behavior.
- Existing inactivity command output/audiences unchanged.

### Phase 7 — full verification and deployment readiness (no deployment)

Automated:

- Focused Periodic Exam backend and frontend suites.
- Full backend suite with configured database and `--keepdb` where appropriate.
- `manage.py check` and `makemigrations --check --dry-run`.
- MySQL migration/schema and focused integration suite.
- Full frontend tests, lint, and production build/type checks.
- Production-sized selection/report/reminder query-count and timing tests.

Manual before deploy:

- Verify platform toggle off/on with Lumbini and another organisation.
- Confirm zero UI visibility when off for learner/org admin and direct-URL denial.
- Compare frozen monthly/quarterly/half-yearly/yearly dates to approved Nepali calendars, including Q4/H2/year crossing.
- Confirm the browser countdown, timeout, no-back navigation, close/reopen catch-up, slow/offline network, and attempt near cycle end.
- Confirm different learners and retakes receive expected papers and no current-cycle repeats.
- Verify question-bank edits/deletes do not change a current paper.
- Verify every report column against hand-calculated learners; open CSV/XLSX in Excel and test filters/Unicode/formula neutralisation.
- Test emails in a safe non-production mailbox, links, branding, exact reminder days, and no reminder after pass.
- Expire a test subscription and verify learner lock, org-admin grace/soft-lock, reminder suppression, and platform toggle access.
- Confirm Level Assessment, certificates, leaderboard, Knowledge Score, course quizzes, and existing reminder command are unchanged.
- Review query load and database locks with Lumbini-sized learner and question counts.

## 14. Approval checkpoint

The design decisions are approved. Implementation is phased; Phase 1 is limited to settings/cycle schema, calendar adapter and verification table, on-demand cycle generation, settings/toggle/availability APIs, and the two requested admin frontend surfaces.
